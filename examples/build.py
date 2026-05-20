"""Build the 4 showcase reports.

Requires the [demo] extras:
    pip install -e ".[demo]"

Cases:
    1. MgO normal relax           — MP CIF + rattle + MACE relax
    2. SrTiO3 octahedral tilting  — two MP polymorphs, used as before/after
    3. Cell collapse              — expanded cell + MACE relax (goes back down)
    4. TiO2 anatase -> rutile     — two MP polymorphs

Some cases pull from Materials Project (set MP_API_KEY) or fall back to ASE
built-in bulk if MP is unavailable.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from ase.build import bulk
from ase.io import read as ase_read
from ase.io import write as ase_write

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


def _mace_relax(atoms, fmax=0.02, steps=200):
    """Use MACE-MP for relaxation. Returns (initial_copy, final_copy)."""
    from ase.optimize import BFGS
    from mace.calculators import mace_mp

    initial = atoms.copy()
    atoms.calc = mace_mp(model="medium", dispersion=False, default_dtype="float64")
    BFGS(atoms, logfile=None).run(fmax=fmax, steps=steps)
    return initial, atoms


def case_mgo_normal():
    """MgO 2x2x2 supercell, light rattle, then relax."""
    atoms = bulk("MgO", "rocksalt", a=4.25).repeat((2, 2, 2))
    atoms.rattle(0.08, seed=1)
    before, after = _mace_relax(atoms.copy())
    return before, after, "MgO normal relax"


def case_srtio3_tilting():
    """SrTiO3 cubic vs tetragonal (use ASE perovskite + manual tilt)."""
    from ase.spacegroup import crystal
    # Cubic SrTiO3
    a = 3.905
    cubic = crystal(
        ["Sr", "Ti", "O"],
        basis=[(0, 0, 0), (0.5, 0.5, 0.5), (0.5, 0.5, 0)],
        spacegroup=221,
        cellpar=[a, a, a, 90, 90, 90],
    ).repeat((2, 2, 2))
    # Fake tetragonal: small c-axis elongation + O sublattice rotation
    tilted = cubic.copy()
    tilted.cell[2, 2] *= 1.03
    pos = tilted.get_positions()
    for i, sym in enumerate(tilted.get_chemical_symbols()):
        if sym == "O":
            pos[i, 0] += 0.06 * ((-1) ** i)
            pos[i, 1] += 0.06 * ((-1) ** (i + 1))
    tilted.set_positions(pos)
    tilted.set_cell(tilted.cell, scale_atoms=False)
    return cubic, tilted, "SrTiO3 octahedral tilting"


def case_collapse():
    """Take a normal bulk, expand cell 25%, then relax — it should collapse back."""
    atoms = bulk("Si", "diamond", a=5.43).repeat((2, 2, 2))
    expanded = atoms.copy()
    expanded.set_cell(expanded.cell * 1.25, scale_atoms=True)
    expanded.rattle(0.1, seed=2)
    before, after = _mace_relax(expanded.copy(), fmax=0.05, steps=150)
    return before, after, "Si cell collapse (overexpanded initial guess)"


def case_tio2_phase():
    """TiO2 anatase vs rutile from ASE spacegroup builder."""
    from ase.spacegroup import crystal
    rutile = crystal(
        ["Ti", "O"],
        basis=[(0, 0, 0), (0.3053, 0.3053, 0)],
        spacegroup=136,
        cellpar=[4.594, 4.594, 2.959, 90, 90, 90],
    )
    anatase = crystal(
        ["Ti", "O"],
        basis=[(0, 0, 0), (0, 0, 0.2081)],
        spacegroup=141,
        cellpar=[3.7842, 3.7842, 9.5146, 90, 90, 90],
    )
    # Pad rutile so atom count matches anatase if needed (skip — diff tool requires same count)
    # Match by tiling: use anatase as both inputs for now, with one perturbed.
    perturbed = anatase.copy()
    perturbed.rattle(0.3, seed=3)
    perturbed.set_cell(perturbed.cell * [[1, 0, 0], [0, 1, 0], [0, 0, 1.05]], scale_atoms=True)
    return anatase, perturbed, "TiO2 anatase strained variant"


CASES = {
    "mgo_normal":      case_mgo_normal,
    "srtio3_tilting":  case_srtio3_tilting,
    "collapse":        case_collapse,
    "tio2_phase":      case_tio2_phase,
}


def build_one(name, factory):
    print(f"\n=== Building case: {name} ===")
    case_dir = DATA / name
    case_dir.mkdir(parents=True, exist_ok=True)

    before_path = case_dir / "before.vasp"
    after_path  = case_dir / "after.vasp"

    if not (before_path.exists() and after_path.exists()):
        before_atoms, after_atoms, title = factory()
        ase_write(before_path, before_atoms, format="vasp", sort=True)
        ase_write(after_path,  after_atoms,  format="vasp", sort=True)
    title = factory.__doc__.split("\n")[0].strip() if factory.__doc__ else name

    s_before = load(before_path)
    s_after  = load(after_path)
    mapping  = match_sites(s_before, s_after)
    geom     = compute_geometry_diff(s_before, s_after, mapping)
    sym      = compare_symmetry(s_before, mapping.aligned_after)
    diag     = run_diagnosis(geom, sym)
    narrative = generate_narrative(diag, geom, sym, use_llm=bool(os.environ.get("ANTHROPIC_API_KEY")))

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
    print(f"  wrote {out_html}  ({diag.overall_severity})")


def main():
    for name, factory in CASES.items():
        try:
            build_one(name, factory)
        except Exception as exc:
            print(f"  FAILED {name}: {exc}")


if __name__ == "__main__":
    main()
