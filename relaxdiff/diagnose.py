"""Rule-based diagnosis — turn numeric diffs into severity-tagged findings."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from relaxdiff.config import DEFAULT, Thresholds
from relaxdiff.geometry import GeometryDiff
from relaxdiff.symmetry import SymmetryDiff

Severity = Literal["ok", "info", "warn", "alert"]


@dataclass
class Finding:
    rule: str
    severity: Severity
    short: str
    magnitude: float
    atoms_involved: list[int] = field(default_factory=list)
    detail: dict = field(default_factory=dict)


@dataclass
class DiagnosisReport:
    findings: list[Finding]
    overall_severity: Severity
    summary_stats: dict

    def to_dict(self) -> dict:
        return {
            "findings": [f.__dict__ for f in self.findings],
            "overall_severity": self.overall_severity,
            "summary_stats": self.summary_stats,
        }


_SEVERITY_ORDER = {"ok": 0, "info": 1, "warn": 2, "alert": 3}


def run_diagnosis(
    geom: GeometryDiff,
    sym: SymmetryDiff,
    thresholds: Thresholds | None = None,
) -> DiagnosisReport:
    t = thresholds or DEFAULT.thresholds
    findings: list[Finding] = []

    findings.extend(_check_displacement(geom, t))
    findings.extend(_check_cell(geom, t))
    findings.extend(_check_symmetry(sym))
    findings.extend(_check_bonds(geom))
    findings.extend(_check_coordination(geom))
    findings.extend(_check_shear(geom, t))

    if not findings:
        findings.append(Finding(
            rule="normal_relaxation",
            severity="ok",
            short="No notable structural changes detected.",
            magnitude=0.0,
        ))

    overall = max((f.severity for f in findings), key=lambda s: _SEVERITY_ORDER[s])

    summary_stats = {
        "max_displacement": geom.max_displacement,
        "rmsd": geom.rmsd,
        "volume_change_frac": geom.cell.volume_change_frac,
        "space_group_before": sym.before.space_group_number,
        "space_group_after": sym.after.space_group_number,
        "bonds_broken": sum(1 for b in geom.bond_changes if b.kind == "broken"),
        "bonds_formed": sum(1 for b in geom.bond_changes if b.kind == "formed"),
        "n_atoms_moved_over_0p5A": sum(
            1 for a in geom.per_atom if a.displacement > 0.5
        ),
    }

    return DiagnosisReport(
        findings=findings,
        overall_severity=overall,
        summary_stats=summary_stats,
    )


def _check_displacement(geom: GeometryDiff, t: Thresholds) -> list[Finding]:
    out: list[Finding] = []
    dists = np.array([a.displacement for a in geom.per_atom])
    if len(dists) == 0:
        return out
    mean, std = float(dists.mean()), float(dists.std() or 1e-9)

    max_d = geom.max_displacement
    max_idx = geom.max_displacement_index
    z = (max_d - mean) / std if std > 0 else 0.0

    if max_d >= t.displacement_alert and z >= t.runaway_zscore:
        out.append(Finding(
            rule="runaway_atom",
            severity="alert",
            short=f"Atom {max_idx} ({geom.per_atom[max_idx].element}) moved {max_d:.2f} Å — likely runaway.",
            magnitude=max_d,
            atoms_involved=[max_idx],
            detail={"z_score": z, "mean_displacement": mean},
        ))
    elif max_d >= t.displacement_warn:
        out.append(Finding(
            rule="large_displacement",
            severity="warn",
            short=f"Largest displacement: {max_d:.2f} Å on atom {max_idx} ({geom.per_atom[max_idx].element}).",
            magnitude=max_d,
            atoms_involved=[max_idx],
            detail={"z_score": z, "mean_displacement": mean},
        ))
    return out


def _check_cell(geom: GeometryDiff, t: Thresholds) -> list[Finding]:
    out: list[Finding] = []
    dv = geom.cell.volume_change_frac
    if dv <= -t.volume_alert:
        out.append(Finding(
            rule="cell_collapse",
            severity="alert",
            short=f"Cell volume collapsed by {abs(dv) * 100:.1f}%.",
            magnitude=dv,
            detail={"volume_before": geom.cell.volume_before, "volume_after": geom.cell.volume_after},
        ))
    elif dv >= t.volume_alert:
        out.append(Finding(
            rule="cell_expansion",
            severity="alert",
            short=f"Cell volume expanded by {dv * 100:.1f}%.",
            magnitude=dv,
            detail={"volume_before": geom.cell.volume_before, "volume_after": geom.cell.volume_after},
        ))
    elif abs(dv) >= t.volume_warn:
        sign = "expanded" if dv > 0 else "contracted"
        out.append(Finding(
            rule="cell_volume_change",
            severity="warn",
            short=f"Cell volume {sign} by {abs(dv) * 100:.1f}%.",
            magnitude=dv,
        ))
    return out


def _check_symmetry(sym: SymmetryDiff) -> list[Finding]:
    if not sym.space_group_changed:
        return []
    if sym.direction == "broken":
        return [Finding(
            rule="symmetry_broken",
            severity="warn",
            short=f"Symmetry broken: {sym.before.space_group_symbol} → {sym.after.space_group_symbol}.",
            magnitude=float(sym.before.space_group_number - sym.after.space_group_number),
            detail={
                "before": sym.before.__dict__,
                "after": sym.after.__dict__,
            },
        )]
    return [Finding(
        rule="symmetry_elevated",
        severity="info",
        short=f"Symmetry elevated: {sym.before.space_group_symbol} → {sym.after.space_group_symbol}.",
        magnitude=float(sym.after.space_group_number - sym.before.space_group_number),
        detail={
            "before": sym.before.__dict__,
            "after": sym.after.__dict__,
        },
    )]


def _check_bonds(geom: GeometryDiff) -> list[Finding]:
    out: list[Finding] = []
    broken = [b for b in geom.bond_changes if b.kind == "broken"]
    formed = [b for b in geom.bond_changes if b.kind == "formed"]
    if broken:
        out.append(Finding(
            rule="bond_breaking",
            severity="warn",
            short=f"{len(broken)} bond(s) broken.",
            magnitude=float(len(broken)),
            atoms_involved=sorted({b.i for b in broken} | {b.j for b in broken}),
            detail={"bonds": [b.__dict__ for b in broken[:10]]},
        ))
    if formed:
        out.append(Finding(
            rule="bond_forming",
            severity="warn",
            short=f"{len(formed)} new bond(s) formed.",
            magnitude=float(len(formed)),
            atoms_involved=sorted({b.i for b in formed} | {b.j for b in formed}),
            detail={"bonds": [b.__dict__ for b in formed[:10]]},
        ))
    return out


def _check_coordination(geom: GeometryDiff) -> list[Finding]:
    changed = [a for a in geom.per_atom if a.cn_change != 0]
    if not changed:
        return []
    return [Finding(
        rule="coordination_change",
        severity="warn",
        short=f"{len(changed)} atom(s) changed coordination number.",
        magnitude=float(len(changed)),
        atoms_involved=[a.index for a in changed],
        detail={"atoms": [a.__dict__ for a in changed[:10]]},
    )]


def _check_shear(geom: GeometryDiff, t: Thresholds) -> list[Finding]:
    strain = np.array(geom.strain)
    off_diag = strain - np.diag(np.diag(strain))
    max_shear = float(np.abs(off_diag).max())
    if max_shear < t.shear_warn:
        return []
    return [Finding(
        rule="large_shear",
        severity="warn",
        short=f"Large shear component in strain: {max_shear:.3f}.",
        magnitude=max_shear,
        detail={"strain": geom.strain},
    )]
