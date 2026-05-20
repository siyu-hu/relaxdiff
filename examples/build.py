"""Build the 4 showcase reports.

No DFT, no MACE — every case is constructed by pure geometric manipulation of
an ASE-built bulk structure. This keeps the demo runnable from a fresh clone
in seconds, with no model weight downloads.

Each case takes a base structure and constructs a (before, after) pair that
exhibits one specific kind of difference RelaxDiff should detect.
"""

from __future__ import annotations

import os
import sys
import numpy as np
from pathlib import Path

# Make the package importable when running from a fresh clone without install.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ase.build import bulk
from ase.io import write as ase_write
from ase.spacegroup import crystal

from relaxdiff.diagnose import run_diagnosis
from relaxdiff.geometry import compute_geometry_diff
from relaxdiff.io import load
from relaxdiff.matching import match_sites
from relaxdiff.narrative import generate_narrative
from relaxdiff.render import render_report
from relaxdiff.symmetry import compare_symmetry


ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUT = ROOT.parent / "docs" / "cases"
OUT.mkdir(parents=True, exist_ok=True)


def case_mgo_normal():
    """Baseline: tiny rattle + 0.5% cell expansion. Should look clean."""
    atoms = bulk("MgO", "rocksalt", a=4.21).repeat((2, 2, 2))
    before = atoms.copy()
    after = atoms.copy()
    after.rattle(0.012, seed=11)
    after.set_cell(after.cell * 1.005, scale_atoms=True)
    return before, after, "MgO — clean ionic relaxation"


def case_srtio3_tilting():
    """Cubic SrTiO3 → tetragonal-like with rotated O sublattice (octahedral tilt)."""
    a = 3.905
    cubic = crystal(
        ["Sr", "Ti", "O"],
        basis=[(0, 0, 0), (0.5, 0.5, 0.5), (0.5, 0.5, 0)],
        spacegroup=221,
        cellpar=[a, a, a, 90, 90, 90],
    ).repeat((2, 2, 2))

    tilted = cubic.copy()
    cell = tilted.get_cell().array.copy()
    cell[2, 2] *= 1.025
    tilted.set_cell(cell, scale_atoms=True)

    pos = tilted.get_positions()
    symbols = tilted.get_chemical_symbols()
    c_len = cell[2, 2]
    for i, sym in enumerate(symbols):
        if sym == "O":
            phase = 2 * np.pi * pos[i, 2] / c_len
            pos[i, 0] += 0.18 * np.sin(phase)
            pos[i, 1] += 0.18 * np.cos(phase)
    tilted.set_positions(pos)
    return cubic, tilted, "SrTiO3 — octahedral tilting"


def case_collapse():
    """Si cell compressed to 78% volume — extreme cell collapse case."""
    atoms = bulk("Si", "diamond", a=5.43).repeat((2, 2, 2))
    before = atoms.copy()
    after = atoms.copy()
    after.set_cell(after.cell * 0.78, scale_atoms=True)
    after.rattle(0.10, seed=22)
    return before, after, "Si — overexpanded initial guess collapsing"


def case_tio2_phase():
    """TiO2 rutile distorted by shear strain and heavy rattle."""
    rutile = crystal(
        ["Ti", "O"],
        basis=[(0, 0, 0), (0.3053, 0.3053, 0)],
        spacegroup=136,
        cellpar=[4.594, 4.594, 2.959, 90, 90, 90],
    ).repeat((2, 2, 2))

    distorted = rutile.copy()
    cell = distorted.get_cell().array.copy()
    cell[1, 0] += 0.55
    cell[2, 2] *= 1.06
    distorted.set_cell(cell, scale_atoms=True)
    distorted.rattle(0.22, seed=33)
    return rutile, distorted, "TiO2 — large shear & atomic rattle"


CASES = {
    "mgo_normal":     case_mgo_normal,
    "srtio3_tilting": case_srtio3_tilting,
    "collapse":       case_collapse,
    "tio2_phase":     case_tio2_phase,
}


def build_one(name: str, factory) -> None:
    print(f"\n=== Building case: {name} ===")
    case_dir = DATA / name
    case_dir.mkdir(parents=True, exist_ok=True)

    before_atoms, after_atoms, title = factory()
    before_path = case_dir / "before.vasp"
    after_path = case_dir / "after.vasp"
    ase_write(before_path, before_atoms, format="vasp", sort=True)
    ase_write(after_path, after_atoms, format="vasp", sort=True)

    s_before = load(before_path)
    s_after = load(after_path)
    mapping = match_sites(s_before, s_after)
    geom = compute_geometry_diff(s_before, s_after, mapping)
    sym = compare_symmetry(s_before, mapping.aligned_after)
    diag = run_diagnosis(geom, sym)
    narrative = generate_narrative(
        diag, geom, sym, use_llm=bool(os.environ.get("ANTHROPIC_API_KEY"))
    )

    out_html = OUT / f"{name}.html"
    render_report(
        before=s_before,
        after=mapping.aligned_after,
        mapping=mapping,
        geometry=geom,
        symmetry=sym,
        diagnosis=diag,
        narrative=narrative,
        title=f"RelaxDiff · {title}",
        output_path=out_html,
    )
    print(f"  -> {out_html.relative_to(ROOT.parent)}  ({diag.overall_severity})")
    for f in diag.findings:
        print(f"     [{f.severity}] {f.short}")


def main() -> None:
    for name, factory in CASES.items():
        try:
            build_one(name, factory)
        except Exception as exc:
            print(f"  FAILED {name}: {exc}")
            raise


if __name__ == "__main__":
    main()
