"""CLI entry point."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from relaxdiff.config import DEFAULT
from relaxdiff.diagnose import run_diagnosis
from relaxdiff.geometry import compute_geometry_diff
from relaxdiff.io import load
from relaxdiff.matching import match_sites
from relaxdiff.narrative import generate_narrative
from relaxdiff.render import render_report
from relaxdiff.symmetry import compare_symmetry

app = typer.Typer(
    add_completion=False,
    help="Relax sanity checker — drop two structures, get a report.",
)


@app.command()
def diff(
    before: Path = typer.Argument(..., exists=True, help="Initial structure file."),
    after: Path = typer.Argument(..., exists=True, help="Final structure file."),
    output: Path = typer.Option(Path("report.html"), "-o", "--output", help="HTML report path."),
    title: Optional[str] = typer.Option(None, "--title", help="Report title."),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip Claude narrative."),
    json_out: Optional[Path] = typer.Option(None, "--json", help="Also dump structured diagnosis."),
    threshold_displacement: Optional[float] = typer.Option(
        None, "--threshold-displacement", help="Override warn threshold (Å)."
    ),
):
    """Generate an HTML diff report from two structure files."""
    thresholds = DEFAULT.thresholds
    if threshold_displacement is not None:
        thresholds.displacement_warn = threshold_displacement

    typer.echo(f"Loading {before} and {after}...")
    s_before = load(before)
    s_after = load(after)

    typer.echo("Matching sites...")
    mapping = match_sites(s_before, s_after)
    typer.echo(f"  method = {mapping.method}, RMSD = {mapping.rmsd:.4f} Å")

    typer.echo("Computing geometry diff...")
    geom = compute_geometry_diff(s_before, s_after, mapping)

    typer.echo("Comparing symmetry...")
    sym = compare_symmetry(s_before, mapping.aligned_after)

    typer.echo("Running diagnosis...")
    report = run_diagnosis(geom, sym, thresholds=thresholds)
    typer.echo(f"  overall severity: {report.overall_severity}")
    for f in report.findings:
        typer.echo(f"  [{f.severity}] {f.short}")

    typer.echo("Generating narrative...")
    narrative = generate_narrative(report, geom, sym, use_llm=not no_llm)

    report_title = title or f"RelaxDiff · {geom.formula}"
    typer.echo(f"Rendering report to {output}...")
    render_report(
        before=s_before,
        after=mapping.aligned_after,
        mapping=mapping,
        geometry=geom,
        symmetry=sym,
        diagnosis=report,
        narrative=narrative,
        title=report_title,
        output_path=output,
    )

    if json_out:
        payload = {
            "title": report_title,
            "diagnosis": report.to_dict(),
            "geometry": geom.to_dict(),
            "symmetry": {
                "before": sym.before.__dict__,
                "after": sym.after.__dict__,
                "direction": sym.direction,
                "tolerance_scan": sym.tolerance_scan,
            },
            "narrative": narrative,
        }
        json_out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        typer.echo(f"JSON diagnosis written to {json_out}")

    typer.echo("Done.")


if __name__ == "__main__":
    app()
