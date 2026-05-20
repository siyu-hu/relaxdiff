"""Structure I/O — unify any input into a pymatgen Structure."""

from __future__ import annotations

from pathlib import Path
from typing import Union

from pymatgen.core import Structure
from pymatgen.io.ase import AseAtomsAdaptor

PathLike = Union[str, Path]


def load(source) -> Structure:
    """Load a structure from path or accept Structure / ASE Atoms directly.

    Supported file extensions: .vasp, POSCAR/CONTCAR, .cif, .xyz, .extxyz, .json
    """
    if isinstance(source, Structure):
        return source

    # ASE Atoms duck-type check
    if hasattr(source, "get_chemical_symbols") and hasattr(source, "get_positions"):
        return AseAtomsAdaptor.get_structure(source)

    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(path)

    name = path.name.lower()
    suffix = path.suffix.lower()

    if name in {"poscar", "contcar"} or suffix in {".vasp", ".poscar"}:
        return Structure.from_file(path)
    if suffix == ".cif":
        return Structure.from_file(path)
    if suffix in {".xyz", ".extxyz"}:
        from ase.io import read as ase_read
        atoms = ase_read(path)
        return AseAtomsAdaptor.get_structure(atoms)
    if suffix == ".json":
        return Structure.from_file(path)

    # Last resort: pymatgen sniff
    return Structure.from_file(path)


def to_cif_string(structure: Structure) -> str:
    """Serialize Structure to CIF string for inline embedding."""
    from pymatgen.io.cif import CifWriter
    return str(CifWriter(structure))
