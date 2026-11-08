"""
Paper B Task 4: Dual-track OpenRouter evaluation under a hard $5 budget.

Track A — full page-anchored Markdown on cheap 1M-context Flash models (K=3)
Track B — ≤25k-token evidence packs on GPT-4o / Claude (K=1)

Usage:
  python paper_b/04_run_openrouter_eval.py            # dry-run estimate only
  python paper_b/04_run_openrouter_eval.py --live      # billable calls
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

PAPER_B = Path(__file__).resolve().parents[1]
ROOT = PAPER_B
DATA = PAPER_B / "data"
CLEAN = DATA / "clean_markdown"
PERT = DATA / "perturbed_markdown"
LOGS = PAPER_B / "results" / "raw_logs"
SPEND_FILE = PAPER_B / "results" / "spend_ledger.json"

load_dotenv(PAPER_B / ".env")

HARD_CAP_USD = 4.50
MAX_PACK_CHARS = 90_000  # ~22–25k tokens
EST_OUT_TOKENS = 2500

INDICATORS = [
    ("GOV-1", "Board Oversight"),
    ("GOV-2", "Management Role"),
    ("STR-1", "Climate Risks & Opportunities"),
    ("STR-2", "Business Model & Value-Chain Impact"),
    ("STR-3", "Climate Scenario Analysis"),
    ("RM-1", "ERM Integration"),
    ("RM-2", "Operational Mitigation & Adaptation"),
    ("MET-1", "Scope 1, 2 & 3 GHG Inventory"),
    ("MET-2", "SASB Extractive Metrics"),
    ("MET-3", "Decarbonisation Targets"),
    ("NUP-1", "Methane MRV & Env. Tracking"),
    ("NUP-2", "Flaring Commercialisation & Spills"),
    ("FIN-1", "IAS 36 & IAS 37 Connectivity"),
    ("ASR-1", "Sustainability Boundary Alignment"),
    ("ASR-2", "ICSR & ISSA 5000 Readiness"),
]

# OpenRouter pricing is USD per token in /models; store $/MTok for readability.
TRACK_A = [
    {
        "model": "deepseek/deepseek-v4.1-flash",
        "slug": "deepseek-v4.1-flash",
        "track": "A_full",
        "k": 3,
        "price_in_per_mtok": 0.051,
        "price_out_per_mtok": 0.567,
        "context": 1_048_576,
    },
    {
        "model": "google/gemini-2.5-flash",
        "slug": "gemini-2.5-flash",
        "track": "A_full",
        "k": 3,
        "price_in_per_mtok": 0.30,
        "price_out_per_mtok": 2.50,
        "context": 1_048_576,
    },
]

TRACK_B = [
    {
        "model": "openai/gpt-4o",
        "slug": "gpt-4o",
        "track": "B_pack",
        "k": 1,
        "price_in_per_mtok": 2.50,
        "price_out_per_mtok": 10.00,
        "context": 128_000,
    },
    {
        "model": "anthropic/claude-sonnet-4.5",
        "slug": "claude-sonnet-4.5",
        "track": "B_pack",
        "k": 1,
        "price_in_per_mtok": 3.00,
        "price_out_per_mtok": 15.00,
        "context": 1_000_000,
    },
]

ENTITIES = ["Seplat", "Oando", "Aradel"]
VERSIONS = ["clean", "perturbed"]


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def load_spend() -> dict:
    if SPEND_FILE.exists():
        return json.loads(SPEND_FILE.read_text(encoding="utf-8"))
    return {"spent_usd": 0.0, "calls": []}


def save_spend(ledger: dict) -> None:
    SPEND_FILE.parent.mkdir(parents=True, exist_ok=True)
    SPEND_FILE.write_text(json.dumps(ledger, indent=2), encoding="utf-8")


def log_path(cfg: dict, entity: str, version: str, run_k: int) -> Path:
    d = LOGS / cfg["slug"]
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{entity}_{version}_run{run_k}.json"


def extract_pages(md: str, page_nums: set[int], entity: str) -> str:
    """Pull selected pages; Oando uses SR/FS prefixes so match any --- ... Page N ---."""
    if not page_nums:
        return md[:MAX_PACK_CHARS]
    chunks = []
    pattern = re.compile(r"--- ([^\n]+?) ---")
    matches = list(pattern.finditer(md))
    for i, m in enumerate(matches):
        label = m.group(1)
        num_m = re.search(r"(\d+)$", label)
        if not num_m:
            continue
        n = int(num_m.group(1))
        if n not in page_nums:
            continue
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        chunks.append(md[start:end])
    pack = "\n".join(chunks)
    if len(pack) > MAX_PACK_CHARS:
        pack = pack[:MAX_PACK_CHARS] + "\n\n[TRUNCATED FOR PACK BUDGET]\n"
    if not pack.strip():
        pack = md[:MAX_PACK_CHARS]
    return f"# Evidence pack for {entity}\n\n{pack}"


def pages_for_entity(entity: str) -> set[int]:
    pages: set[int] = set()
    bench = json.loads((DATA / "human_benchmark_scores.json").read_text(encoding="utf-8"))
    for rec in bench["records"]:
        if rec["entity_id"] != entity:
            continue
        for n in re.findall(r"p\.?\s*(\d+)", rec.get("human_notes_or_page", ""), flags=re.I):
            pages.add(int(n))
        for a, b in re.findall(r"p\.?\s*(\d+)\s*[–-]\s*(\d+)", rec.get("human_notes_or_page", ""), flags=re.I):
            lo, hi = int(a), int(b)
            pages.update(range(lo, min(hi, lo + 8) + 1))
    manifest = json.loads((DATA / "planted_errors_manifest.json").read_text(encoding="utf-8"))
    for e in manifest["errors"]:
        if e["entity_id"] == entity and isinstance(e.get("page_number"), int):
            pages.add(e["page_number"])
    # Always include a few climate-critical pages as buffer
    if entity == "Seplat":
        pages.update({5, 9, 11, 13, 25, 37, 48, 49, 50, 51, 108, 109, 110, 111, 114, 115, 150, 151})
    elif entity == "Oando":
        pages.update({11, 17, 19, 22, 31, 43, 48, 49})
    elif entity == "Aradel":
        pages.update({19, 22, 31, 37, 42, 43, 44, 45})
    return pages


def load_document(entity: str, version: str, track: str) -> str:
    path = (CLEAN if version == "clean" else PERT) / f"{entity}.md"
    md = path.read_text(encoding="utf-8")
    if track == "B_pack":
        return extract_pages(md, pages_for_entity(entity), entity)
    return md


def build_prompt(entity: str, version: str, doc_text: str) -> str:
    indicator_lines = "\n".join(f"- {i}: {d}" for i, d in INDICATORS)
    traps = (
        "Also answer these ABSENT-METRIC traps (Type_D): if the document does not state "
        "(1) an exact Internal Carbon Price in USD/tCO2e (IFRS S2 para 29(f)) or "
        "(2) an exact percentage of Executive Remuneration tied to climate KPIs (para 29(g)), "
        "you MUST assign score 0, anomaly_detected=true, anomaly_type=Type_D, "
        "verbatim_evidence_quote=\"N/A\", cited_page_number=null for those trap rows "
        "(use indicator_id MET-2 for carbon price trap and GOV-1 for remuneration trap "
        "ONLY when assessing the trap — still also score the ordinary GOV-1/MET-2 rows separately "
        "in the main 15-indicator array). Put trap answers in a separate JSON array key "
        "\"type_d_traps\" with objects {trap_id, assigned_score, anomaly_detected, anomaly_type, "
        "verbatim_evidence_quote, cited_page_number, auditor_rationale} where trap_id is "
        "ICP_29f or REMUN_29g."
    )
    return f"""You are a junior sustainability assurer working under IAASB ISSA 5000 and IFRS S2.
Score the Nigerian upstream oil & gas disclosure for entity={entity}, version={version}.

Rubric: each indicator 0–3 where
0 = omitted; 1 = boilerplate/generic; 2 = entity-specific but incomplete; 3 = quantitative/investor-grade.

Score ALL of these indicators:
{indicator_lines}

Watch for planted anomalies:
- Type_A: quantitative metrics replaced by greenwashing boilerplate
- Type_B: internal numeric contradictions across pages
- Type_C: unit changes without rescaling, or JV/PSC boundary exclusions (e.g. 65% equity excluded)
- Type_D: requests for metrics that are absent (do not hallucinate)

{traps}

Return STRICT JSON only with this shape:
{{
  "evaluations": [
    {{
      "indicator_id": "GOV-1",
      "assigned_score": 0,
      "anomaly_detected": false,
      "anomaly_type": "None",
      "verbatim_evidence_quote": "N/A",
      "cited_page_number": null,
      "auditor_rationale": "..."
    }}
  ],
  "type_d_traps": []
}}
assigned_score must be integer 0,1,2, or 3. anomaly_type must be None|Type_A|Type_B|Type_C|Type_D.
Quotes must be exact substrings from the document when score>0.

DOCUMENT START
{doc_text}
DOCUMENT END
"""


def cost_usd(cfg: dict, in_tok: int, out_tok: int) -> float:
    return (in_tok / 1_000_000) * cfg["price_in_per_mtok"] + (out_tok / 1_000_000) * cfg["price_out_per_mtok"]


def dry_run() -> float:
    total = 0.0
    rows = []
    for cfg in TRACK_A + TRACK_B:
        for entity in ENTITIES:
            for version in VERSIONS:
                doc = load_document(entity, version, cfg["track"])
                prompt = build_prompt(entity, version, doc)
                in_tok = estimate_tokens(prompt)
                if in_tok + EST_OUT_TOKENS > cfg["context"]:
                    print(f"WARN {cfg['slug']} {entity}/{version}: ~{in_tok} tokens may exceed context {cfg['context']}")
                for k in range(1, cfg["k"] + 1):
                    c = cost_usd(cfg, in_tok, EST_OUT_TOKENS)
                    total += c
                    rows.append((cfg["slug"], entity, version, k, in_tok, c))
    print("=== DRY-RUN COST ESTIMATE ===")
    for r in rows:
        print(f"  {r[0]:22} {r[1]:7} {r[2]:10} run{r[3]} in~{r[4]:,} ${r[5]:.4f}")
    print(f"TOTAL ESTIMATE: ${total:.4f}  (hard cap ${HARD_CAP_USD:.2f})")
    return total


def call_model(client: OpenAI, cfg: dict, entity: str, version: str, run_k: int, ledger: dict) -> dict:
    out = log_path(cfg, entity, version, run_k)
    if out.exists():
        print(f"SKIP cached {out.name}")
        return json.loads(out.read_text(encoding="utf-8"))

    if ledger["spent_usd"] >= HARD_CAP_USD:
        raise RuntimeError(f"Hard spend cap ${HARD_CAP_USD} reached; refusing further calls")

    doc = load_document(entity, version, cfg["track"])
    prompt = build_prompt(entity, version, doc)
    in_tok_est = estimate_tokens(prompt)
    projected = ledger["spent_usd"] + cost_usd(cfg, in_tok_est, EST_OUT_TOKENS)
    if projected > HARD_CAP_USD:
        raise RuntimeError(
            f"Projected spend ${projected:.4f} would exceed cap ${HARD_CAP_USD}; stopping before {cfg['slug']} {entity}/{version}"
        )

    t0 = time.time()
    resp = client.chat.completions.create(
        model=cfg["model"],
        temperature=0.0,
        top_p=1.0,
        messages=[
            {"role": "system", "content": "You are a careful junior sustainability assurer. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or "{}"
    usage = getattr(resp, "usage", None)
    in_tok = getattr(usage, "prompt_tokens", None) or in_tok_est
    out_tok = getattr(usage, "completion_tokens", None) or estimate_tokens(content)
    spent = cost_usd(cfg, in_tok, out_tok)
    ledger["spent_usd"] += spent
    ledger["calls"].append(
        {
            "model": cfg["model"],
            "entity": entity,
            "version": version,
            "run": run_k,
            "prompt_tokens": in_tok,
            "completion_tokens": out_tok,
            "usd": spent,
            "elapsed_s": round(time.time() - t0, 2),
        }
    )
    save_spend(ledger)

    def _parse_json_content(text: str) -> dict:
        text = (text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("{"), text.rfind("}")
            if start >= 0 and end > start:
                return json.loads(text[start : end + 1])
            raise

    try:
        parsed = _parse_json_content(content)
    except Exception:
        parsed = {"raw_text": content, "parse_error": True}

    payload = {
        "model": cfg["model"],
        "slug": cfg["slug"],
        "track": cfg["track"],
        "entity_id": entity,
        "version": version,
        "run": run_k,
        "prompt_tokens": in_tok,
        "completion_tokens": out_tok,
        "usd": spent,
        "response": parsed,
    }
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"OK {cfg['slug']} {entity}/{version} run{run_k} ${spent:.4f} total=${ledger['spent_usd']:.4f}")
    return payload


def live_run() -> None:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise SystemExit("OPENROUTER_API_KEY missing in paper_b/.env")
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)
    ledger = load_spend()
    print(f"Starting live run; prior spend ${ledger['spent_usd']:.4f}")
    for cfg in TRACK_A + TRACK_B:
        for entity in ENTITIES:
            for version in VERSIONS:
                for k in range(1, cfg["k"] + 1):
                    try:
                        call_model(client, cfg, entity, version, k, ledger)
                    except Exception as exc:
                        print(f"STOP: {exc}")
                        save_spend(ledger)
                        return
    print(f"Complete. Total spend ${ledger['spent_usd']:.4f}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Execute billable OpenRouter calls")
    args = parser.parse_args()
    est = dry_run()
    if not args.live:
        print("Dry-run only. Re-run with --live to spend.")
        return
    if est > HARD_CAP_USD:
        raise SystemExit(f"Dry-run estimate ${est:.2f} exceeds hard cap ${HARD_CAP_USD}; aborting.")
    live_run()


if __name__ == "__main__":
    main()
