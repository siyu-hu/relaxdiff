"""HTML report renderer — Jinja2 + inline 3Dmol.js."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pymatgen.core import Structure

from relaxdiff.diagnose import DiagnosisReport
from relaxdiff.geometry import GeometryDiff
from relaxdiff.io import to_cif_string
from relaxdiff.matching import SiteMapping
from relaxdiff.symmetry import SymmetryDiff, symmetry_diff_to_dict


THREEDMOL_CDN = "https://3Dmol.org/build/3Dmol-min.js"


def render_report(
    before: Structure,
    after: Structure,
    mapping: SiteMapping,
    geometry: GeometryDiff,
    symmetry: SymmetryDiff,
    diagnosis: DiagnosisReport,
    narrative: str,
    title: str = "RelaxDiff report",
    output_path: str | Path | None = None,
    embed_3dmol: bool = True,
) -> str:
    """Render a self-contained HTML report. Returns the HTML string and optionally writes it."""
    template_dir = Path(__file__).parent / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("report.html.j2")

    # Build the data payload for the in-page JS
    displacements_payload = [
        {
            "index": a.index,
            "element": a.element,
            "displacement": a.displacement,
            "vec": a.displacement_vec,
            "cn_before": a.cn_before,
            "cn_after": a.cn_after,
        }
        for a in geometry.per_atom
    ]

    before_cif = to_cif_string(before)
    after_cif = to_cif_string(mapping.aligned_after)

    payload = {
        "title": title,
        "narrative_html": _markdown_to_html(narrative),
        "diagnosis": diagnosis.to_dict(),
        "geometry": geometry.to_dict(),
        "symmetry": symmetry_diff_to_dict(symmetry),
        "before_cif": before_cif,
        "after_cif": after_cif,
        "displacements": displacements_payload,
        "max_displacement": geometry.max_displacement,
        "severity_overall": diagnosis.overall_severity,
        "viewer_lib": "embedded" if embed_3dmol else "cdn",
        "threedmol_url": THREEDMOL_CDN,
    }

    html = template.render(
        payload_json=json.dumps(payload),
        payload=payload,
    )

    if output_path is not None:
        Path(output_path).write_text(html, encoding="utf-8")
    return html


def _markdown_to_html(md: str) -> str:
    """Minimal markdown -> HTML. Paragraphs only; we don't need full markdown."""
    paragraphs = [p.strip() for p in md.strip().split("\n\n") if p.strip()]
    out = []
    for p in paragraphs:
        if p.startswith("  - ") or p.startswith("- "):
            items = [line.strip("- ").strip() for line in p.split("\n") if line.strip()]
            out.append("<ul>" + "".join(f"<li>{_escape(i)}</li>" for i in items) + "</ul>")
        else:
            out.append(f"<p>{_escape(p)}</p>")
    return "\n".join(out)


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
