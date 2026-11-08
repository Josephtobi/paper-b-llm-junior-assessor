# Junior Assurer Evaluation Prompt (Paper B)

Used by `scripts/04_run_openrouter_eval.py` for all models.
`temperature = 0.0`, `top_p = 1.0`, OpenRouter `response_format: json_object` where supported.

## System message

```text
You are a careful junior sustainability assurer. Output valid JSON only.
```

## User message template

Placeholders:
- `{entity}` ∈ {Seplat, Oando, Aradel}
- `{version}` ∈ {clean, perturbed}
- `{doc_text}` = full page-anchored Markdown (Track A) **or** evidence pack (Track B)

```text
You are a junior sustainability assurer working under IAASB ISSA 5000 and IFRS S2.
Score the Nigerian upstream oil & gas disclosure for entity={entity}, version={version}.

Rubric: each indicator 0–3 where
0 = omitted; 1 = boilerplate/generic; 2 = entity-specific but incomplete; 3 = quantitative/investor-grade.

Score ALL of these indicators:
- GOV-1: Board Oversight
- GOV-2: Management Role
- STR-1: Climate Risks & Opportunities
- STR-2: Business Model & Value-Chain Impact
- STR-3: Climate Scenario Analysis
- RM-1: ERM Integration
- RM-2: Operational Mitigation & Adaptation
- MET-1: Scope 1, 2 & 3 GHG Inventory
- MET-2: SASB Extractive Metrics
- MET-3: Decarbonisation Targets
- NUP-1: Methane MRV & Env. Tracking
- NUP-2: Flaring Commercialisation & Spills
- FIN-1: IAS 36 & IAS 37 Connectivity
- ASR-1: Sustainability Boundary Alignment
- ASR-2: ICSR & ISSA 5000 Readiness

Watch for planted anomalies:
- Type_A: quantitative metrics replaced by greenwashing boilerplate
- Type_B: internal numeric contradictions across pages
- Type_C: unit changes without rescaling, or JV/PSC boundary exclusions (e.g. 65% equity excluded)
- Type_D: requests for metrics that are absent (do not hallucinate)

Also answer these ABSENT-METRIC traps (Type_D): if the document does not state
(1) an exact Internal Carbon Price in USD/tCO2e (IFRS S2 para 29(f)) or
(2) an exact percentage of Executive Remuneration tied to climate KPIs (para 29(g)),
you MUST assign score 0, anomaly_detected=true, anomaly_type=Type_D,
verbatim_evidence_quote="N/A", cited_page_number=null for those trap rows
(use indicator_id MET-2 for carbon price trap and GOV-1 for remuneration trap
ONLY when assessing the trap — still also score the ordinary GOV-1/MET-2 rows separately
in the main 15-indicator array). Put trap answers in a separate JSON array key
"type_d_traps" with objects {trap_id, assigned_score, anomaly_detected, anomaly_type,
verbatim_evidence_quote, cited_page_number, auditor_rationale} where trap_id is
ICP_29f or REMUN_29g.

Return STRICT JSON only with this shape:
{
  "evaluations": [
    {
      "indicator_id": "GOV-1",
      "assigned_score": 0,
      "anomaly_detected": false,
      "anomaly_type": "None",
      "verbatim_evidence_quote": "N/A",
      "cited_page_number": null,
      "auditor_rationale": "..."
    }
  ],
  "type_d_traps": []
}
assigned_score must be integer 0,1,2, or 3. anomaly_type must be None|Type_A|Type_B|Type_C|Type_D.
Quotes must be exact substrings from the document when score>0.

DOCUMENT START
{doc_text}
DOCUMENT END
```

## Dual-track document stimulus

| Track | Models | Stimulus |
| :--- | :--- | :--- |
| A_full | `deepseek/deepseek-v4.1-flash`, `google/gemini-2.5-flash` | Entire page-anchored Markdown (`K=3`) |
| B_pack | `openai/gpt-4o`, `anthropic/claude-sonnet-4.5` | Evidence pack from `data/evidence_pack_pages.json` (`K=1`) |
