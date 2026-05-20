"""Site matching smoke tests."""

import numpy as np
from ase.build import bulk
from pymatgen.io.ase import AseAtomsAdaptor

from relaxdiff.matching import match_sites


def test_identity_mapping_zero_displacement():
    atoms = bulk("Si", "diamond", a=5.43).repeat((2, 1, 1))
    s = AseAtomsAdaptor.get_structure(atoms)
    mapping = match_sites(s, s)
    assert mapping.rmsd < 1e-8
    assert np.allclose(mapping.distances, 0.0)
    assert all(i == j for i, j in mapping.pairs)


def test_rattle_recovers_per_atom_displacement():
    atoms = bulk("MgO", "rocksalt", a=4.25).repeat((2, 2, 2))
    before = AseAtomsAdaptor.get_structure(atoms.copy())
    atoms.rattle(0.05, seed=42)
    after = AseAtomsAdaptor.get_structure(atoms)

    mapping = match_sites(before, after)
    assert mapping.rmsd > 0
    assert mapping.rmsd < 0.2
    assert mapping.method in {"structure_matcher", "hungarian"}
