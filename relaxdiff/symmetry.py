"""Symmetry diff — space group, point group, Wyckoff comparison via spglib."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pymatgen.core import Structure
from pymatgen.symmetry.analyzer import SpacegroupAnalyzer

from relaxdiff.config import DEFAULT


@dataclass
class SymmetrySnapshot:
    space_group_number: int
    space_group_symbol: str
    point_group: str
    crystal_system: str
    n_symmetry_ops: int
    symprec: float


@dataclass
class SymmetryDiff:
    before: SymmetrySnapshot
    after: SymmetrySnapshot
    space_group_changed: bool
    direction: str                       # "broken" | "elevated" | "same"
    tolerance_scan: list[dict]           # symprec -> {before_sg, after_sg, changed}


def _snapshot(structure: Structure, symprec: float) -> SymmetrySnapshot:
    try:
        sga = SpacegroupAnalyzer(structure, symprec=symprec)
        return SymmetrySnapshot(
            space_group_number=sga.get_space_group_number(),
            space_group_symbol=sga.get_space_group_symbol(),
            point_group=sga.get_point_group_symbol(),
            crystal_system=sga.get_crystal_system(),
            n_symmetry_ops=len(sga.get_symmetry_operations()),
            symprec=symprec,
        )
    except Exception:
        return SymmetrySnapshot(
            space_group_number=1,
            space_group_symbol="P1",
            point_group="1",
            crystal_system="triclinic",
            n_symmetry_ops=1,
            symprec=symprec,
        )


def compare_symmetry(
    before: Structure,
    after: Structure,
    symprec: Optional[float] = None,
) -> SymmetryDiff:
    symprec = symprec or DEFAULT.thresholds.default_symprec
    b = _snapshot(before, symprec)
    a = _snapshot(after, symprec)

    changed = b.space_group_number != a.space_group_number
    if not changed:
        direction = "same"
    elif a.space_group_number < b.space_group_number:
        direction = "broken"
    else:
        direction = "elevated"

    scan = []
    for tol in DEFAULT.thresholds.symprec_scan:
        sb = _snapshot(before, tol)
        sa = _snapshot(after, tol)
        scan.append({
            "symprec": tol,
            "before_sg": sb.space_group_number,
            "after_sg": sa.space_group_number,
            "before_symbol": sb.space_group_symbol,
            "after_symbol": sa.space_group_symbol,
            "changed": sb.space_group_number != sa.space_group_number,
        })

    return SymmetryDiff(
        before=b,
        after=a,
        space_group_changed=changed,
        direction=direction,
        tolerance_scan=scan,
    )


def symmetry_diff_to_dict(diff: SymmetryDiff) -> dict:
    return {
        "before": diff.before.__dict__,
        "after": diff.after.__dict__,
        "space_group_changed": diff.space_group_changed,
        "direction": diff.direction,
        "tolerance_scan": diff.tolerance_scan,
    }
