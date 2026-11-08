# Paper B v1.3 — AI as a Junior Assessor (Replication Package)

Replication materials for the **v1.3** working paper:

> **AI as a Junior Assessor: Evaluating Large Language Models on IFRS S2 Climate Disclosures and Adversarial Error Detection in Nigerian Upstream Oil & Gas**

Human ground truth scores come from:

> Davies, J. (2026). *Ready for 2028? IFRS S1 and S2 Readiness of Nigeria's Listed and OTC Oil & Gas Public Interest Entities (v1.1)*. Zenodo. https://doi.org/10.5281/zenodo.23984011

**Release:** [`v1.3.0`](https://github.com/Josephtobi/paper-b-llm-junior-assessor/releases/tag/v1.3.0)  
**GitHub:** https://github.com/Josephtobi/paper-b-llm-junior-assessor

## What’s in this repo

| Path | Contents |
| :--- | :--- |
| [`prompts/junior_assurer_prompt.md`](prompts/junior_assurer_prompt.md) | Exact system + user prompts |
| [`rubric/ifrs_s2_15_indicator_rubric.md`](rubric/ifrs_s2_15_indicator_rubric.md) | 15-indicator 0–3 ordinal rubric (max 45) |
| [`data/human_benchmark_scores.csv`](data/human_benchmark_scores.csv) | Paper A human scores for Seplat, Oando, Aradel |
| [`data/evidence_pack_pages.json`](data/evidence_pack_pages.json) | Track B evidence-pack page lists |
| [`data/planted_errors_manifest.json`](data/planted_errors_manifest.json) | Adversarial Types A–D plant log |
| [`scripts/`](scripts/) | Pipeline `01`–`06` |
| [`results/raw_logs/`](results/raw_logs/) | All OpenRouter raw JSON responses (48 calls) |
| [`results/tables/`](results/tables/) | Publication tables (κ_w, α, detection, QVR) |
| [`results/spend_ledger.json`](results/spend_ledger.json) | Token/cost ledger (USD **3.62**) |
| [`.zenodo.json`](.zenodo.json) | Zenodo deposit metadata |

**Not included (size / rights):** full annual-report Markdown corpora and original PDFs. Reconstruct with `scripts/02_pdf_to_markdown.py` from public NGX/NASD filings listed in `data/pdf_manifest.json`.

## Dual-track design

- **Track A (full document, K=3):** `deepseek/deepseek-v4.1-flash`, `google/gemini-2.5-flash`  
  Seplat billed prompt tokens ≈ **368k** (DeepSeek) / **443k** (Gemini).  
  Oando = sustainability report (**90** pages) **+** financial statements (**113** pages).  
  Aradel = annual report only (**219** pages).
- **Track B (evidence pack, K=1):** `openai/gpt-4o`, `anthropic/claude-sonnet-4.5`  
  Pack prompt tokens ≈ **15k–24k**. Seplat pack is truncated at **90,000** characters (`[TRUNCATED FOR PACK BUDGET]`); pages **145–151** (incl. scenario analysis) drop after the cap.

## Metrics notes (as computed)

- Table 1 κ_w / MAE / bias = **mean of per-run statistics** (not a single pooled κ across all pairs). Recompute both with `scripts/06_scoring_deep_dive.py`.
- Table 3 detection = planted-error recall with a liberal type match (target indicator, else any evaluation row with the matching `anomaly_type`).
- Type D trap objects parsed: Claude 12, GPT-4o 12, Gemini 36, DeepSeek 30 (3 DeepSeek logs lacked usable evaluations).

## Quick start

```bash
pip install -r requirements.txt
python scripts/05_compute_metrics.py       # rebuild Tables 1–4 from raw_logs
python scripts/06_scoring_deep_dive.py     # kappa pooled vs mean-of-runs, tokens, pack truncation, Type D counts
# Optional re-score (costs money): put OPENROUTER_API_KEY in .env
python scripts/04_run_openrouter_eval.py   # dry-run estimate
```

## Citation

If you use these materials, please cite:

1. **This replication package (Paper B v1.3):**  
   Davies, J. (2026). *AI as a Junior Assessor: Evaluating Large Language Models on IFRS S2 Climate Disclosures and Adversarial Error Detection in Nigerian Upstream Oil & Gas* (Replication package v1.3.0) [Computer software]. GitHub. https://github.com/Josephtobi/paper-b-llm-junior-assessor/releases/tag/v1.3.0

2. **Paper A human benchmark (source of the ordinal scores):**  
   Davies, J. (2026). *Ready for 2028? IFRS S1 and S2 Readiness of Nigeria's Listed and OTC Oil & Gas Public Interest Entities* (Version v1.1). Zenodo. https://doi.org/10.5281/zenodo.23984011
