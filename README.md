# AI as a Junior Assessor — Replication Package (Paper B)

Replication materials for:

> **AI as a Junior Assessor: Evaluating Large Language Models on IFRS S2 Climate Disclosures and Adversarial Error Detection in Nigerian Upstream Oil & Gas**

Human ground truth scores come from:

> Davies, J. (2026). *Ready for 2028? IFRS S1 and S2 Readiness of Nigeria's Listed and OTC Oil & Gas Public Interest Entities (v1.1)*. Zenodo. https://doi.org/10.5281/zenodo.23984011

## What’s in this repo

| Path | Contents |
| :--- | :--- |
| [`prompts/junior_assurer_prompt.md`](prompts/junior_assurer_prompt.md) | Exact system + user prompts |
| [`rubric/ifrs_s2_15_indicator_rubric.md`](rubric/ifrs_s2_15_indicator_rubric.md) | 15-indicator 0–3 ordinal rubric (max 45) |
| [`data/human_benchmark_scores.csv`](data/human_benchmark_scores.csv) | Paper A human scores for Seplat, Oando, Aradel |
| [`data/evidence_pack_pages.json`](data/evidence_pack_pages.json) | Track B evidence-pack page lists |
| [`data/planted_errors_manifest.json`](data/planted_errors_manifest.json) | Adversarial Types A–D plant log |
| [`scripts/`](scripts/) | Pipeline `01`–`05` |
| [`results/raw_logs/`](results/raw_logs/) | All OpenRouter raw JSON responses (48 calls) |
| [`results/tables/`](results/tables/) | Publication tables (κ_w, α, detection, QVR) |
| [`results/spend_ledger.json`](results/spend_ledger.json) | Token/cost ledger (USD **3.62**) |

**Not included (size / rights):** full annual-report Markdown corpora and original PDFs. Reconstruct with `scripts/02_pdf_to_markdown.py` from public NGX/NASD filings listed in `data/pdf_manifest.json`.

## Dual-track design

- **Track A (full document, K=3):** `deepseek/deepseek-v4.1-flash`, `google/gemini-2.5-flash`  
  Seplat billed prompt tokens ≈ **368k** (DeepSeek) / **443k** (Gemini).
- **Track B (evidence pack, K=1):** `openai/gpt-4o`, `anthropic/claude-sonnet-4.5`  
  Pack prompt tokens ≈ **15k–24k**.

## Metrics notes (as computed)

- Table 1 κ_w / MAE / bias = **mean of per-run statistics** (not a single pooled κ across all pairs).
- Table 3 detection = planted-error recall with a liberal type match (target indicator, else any evaluation row with the matching `anomaly_type`).
- Type D trap objects parsed: Claude 12, GPT-4o 12, Gemini 36, DeepSeek 30 (3 DeepSeek logs lacked usable evaluations).

## Quick start

```bash
pip install -r requirements.txt
# Optional re-score (costs money): put OPENROUTER_API_KEY in .env
python scripts/04_run_openrouter_eval.py          # dry-run
python scripts/05_compute_metrics.py              # rebuild tables from raw_logs
```

## Citation

Please cite both Paper B (this study) and the Zenodo Paper A benchmark above when using these scores or logs.
