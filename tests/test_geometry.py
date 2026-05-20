"""Geometry diff smoke tests."""

import numpy as np
from ase.build import bulk
from pymatgen.io.ase import AseAtomsAdaptor

from relaxdiff.geometry import compute_geometry_diff
from relaxdiff.matching import match_sites


def test_identical_structures_no_changes():
    atoms = bulk("MgO", "rocksalt", a=4.25).repeat((2, 2, 2))
    s = AseAtomsAdaptor.get_structure(atoms)
    mapping = match_sites(s, s)
    geom = compute_geometry_diff(s, s, mapping)

    assert geom.max_displacement < 1e-6
    assert abs(geom.cell.volume_change_frac) < 1e-9
    assert all(b.kind not in {"broken", "formed"} for b in geom.bond_changes)
    assert all(a.cn_change == 0 for a in geom.per_atom)


def test_volume_change_is_detected():
    atoms = bulk("Si", "diamond", a=5.43)
    before = AseAtomsAdaptor.get_structure(atoms.copy())
    atoms.set_cell(atoms.cell * 1.1, scale_atoms=True)
    after = AseAtomsAdaptor.get_structure(atoms)

    mapping = match_sites(before, after)
    geom = compute_geometry_diff(before, after, mapping)
    assert geom.cell.volume_change_frac > 0.3
