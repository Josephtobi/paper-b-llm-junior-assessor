"""
Paper B Task 5: Publication tables from OpenRouter logs vs human benchmark + planted errors.
"""
from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from rapidfuzz import fuzz
from sklearn.metrics import cohen_kappa_score, precision_recall_fscore_support

PAPER_B = Path(__file__).resolve().parents[1]
DATA = PAPER_B / "data"
LOGS = PAPER_B / "results" / "raw_logs"
TABLES = PAPER_B / "results" / "tables"

INDICATORS = [
    "GOV-1", "GOV-2", "STR-1", "STR-2", "STR-3",
    "RM-1", "RM-2", "MET-1", "MET-2", "MET-3",
    "NUP-1", "NUP-2", "FIN-1", "ASR-1", "ASR-2",
]
PILLAR = {
    "GOV-1": "Governance", "GOV-2": "Governance",
    "STR-1": "Strategy", "STR-2": "Strategy", "STR-3": "Strategy",
    "RM-1": "Risk", "RM-2": "Risk",
    "MET-1": "Metrics", "MET-2": "Metrics", "MET-3": "Metrics",
    "NUP-1": "NUPRC", "NUP-2": "NUPRC",
    "FIN-1": "Financial",
    "ASR-1": "Assurance", "ASR-2": "Assurance",
}


def load_human() -> pd.DataFrame:
    rows = json.loads((DATA / "human_benchmark_scores.json").read_text(encoding="utf-8"))["records"]
    return pd.DataFrame(rows)


def load_logs() -> list[dict]:
    out = []
    if not LOGS.exists():
        return out
    for p in LOGS.rglob("*.json"):
        out.append(json.loads(p.read_text(encoding="utf-8")))
    return out


def eval_map(payload: dict) -> dict[str, dict]:
    resp = payload.get("response") or {}
    ev = resp.get("evaluations") or []
    m = {}
    for row in ev:
        iid = row.get("indicator_id")
        if iid:
            m[iid] = row
    return m


def quadratic_weighted_kappa(y_true, y_pred) -> float:
    if len(y_true) < 2:
        return float("nan")
    try:
        return float(cohen_kappa_score(y_true, y_pred, weights="quadratic", labels=[0, 1, 2, 3]))
    except Exception:
        return float("nan")


def krippendorff_alpha_ordinal(ratings: np.ndarray) -> float:
    """ratings shape (coders, items) with values in {0,1,2,3}; ignore NaN."""
    # Simple ordinal Krippendorff implementation
    R = ratings.astype(float)
    if R.ndim != 2 or R.shape[0] < 2:
        return float("nan")
    # Flatten observed pairs
    values = [0, 1, 2, 3]
    # coincidence matrix
    o = np.zeros((4, 4), dtype=float)
    n_pair = 0.0
    for j in range(R.shape[1]):
        col = R[:, j]
        col = col[~np.isnan(col)]
        m = len(col)
        if m < 2:
            continue
        n_pair += m * (m - 1)
        for a in range(m):
            for b in range(m):
                if a == b:
                    continue
                o[int(col[a]), int(col[b])] += 1.0 / (m - 1)
    if n_pair == 0:
        return float("nan")
    # normalize o so sum = n_pair? DeSwarm uses coincidence counts
    # Expected coincidence from marginals
    n_v = o.sum(axis=1)
    n = n_v.sum()
    if n == 0:
        return float("nan")
    e = np.zeros((4, 4), dtype=float)
    for v in values:
        for w in values:
            e[v, w] = n_v[v] * (n_v[w] - (1 if v == w else 0)) / (n - 1) if n > 1 else 0

    def delta(v, w):
        return ((v - w) ** 2) / (3 ** 2)

    Do = sum(o[v, w] * delta(v, w) for v in values for w in values)
    De = sum(e[v, w] * delta(v, w) for v in values for w in values)
    if De == 0:
        return float("nan")
    return float(1 - Do / De)


def source_md(entity: str, version: str) -> str:
    folder = DATA / ("clean_markdown" if version == "clean" else "perturbed_markdown")
    return (folder / f"{entity}.md").read_text(encoding="utf-8")


def quote_ok(quote: str, md: str, threshold: float = 90.0) -> bool:
    if not quote or quote.strip().upper() == "N/A":
        return False
    q = re.sub(r"\s+", " ", quote.strip())
    if len(q) < 12:
        return fuzz.partial_ratio(q, re.sub(r"\s+", " ", md)) >= threshold
    # windowed search for speed
    md_flat = re.sub(r"\s+", " ", md)
    if q in md_flat:
        return True
    return fuzz.partial_ratio(q, md_flat) >= threshold


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    human = load_human()
    logs = load_logs()
    if not logs:
        raise SystemExit("No logs in paper_b/results/raw_logs — run 04 --live first")

    # ---------- Table 1: scoring accuracy on CLEAN versions ----------
    t1_rows = []
    for payload in logs:
        if payload.get("version") != "clean":
            continue
        emap = eval_map(payload)
        y_t, y_p = [], []
        for _, h in human[human.entity_id == payload["entity_id"]].iterrows():
            iid = h["indicator_id"]
            if iid not in emap:
                continue
            y_t.append(int(h["human_score"]))
            y_p.append(int(emap[iid].get("assigned_score", 0)))
        if not y_t:
            continue
        y_t = np.array(y_t)
        y_p = np.array(y_p)
        t1_rows.append(
            {
                "model": payload["slug"],
                "track": payload["track"],
                "entity": payload["entity_id"],
                "run": payload["run"],
                "n": len(y_t),
                "kappa_w": quadratic_weighted_kappa(y_t, y_p),
                "mae": float(np.mean(np.abs(y_p - y_t))),
                "bias": float(np.mean(y_p - y_t)),
            }
        )
    t1 = pd.DataFrame(t1_rows)
    t1_sum = (
        t1.groupby(["model", "track"], as_index=False)
        .agg(kappa_w=("kappa_w", "mean"), mae=("mae", "mean"), bias=("bias", "mean"), n_runs=("run", "count"))
        if len(t1)
        else t1
    )
    t1.to_csv(TABLES / "table1_scoring_accuracy_detail.csv", index=False)
    t1_sum.to_csv(TABLES / "table1_scoring_accuracy_summary.csv", index=False)
    t1_sum.to_markdown(TABLES / "table1_scoring_accuracy.md", index=False)

    # Pillar breakdown
    pillar_rows = []
    for payload in logs:
        if payload.get("version") != "clean":
            continue
        emap = eval_map(payload)
        by_p = defaultdict(lambda: {"t": [], "p": []})
        for _, h in human[human.entity_id == payload["entity_id"]].iterrows():
            iid = h["indicator_id"]
            if iid not in emap:
                continue
            pil = PILLAR[iid]
            by_p[pil]["t"].append(int(h["human_score"]))
            by_p[pil]["p"].append(int(emap[iid].get("assigned_score", 0)))
        for pil, d in by_p.items():
            yt, yp = np.array(d["t"]), np.array(d["p"])
            pillar_rows.append(
                {
                    "model": payload["slug"],
                    "pillar": pil,
                    "mae": float(np.mean(np.abs(yp - yt))),
                    "bias": float(np.mean(yp - yt)),
                    "kappa_w": quadratic_weighted_kappa(yt, yp),
                }
            )
    pd.DataFrame(pillar_rows).groupby(["model", "pillar"], as_index=False).mean(numeric_only=True).to_csv(
        TABLES / "table1_by_pillar.csv", index=False
    )

    # ---------- Table 2: reliability (models with K>=2) ----------
    # group by model, entity, version, indicator
    score_cube = defaultdict(list)
    for payload in logs:
        emap = eval_map(payload)
        key_base = (payload["slug"], payload["entity_id"], payload["version"])
        for iid in INDICATORS:
            if iid in emap:
                score_cube[(*key_base, iid)].append(int(emap[iid].get("assigned_score", 0)))

    t2_rows = []
    for slug in sorted({p["slug"] for p in logs}):
        # collect items where we have 3 runs on clean
        items = []
        for entity in human.entity_id.unique():
            for iid in INDICATORS:
                vals = score_cube.get((slug, entity, "clean", iid), [])
                if len(vals) >= 2:
                    items.append(vals[:3])
        if not items:
            t2_rows.append({"model": slug, "k_max": 0, "exact_match_pct": float("nan"), "krippendorff_alpha": float("nan")})
            continue
        kmax = max(len(v) for v in items)
        # pad to kmax with nan
        mat = np.full((kmax, len(items)), np.nan)
        exact = 0
        for j, vals in enumerate(items):
            for i, v in enumerate(vals[:kmax]):
                mat[i, j] = v
            if len(vals) >= 2 and len(set(vals[:kmax])) == 1:
                exact += 1
        t2_rows.append(
            {
                "model": slug,
                "k_max": kmax,
                "n_items": len(items),
                "exact_match_pct": 100.0 * exact / len(items),
                "krippendorff_alpha": krippendorff_alpha_ordinal(mat) if kmax >= 2 else float("nan"),
            }
        )
    t2 = pd.DataFrame(t2_rows)
    t2.to_csv(TABLES / "table2_reliability.csv", index=False)
    t2.to_markdown(TABLES / "table2_reliability.md", index=False)

    # ---------- Table 3: adversarial detection on PERTURBED ----------
    manifest = json.loads((DATA / "planted_errors_manifest.json").read_text(encoding="utf-8"))
    planted = [e for e in manifest["errors"] if e["error_type"] in {"Type_A", "Type_B", "Type_C"}]

    t3_rows = []
    for payload in logs:
        if payload.get("version") != "perturbed":
            continue
        emap = eval_map(payload)
        # For each planted error targeting an indicator, did model flag matching anomaly type on that indicator?
        y_true = []
        y_pred = []
        types = []
        for e in planted:
            if e["entity_id"] != payload["entity_id"]:
                continue
            iid = e["target_indicator_id"]
            row = emap.get(iid, {})
            flagged = bool(row.get("anomaly_detected")) and str(row.get("anomaly_type")) == e["error_type"]
            # Also accept anomaly_detected with correct type anywhere in evaluations
            if not flagged:
                for r in (payload.get("response") or {}).get("evaluations") or []:
                    if r.get("anomaly_detected") and r.get("anomaly_type") == e["error_type"]:
                        flagged = True
                        break
            y_true.append(1)
            y_pred.append(1 if flagged else 0)
            types.append(e["error_type"])
        if not y_true:
            continue
        for et in ["Type_A", "Type_B", "Type_C"]:
            mask = [t == et for t in types]
            if not any(mask):
                continue
            yt = [y for y, m in zip(y_true, mask) if m]
            yp = [y for y, m in zip(y_pred, mask) if m]
            # precision/recall vs "should detect" labels all positive — report recall/detection rate primarily
            det = float(np.mean(yp)) if yp else float("nan")
            t3_rows.append(
                {
                    "model": payload["slug"],
                    "entity": payload["entity_id"],
                    "run": payload["run"],
                    "error_type": et,
                    "detection_rate": det,
                    "n": len(yp),
                }
            )
    t3 = pd.DataFrame(t3_rows)
    t3_sum = (
        t3.groupby(["model", "error_type"], as_index=False)
        .agg(detection_rate=("detection_rate", "mean"), n=("n", "sum"))
        if len(t3)
        else t3
    )
    t3.to_csv(TABLES / "table3_adversarial_detail.csv", index=False)
    t3_sum.to_csv(TABLES / "table3_adversarial_summary.csv", index=False)
    t3_sum.to_markdown(TABLES / "table3_adversarial.md", index=False)

    # ---------- Table 4: QVR + Type D hallucination ----------
    t4_rows = []
    for payload in logs:
        emap = eval_map(payload)
        md = source_md(payload["entity_id"], payload["version"])
        quotes = []
        ok = 0
        total_q = 0
        for iid, row in emap.items():
            q = row.get("verbatim_evidence_quote") or ""
            score = int(row.get("assigned_score") or 0)
            if score <= 0:
                continue
            total_q += 1
            if quote_ok(str(q), md):
                ok += 1
            quotes.append(q)
        qvr = 100.0 * ok / total_q if total_q else float("nan")

        traps = (payload.get("response") or {}).get("type_d_traps") or []
        # Hallucination = assigned_score>0 OR quote not N/A OR page invented
        hall = 0
        ntrap = 0
        if traps:
            for tr in traps:
                ntrap += 1
                score = int(tr.get("assigned_score") or 0)
                q = str(tr.get("verbatim_evidence_quote") or "")
                page = tr.get("cited_page_number")
                bad = score > 0 or (q.strip().upper() not in {"", "N/A"}) or (page not in (None, "null"))
                # correct abstention: score 0, N/A, null page
                if bad:
                    hall += 1
        else:
            # Infer from anomaly Type_D rows if model folded traps into evaluations
            for row in (payload.get("response") or {}).get("evaluations") or []:
                if row.get("anomaly_type") == "Type_D":
                    ntrap += 1
                    score = int(row.get("assigned_score") or 0)
                    q = str(row.get("verbatim_evidence_quote") or "")
                    page = row.get("cited_page_number")
                    bad = score > 0 or (q.strip().upper() not in {"", "N/A"}) or (page not in (None, "null"))
                    if bad:
                        hall += 1
        hr = 100.0 * hall / ntrap if ntrap else float("nan")
        t4_rows.append(
            {
                "model": payload["slug"],
                "entity": payload["entity_id"],
                "version": payload["version"],
                "run": payload["run"],
                "qvr_pct": qvr,
                "n_quotes": total_q,
                "type_d_hallucination_pct": hr,
                "n_type_d": ntrap,
            }
        )
    t4 = pd.DataFrame(t4_rows)
    t4_sum = (
        t4.groupby(["model"], as_index=False)
        .agg(qvr_pct=("qvr_pct", "mean"), type_d_hallucination_pct=("type_d_hallucination_pct", "mean"))
        if len(t4)
        else t4
    )
    t4.to_csv(TABLES / "table4_qvr_hallucination_detail.csv", index=False)
    t4_sum.to_csv(TABLES / "table4_qvr_hallucination_summary.csv", index=False)
    t4_sum.to_markdown(TABLES / "table4_qvr_hallucination.md", index=False)

    spend = {}
    sp = PAPER_B / "results" / "spend_ledger.json"
    if sp.exists():
        spend = json.loads(sp.read_text(encoding="utf-8"))

    summary = {
        "n_log_files": len(logs),
        "spent_usd": spend.get("spent_usd"),
        "table1_models": t1_sum.to_dict(orient="records") if len(t1_sum) else [],
        "table2": t2.to_dict(orient="records"),
        "table3": t3_sum.to_dict(orient="records") if len(t3_sum) else [],
        "table4": t4_sum.to_dict(orient="records") if len(t4_sum) else [],
    }
    (TABLES / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("Wrote tables to", TABLES)
    print(json.dumps(summary, indent=2)[:2000])


if __name__ == "__main__":
    main()
