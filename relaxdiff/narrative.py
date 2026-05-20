"""LLM narrative — feed structured diagnosis JSON to Claude, get prose explanation."""

from __future__ import annotations

import json
import os
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent / "prompts"

from relaxdiff.config import DEFAULT, LLMConfig
from relaxdiff.diagnose import DiagnosisReport
from relaxdiff.geometry import GeometryDiff
from relaxdiff.symmetry import SymmetryDiff


def generate_narrative(
    diagnosis: DiagnosisReport,
    geometry: GeometryDiff,
    symmetry: SymmetryDiff,
    config: LLMConfig | None = None,
    use_llm: bool = True,
) -> str:
    """Return a markdown narrative. Falls back to template if LLM unavailable."""
    config = config or DEFAULT.llm

    if not use_llm or not config.enabled or not os.environ.get("ANTHROPIC_API_KEY"):
        return _fallback_template(diagnosis, geometry, symmetry)

    try:
        return _call_claude(diagnosis, geometry, symmetry, config)
    except Exception as e:
        return _fallback_template(diagnosis, geometry, symmetry, error=str(e))


def _call_claude(
    diagnosis: DiagnosisReport,
    geometry: GeometryDiff,
    symmetry: SymmetryDiff,
    config: LLMConfig,
) -> str:
    import anthropic

    system_prompt = _load_prompt("system.md")
    examples = _load_examples()

    user_payload = {
        "formula": geometry.formula,
        "n_atoms": geometry.n_atoms,
        "overall_severity": diagnosis.overall_severity,
        "summary_stats": diagnosis.summary_stats,
        "findings": [
            {
                "rule": f.rule,
                "severity": f.severity,
                "short": f.short,
                "magnitude": f.magnitude,
                "atoms_involved": f.atoms_involved[:8],
            }
            for f in diagnosis.findings
        ],
        "cell": geometry.cell.__dict__,
        "symmetry": {
            "before": symmetry.before.__dict__,
            "after": symmetry.after.__dict__,
            "direction": symmetry.direction,
        },
        "top_displacements": sorted(
            [a.__dict__ for a in geometry.per_atom],
            key=lambda a: a["displacement"],
            reverse=True,
        )[:8],
    }

    messages = []
    for ex in examples:
        messages.append({
            "role": "user",
            "content": json.dumps(ex["input_summary"], indent=2),
        })
        messages.append({"role": "assistant", "content": ex["output"]})
    messages.append({"role": "user", "content": json.dumps(user_payload, indent=2)})

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=config.model,
        max_tokens=config.max_tokens,
        system=[
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=messages,
    )
    return response.content[0].text.strip()


def _fallback_template(
    diagnosis: DiagnosisReport,
    geometry: GeometryDiff,
    symmetry: SymmetryDiff,
    error: str | None = None,
) -> str:
    """Deterministic narrative so the pipeline always produces output.

    Three short paragraphs, modelled on the prompt the LLM would have followed:
    verdict, specific evidence, and a suggested next step.
    """
    sev = diagnosis.overall_severity
    formula = geometry.formula
    n = geometry.n_atoms
    dv_pct = geometry.cell.volume_change_frac * 100
    rmsd = geometry.rmsd
    max_d = geometry.max_displacement
    max_idx = geometry.max_displacement_index
    max_elem = geometry.per_atom[max_idx].element if geometry.per_atom else "?"
    sg_b = symmetry.before.space_group_symbol
    sg_a = symmetry.after.space_group_symbol
    sg_changed = symmetry.space_group_changed
    bonds_broken = diagnosis.summary_stats.get("bonds_broken", 0)
    bonds_formed = diagnosis.summary_stats.get("bonds_formed", 0)

    verdict = {
        "ok": f"This relaxation of {formula} looks clean.",
        "info": f"This relaxation of {formula} completed with only minor changes.",
        "warn": f"This relaxation of {formula} has notable changes worth a closer look.",
        "alert": f"This relaxation of {formula} looks broken and needs manual review before being trusted.",
    }[sev]

    # Paragraph 1: verdict + headline numbers
    headline_bits = []
    if max_d > 0.05:
        headline_bits.append(f"the largest atomic displacement is {max_d:.2f} Å "
                             f"(atom {max_idx}, {max_elem})")
    if abs(dv_pct) > 0.5:
        sign = "+" if dv_pct > 0 else ""
        headline_bits.append(f"cell volume changed by {sign}{dv_pct:.1f}%")
    if sg_changed:
        headline_bits.append(f"space group went from {sg_b} to {sg_a}")
    headline = "; ".join(headline_bits) if headline_bits else (
        "atoms barely moved and the cell stayed put"
    )
    para1 = f"{verdict} Overall RMSD is {rmsd:.3f} Å across {n} atoms — {headline}."

    # Paragraph 2: specific evidence from the top findings
    notable = [f for f in diagnosis.findings if f.severity in {"warn", "alert"}]
    if notable:
        evidence_parts = []
        for f in notable[:4]:
            evidence_parts.append(f.short.rstrip("."))
        if bonds_broken or bonds_formed:
            bond_part = []
            if bonds_broken:
                bond_part.append(f"{bonds_broken} bond(s) broken")
            if bonds_formed:
                bond_part.append(f"{bonds_formed} new bond(s) formed")
            evidence_parts.append(" and ".join(bond_part))
        para2 = "Specifically: " + "; ".join(evidence_parts) + "."
    else:
        para2 = (
            "No notable findings tripped any of the diagnostic rules. "
            f"Maximum displacement {max_d:.2f} Å stayed below the warn "
            f"threshold and no bonds were broken or formed."
        )

    # Paragraph 3: interpretation hint
    if sev == "alert":
        para3 = (
            "This pattern is consistent with either a poor initial guess "
            "(misplaced atoms, wrong lattice scaling) or the optimizer "
            "crossing a barrier into a different basin. Re-check the input "
            "geometry and optimizer settings before drawing physical conclusions."
        )
    elif sev == "warn":
        if sg_changed:
            para3 = (
                "The symmetry change is the most informative signal here — "
                "worth checking whether it reflects a real distortion (e.g. "
                "Jahn-Teller, octahedral tilt, phase transition) or is an "
                "artifact of the starting configuration."
            )
        elif bonds_broken or bonds_formed:
            para3 = (
                "Bond topology changed during the optimization, which is unusual "
                "for a routine ionic relaxation. Inspect the listed atoms to "
                "decide whether this represents a real reconstruction."
            )
        else:
            para3 = (
                "Changes are localized rather than catastrophic. A spot check "
                "of the listed atoms is probably enough to clear this one."
            )
    elif sev == "info":
        para3 = "Nothing here suggests an optimization problem."
    else:
        para3 = (
            "Looks like a textbook ionic relaxation around an already-good "
            "starting structure. No manual review needed."
        )

    paragraphs = [para1, para2, para3]
    if error:
        paragraphs.append(f"(LLM narrative unavailable: {error})")
    return "\n\n".join(paragraphs)


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_examples() -> list[dict]:
    raw = (_PROMPTS_DIR / "examples.json").read_text(encoding="utf-8")
    return json.loads(raw)
