"""
Task 1: Map Ready for 2028? human readiness scores to a clean ground-truth benchmark.

Reads evaluations/master_score_matrix.csv (+ optional scorecard page notes)
and writes paper_b/data/human_benchmark_scores.{json,csv}.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "data" / "human_benchmark_scores.csv"
EVAL_DIR = ROOT / "data"
OUT_DIR = ROOT / "data"
ENTITIES = ["Seplat", "Oando", "Aradel"]
MAX_COMPOSITE = 45

INDICATORS = [
    ("GOV-1", "Governance", "Board Oversight"),
    ("GOV-2", "Governance", "Management Role"),
    ("STR-1", "Strategy", "Climate Risks & Opportunities"),
    ("STR-2", "Strategy", "Business Model & Value-Chain Impact"),
    ("STR-3", "Strategy", "Climate Scenario Analysis"),
    ("RM-1", "Risk Management", "ERM Integration"),
    ("RM-2", "Risk Management", "Operational Mitigation & Adaptation"),
    ("MET-1", "Metrics & Targets", "Scope 1, 2 & 3 GHG Inventory"),
    ("MET-2", "Metrics & Targets", "SASB Extractive Metrics (EM-EP/RM/SV)"),
    ("MET-3", "Metrics & Targets", "Decarbonisation Targets"),
    ("NUP-1", "NUPRC Methane Consistency", "Methane MRV & Env. Tracking"),
    ("NUP-2", "NUPRC Methane Consistency", "Flaring Commercialisation & Spills"),
    ("FIN-1", "Financial Connectivity", "IAS 36 & IAS 37 Connectivity"),
    ("ASR-1", "Assurance Readiness", "Sustainability Boundary Alignment"),
    ("ASR-2", "Assurance Readiness", "ICSR & ISSA 5000 Readiness"),
]

SCORECARD_FILES = {
    "Seplat": "Seplat.md",
    "Oando": "Oando.md",
    "Aradel": "Aradel.md",
}


def parse_scorecard_notes(path: Path) -> dict[str, str]:
    """Best-effort extract of page/evidence notes from readiness scorecard markdown tables."""
    if not path.exists():
        return {}
    notes: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = re.match(
            r"\|\s*(GOV-\d|STR-\d|RM-\d|MET-\d|NUP-\d|FIN-\d|ASR-\d)\s*\|\s*(\d)\s*\|\s*(.+?)\s*\|?\s*$",
            line,
        )
        if not m:
            continue
        ind, _score, evidence = m.group(1), m.group(2), m.group(3).strip()
        notes[ind] = evidence[:500]
    return notes


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(MATRIX)
    df = df[df["company"].isin(ENTITIES)].copy()
    if len(df) != len(ENTITIES):
        missing = set(ENTITIES) - set(df["company"])
        raise SystemExit(f"Missing entities in matrix: {missing}")

    rows = []
    checksums = {}
    for _, firm in df.iterrows():
        entity = firm["company"]
        notes = parse_scorecard_notes(EVAL_DIR / SCORECARD_FILES[entity])
        total = 0
        for ind_id, pillar, desc in INDICATORS:
            score = int(firm[ind_id])
            total += score
            rows.append(
                {
                    "entity_id": entity,
                    "indicator_id": ind_id,
                    "pillar": pillar,
                    "indicator_description": desc,
                    "human_score": score,
                    "human_notes_or_page": notes.get(ind_id, ""),
                    "tier": int(firm["tier"]),
                    "listing_venue": firm["listing_venue"],
                    "paper_a_composite": int(firm["composite"]),
                    "max_composite": MAX_COMPOSITE,
                }
            )
        expected = int(firm["composite"])
        checksums[entity] = {"sum_indicators": total, "matrix_composite": expected, "ok": total == expected}
        if total != expected:
            raise SystemExit(
                f"Checksum fail for {entity}: sum={total} vs composite={expected}"
            )

    out_df = pd.DataFrame(rows)
    csv_path = OUT_DIR / "human_benchmark_scores.csv"
    json_path = OUT_DIR / "human_benchmark_scores.json"
    out_df.to_csv(csv_path, index=False)
    payload = {
        "source_paper": "Davies (2026) Ready for 2028? Zenodo 10.5281/zenodo.23984011",
        "max_composite": MAX_COMPOSITE,
        "indicator_count": len(INDICATORS),
        "entities": ENTITIES,
        "checksums": checksums,
        "records": rows,
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("Wrote", csv_path)
    print("Wrote", json_path)
    print("Checksums:")
    for ent, c in checksums.items():
        print(f"  {ent}: {c['sum_indicators']}/{MAX_COMPOSITE} (matrix {c['matrix_composite']}) OK")
    print("Rows:", len(rows))


if __name__ == "__main__":
    main()
