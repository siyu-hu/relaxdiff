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
    """Deterministic narrative so the pipeline always produces output."""
    sev = diagnosis.overall_severity
    formula = geometry.formula
    n = geometry.n_atoms
    dv = geometry.cell.volume_change_frac * 100
    sg_b = symmetry.before.space_group_symbol
    sg_a = symmetry.after.space_group_symbol

    verdict = {
        "ok": "This relaxation looks clean.",
        "info": "This relaxation completed with minor changes.",
        "warn": "This relaxation has notable changes worth reviewing.",
        "alert": "This relaxation looks broken and needs manual review.",
    }[sev]

    lines = [
        f"{verdict} The structure is {formula} with {n} atoms.",
        "",
        f"Maximum atomic displacement was {geometry.max_displacement:.2f} Å "
        f"(RMSD {geometry.rmsd:.3f} Å). Cell volume changed by {dv:+.1f}%. "
        f"Space group {sg_b} → {sg_a}.",
    ]

    notable = [f for f in diagnosis.findings if f.severity in {"warn", "alert"}]
    if notable:
        lines.append("")
        lines.append("Notable findings:")
        for f in notable:
            lines.append(f"  - [{f.severity.upper()}] {f.short}")

    if error:
        lines.append("")
        lines.append(f"(LLM narrative unavailable: {error})")

    return "\n".join(lines)


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / name).read_text(encoding="utf-8")


def _load_examples() -> list[dict]:
    raw = (_PROMPTS_DIR / "examples.json").read_text(encoding="utf-8")
    return json.loads(raw)
