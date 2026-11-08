"""
Paper B Task 3: Seed 6–8 material misstatements per Tier-1 report (Types A–C in
Markdown; Type D logged as evaluation traps for absent IFRS S2 metrics).
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path

PAPER_B = Path(__file__).resolve().parents[1]
CLEAN = PAPER_B / "data" / "clean_markdown"
OUT = PAPER_B / "data" / "perturbed_markdown"
MANIFEST = PAPER_B / "data" / "planted_errors_manifest.json"

TYPE_D_TRAPS = [
    {
        "error_type": "Type_D",
        "target_indicator_id": "MET-2",
        "trap_metric": "Internal Carbon Price (USD/tCO2e) under IFRS S2 para 29(f)",
        "expected_auditor_action": "Assign score 0; verbatim_evidence_quote=N/A; do not invent a page citation.",
        "page_number": None,
        "original_text": "",
        "modified_text": "",
    },
    {
        "error_type": "Type_D",
        "target_indicator_id": "GOV-1",
        "trap_metric": "Exact % of Executive Remuneration tied to climate KPIs under IFRS S2 para 29(g)",
        "expected_auditor_action": "Assign score 0; verbatim_evidence_quote=N/A; abstain from fabricating a percentage.",
        "page_number": None,
        "original_text": "",
        "modified_text": "",
    },
]


def page_near(text: str, idx: int) -> str | int | None:
    prefix = text[:idx]
    matches = list(re.finditer(r"--- ([^\n]+?) ---", prefix))
    if not matches:
        return None
    label = matches[-1].group(1).strip()
    m = re.search(r"(\d+)$", label)
    return int(m.group(1)) if m else label


def apply_replace(
    text: str,
    original: str,
    modified: str,
    *,
    entity_id: str,
    error_id: str,
    error_type: str,
    target_indicator_id: str,
    expected_auditor_action: str,
) -> tuple[str, dict]:
    if original not in text:
        raise ValueError(f"{entity_id}/{error_id}: original snippet not found")
    idx = text.find(original)
    entry = {
        "entity_id": entity_id,
        "error_id": error_id,
        "error_type": error_type,
        "target_indicator_id": target_indicator_id,
        "page_number": page_near(text, idx),
        "original_text": original,
        "modified_text": modified,
        "expected_auditor_action": expected_auditor_action,
    }
    return text.replace(original, modified, 1), entry


def seed_seplat(text: str) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    # Type A: replace quantitative Scope 1/2 sentence with greenwashing boilerplate
    orig_a = (
        "For 2025, our gross Scope 1 and Scope 2 emissions across our onshore "
        "operated assets was 899.7 ktCO2e, 37% lower than our 2020 \n"
        "baseline figure of 1,423.0 ktCO2e."
    )
    mod_a = (
        "For 2025, the Group affirms 100% alignment with PIA 2021 zero-routine-flaring "
        "mandates and the Paris Agreement through continuous environmental stewardship, "
        "without separately quantifying Scope 1 and Scope 2 inventory totals in this section."
    )
    text, e = apply_replace(
        text,
        orig_a,
        mod_a,
        entity_id="Seplat",
        error_id="SEPLAT_A1",
        error_type="Type_A",
        target_indicator_id="MET-1",
        expected_auditor_action="Downgrade MET-1 toward boilerplate (≤1) and flag Type_A omission/greenwashing substitution.",
    )
    errors.append(e)

    # Type B: keep early narrative 24.3 intensity; multiply a later table figure 10x
    # Find a later occurrence of 24.3 that is not the page-5 headline if possible.
    needle_b = "24.3 kg/CO2"
    positions = [m.start() for m in re.finditer(re.escape(needle_b), text)]
    if len(positions) < 2:
        raise ValueError("Seplat: need ≥2 occurrences of 24.3 kg/CO2 for Type B")
    # Perturb a mid/late occurrence (skip first headline)
    idx = positions[1]
    orig_b = text[idx : idx + len(needle_b)]
    mod_b = "243.0 kg/CO2"
    text = text[:idx] + mod_b + text[idx + len(needle_b) :]
    errors.append(
        {
            "entity_id": "Seplat",
            "error_id": "SEPLAT_B1",
            "error_type": "Type_B",
            "target_indicator_id": "MET-1",
            "page_number": page_near(text, idx),
            "original_text": orig_b,
            "modified_text": mod_b,
            "expected_auditor_action": "Detect contradiction vs earlier 24.3 intensity narrative; flag Type_B.",
        }
    )

    # Type B2: multiply 899.7 residual mention if still present elsewhere, else flare %
    # Use EORF quantitative claim alteration in performance section while leaving another intact.
    orig_b2 = "899.7 ktCO2e"
    if orig_b2 in text:
        text, e = apply_replace(
            text,
            orig_b2,
            "8,997 ktCO2e",
            entity_id="Seplat",
            error_id="SEPLAT_B2",
            error_type="Type_B",
            target_indicator_id="MET-1",
            expected_auditor_action="Flag 10x emissions contradiction vs any remaining baseline/narrative figures; Type_B.",
        )
        errors.append(e)
    else:
        # Fallback: inflate onshore flare elimination % in a dense metrics block
        orig_b2 = "86% \nFlaring \neliminated \nonshore"
        text, e = apply_replace(
            text,
            orig_b2,
            "8.6% \nFlaring \neliminated \nonshore",
            entity_id="Seplat",
            error_id="SEPLAT_B2",
            error_type="Type_B",
            target_indicator_id="NUP-2",
            expected_auditor_action="Flag contradiction vs EORF/zero-routine-flaring narrative elsewhere; Type_B.",
        )
        errors.append(e)

    # Type C: unit manipulation without rescaling (table header is line-broken in extract)
    orig_c = "Gross Scope 1 \nemissions \nreduction \n(ktCO2e)"
    mod_c = "Gross Scope 1 \nemissions \nreduction \n(tCO2e)"
    if orig_c not in text:
        # Fallback: any remaining baseline unit after Type A may still exist elsewhere
        orig_c = "1,423.0 ktCO2e"
        mod_c = "1,423.0 tCO2e"
    text, e = apply_replace(
        text,
        orig_c,
        mod_c,
        entity_id="Seplat",
        error_id="SEPLAT_C1",
        error_type="Type_C",
        target_indicator_id="MET-1",
        expected_auditor_action="Flag unit distortion (ktCO2e→tCO2e without rescaling); Type_C.",
    )
    errors.append(e)

    # Type C2: JV boundary footnote insertion after first emissions intensity block
    insert_at = text.find("Carbon emissions intensity onshore")
    if insert_at < 0:
        raise ValueError("Seplat Type C2 anchor missing")
    footnote = (
        "\n\n[PLANTED FOOTNOTE — Type_C] Non-operated Joint Venture (JV) assets representing "
        "65% of equity production were excluded from the Group's \"100% Corporate Net-Zero\" "
        "boundary used in this report.\n\n"
    )
    text = text[:insert_at] + footnote + text[insert_at:]
    errors.append(
        {
            "entity_id": "Seplat",
            "error_id": "SEPLAT_C2",
            "error_type": "Type_C",
            "target_indicator_id": "ASR-1",
            "page_number": page_near(text, insert_at),
            "original_text": "",
            "modified_text": footnote.strip(),
            "expected_auditor_action": "Flag boundary manipulation excluding 65% JV equity production; Type_C.",
        }
    )
    return text, errors


def seed_oando(text: str) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    # Type A: replace IT carbon footprint quantitative range with boilerplate
    orig_a = "approximately 400–550 tCO2e"
    mod_a = (
        "full qualitative alignment with PIA 2021 zero-routine-flaring mandates and the Paris "
        "Agreement across IT and operations (no discrete tCO2e inventory disclosed here)"
    )
    text, e = apply_replace(
        text,
        orig_a,
        mod_a,
        entity_id="Oando",
        error_id="OANDO_A1",
        error_type="Type_A",
        target_indicator_id="MET-1",
        expected_auditor_action="Downgrade quantitative MET evidence and flag Type_A greenwashing substitution.",
    )
    errors.append(e)

    # Type B: inflate emissions reduction headline while leaving other narrative intact
    orig_b = "+3.96%"
    text, e = apply_replace(
        text,
        orig_b,
        "+39.6%",
        entity_id="Oando",
        error_id="OANDO_B1",
        error_type="Type_B",
        target_indicator_id="MET-3",
        expected_auditor_action="Detect 10x contradiction vs remaining emissions narrative; flag Type_B.",
    )
    errors.append(e)

    # Type B2: multiply a remaining tCO2e figure if present
    for cand, mult_label, new in [
        ("150– 200 tCO2e", "10x", "1,500– 2,000 tCO2e"),
        ("150–200 tCO2e", "10x", "1,500–2,000 tCO2e"),
        ("30–60 tCO2e", "10x", "300–600 tCO2e"),
    ]:
        if cand in text:
            text, e = apply_replace(
                text,
                cand,
                new,
                entity_id="Oando",
                error_id="OANDO_B2",
                error_type="Type_B",
                target_indicator_id="MET-1",
                expected_auditor_action=f"Flag {mult_label} numeric contradiction across IT carbon notes; Type_B.",
            )
            errors.append(e)
            break
    else:
        # Use spill recovery narrative nearby if numbers differ
        m = re.search(r"recovery rate to (\d+)%", text, re.I)
        if not m:
            raise ValueError("Oando Type B2 target missing")
        orig = m.group(0)
        mod = orig.replace(m.group(1), str(int(m.group(1)) * 4))
        text, e = apply_replace(
            text,
            orig,
            mod,
            entity_id="Oando",
            error_id="OANDO_B2",
            error_type="Type_B",
            target_indicator_id="NUP-2",
            expected_auditor_action="Flag 4x spill-recovery contradiction vs other HSE claims; Type_B.",
        )
        errors.append(e)

    # Type C: unit swap without scaling
    if "tCO2e" in text:
        # Change a unit label near IT footprint discussion
        orig_c = "device-count-based estimation methods"
        # Prefer changing unit in a nearby remaining tCO2e token
        idx = text.find("tCO2e")
        if idx < 0:
            raise ValueError("Oando Type C unit token missing")
        # replace first remaining tCO2e with ktCO2e (no rescale)
        text = text[:idx] + "ktCO2e" + text[idx + len("tCO2e") :]
        errors.append(
            {
                "entity_id": "Oando",
                "error_id": "OANDO_C1",
                "error_type": "Type_C",
                "target_indicator_id": "MET-1",
                "page_number": page_near(text, idx),
                "original_text": "tCO2e",
                "modified_text": "ktCO2e",
                "expected_auditor_action": "Flag unit distortion tCO2e→ktCO2e without rescaling; Type_C.",
            }
        )
    else:
        raise ValueError("Oando: no tCO2e left for Type C")

    # Type C2: JV boundary footnote
    insert_at = text.lower().find("greenhouse gas emission")
    if insert_at < 0:
        insert_at = text.lower().find("scope 1")
    if insert_at < 0:
        raise ValueError("Oando Type C2 anchor missing")
    footnote = (
        "\n\n[PLANTED FOOTNOTE — Type_C] Non-operated Joint Venture (JV) assets representing "
        "65% of equity production were excluded from the \"100% Corporate Net-Zero\" reporting boundary.\n\n"
    )
    text = text[:insert_at] + footnote + text[insert_at:]
    errors.append(
        {
            "entity_id": "Oando",
            "error_id": "OANDO_C2",
            "error_type": "Type_C",
            "target_indicator_id": "ASR-1",
            "page_number": page_near(text, insert_at),
            "original_text": "",
            "modified_text": footnote.strip(),
            "expected_auditor_action": "Flag JV/PSC boundary exclusion of 65% equity production; Type_C.",
        }
    )
    return text, errors


def seed_aradel(text: str) -> tuple[str, list[dict]]:
    errors: list[dict] = []
    # Type A: replace zero hydrocarbon spills claim with boilerplate
    orig_a = "Zero work-related fatalities; zero hydrocarbon spills to \nland or water"
    mod_a = (
        "The Company remains fully aligned with PIA 2021 zero-routine-flaring mandates and the "
        "Paris Agreement through ongoing HSE excellence (qualitative affirmation only in this extract)."
    )
    text, e = apply_replace(
        text,
        orig_a,
        mod_a,
        entity_id="Aradel",
        error_id="ARADEL_A1",
        error_type="Type_A",
        target_indicator_id="NUP-2",
        expected_auditor_action="Downgrade quantitative HSE/spill evidence and flag Type_A substitution.",
    )
    errors.append(e)

    # Type B: contradict routine flare narrative — leave 'eliminating routine flaring' intact,
    # but change Ogbele routine-flare cell / related figure.
    orig_b = "0 Fire / 0 Routine Flare in Ogbele/"
    mod_b = "0 Fire / 40 Routine Flare in Ogbele/"
    text, e = apply_replace(
        text,
        orig_b,
        mod_b,
        entity_id="Aradel",
        error_id="ARADEL_B1",
        error_type="Type_B",
        target_indicator_id="RM-2",
        expected_auditor_action="Detect contradiction vs eliminating-routine-flaring narrative; flag Type_B.",
    )
    errors.append(e)

    # Type B2: inflate UA/UC counts nearby if present
    orig_b2 = "7,156/7,745"
    if orig_b2 in text:
        text, e = apply_replace(
            text,
            orig_b2,
            "71,560/77,450",
            entity_id="Aradel",
            error_id="ARADEL_B2",
            error_type="Type_B",
            target_indicator_id="RM-2",
            expected_auditor_action="Flag 10x HSE/UA-UC table contradiction; Type_B.",
        )
        errors.append(e)
    else:
        raise ValueError("Aradel Type B2 missing")

    # Type C: insert JV boundary footnote near flaring commitment
    insert_at = text.find("eliminating routine flaring")
    if insert_at < 0:
        raise ValueError("Aradel Type C anchor missing")
    footnote = (
        "\n\n[PLANTED FOOTNOTE — Type_C] Non-operated Joint Venture (JV) assets representing "
        "65% of equity production were excluded from the \"100% Corporate Net-Zero\" boundary.\n\n"
    )
    text = text[:insert_at] + footnote + text[insert_at:]
    errors.append(
        {
            "entity_id": "Aradel",
            "error_id": "ARADEL_C1",
            "error_type": "Type_C",
            "target_indicator_id": "ASR-1",
            "page_number": page_near(text, insert_at),
            "original_text": "",
            "modified_text": footnote.strip(),
            "expected_auditor_action": "Flag boundary manipulation excluding 65% JV equity; Type_C.",
        }
    )

    # Type C2: unit-like distortion — change 'Oil Spill' header context count 0 to unit confusion
    # Insert a fake unit note on flare counts
    orig_c2 = "Flaring in Omerelu"
    mod_c2 = "Flaring in Omerelu (figures stated in kt without rescaling from historical t units)"
    text, e = apply_replace(
        text,
        orig_c2,
        mod_c2,
        entity_id="Aradel",
        error_id="ARADEL_C2",
        error_type="Type_C",
        target_indicator_id="MET-2",
        expected_auditor_action="Flag unit/scale ambiguity without reconciliation; Type_C.",
    )
    errors.append(e)
    return text, errors


SEEDERS = {
    "Seplat": seed_seplat,
    "Oando": seed_oando,
    "Aradel": seed_aradel,
}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    all_errors: list[dict] = []

    for entity, seeder in SEEDERS.items():
        src = CLEAN / f"{entity}.md"
        if not src.exists():
            raise SystemExit(f"Missing clean markdown: {src}")
        clean = src.read_text(encoding="utf-8")
        perturbed, errors = seeder(clean)
        for i, trap in enumerate(TYPE_D_TRAPS, start=1):
            d = deepcopy(trap)
            d["entity_id"] = entity
            d["error_id"] = f"{entity.upper()}_D{i}"
            errors.append(d)
        if not (6 <= len(errors) <= 8):
            raise SystemExit(f"{entity}: expected 6–8 errors, got {len(errors)}")
        out_path = OUT / f"{entity}.md"
        out_path.write_text(perturbed, encoding="utf-8")
        all_errors.extend(errors)
        print(f"{entity}: wrote {out_path.name}; planted {len(errors)} errors")
        for e in errors:
            print(f"  {e['error_id']} {e['error_type']} → {e['target_indicator_id']} p={e.get('page_number')}")

    payload = {
        "description": "Planted ISSA 5000 adversarial misstatements for Paper B Track A/B evaluation",
        "entities": list(SEEDERS),
        "error_count": len(all_errors),
        "errors": all_errors,
    }
    MANIFEST.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print("Wrote", MANIFEST, "total errors", len(all_errors))


if __name__ == "__main__":
    main()
