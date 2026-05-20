"""Diagnosis rule engine smoke tests."""

from ase.build import bulk
from pymatgen.io.ase import AseAtomsAdaptor

from relaxdiff.diagnose import run_diagnosis
from relaxdiff.geometry import compute_geometry_diff
from relaxdiff.matching import match_sites
from relaxdiff.symmetry import compare_symmetry


def _diagnose(before, after):
    mapping = match_sites(before, after)
    geom = compute_geometry_diff(before, after, mapping)
    sym = compare_symmetry(before, mapping.aligned_after)
    return run_diagnosis(geom, sym)


def test_identical_is_ok():
    atoms = bulk("MgO", "rocksalt", a=4.25).repeat((2, 2, 2))
    s = AseAtomsAdaptor.get_structure(atoms)
    report = _diagnose(s, s)
    assert report.overall_severity == "ok"
    assert any(f.rule == "normal_relaxation" for f in report.findings)


def test_volume_collapse_triggers_alert():
    atoms = bulk("Si", "diamond", a=5.43).repeat((2, 2, 2))
    before = AseAtomsAdaptor.get_structure(atoms.copy())
    atoms.set_cell(atoms.cell * 0.8, scale_atoms=True)
    after = AseAtomsAdaptor.get_structure(atoms)

    report = _diagnose(before, after)
    assert report.overall_severity in {"warn", "alert"}
    assert any("cell" in f.rule for f in report.findings)
