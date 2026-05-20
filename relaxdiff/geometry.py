"""Geometric diff — displacement, bonds, coordination, cell, strain."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
from pymatgen.analysis.local_env import CrystalNN
from pymatgen.core import Structure

from relaxdiff.matching import SiteMapping


@dataclass
class AtomDiff:
    index: int
    element: str
    displacement: float                  # Å
    displacement_vec: list[float]
    cn_before: int
    cn_after: int
    cn_change: int


@dataclass
class BondChange:
    i: int
    j: int
    element_i: str
    element_j: str
    length_before: Optional[float]       # None if newly formed
    length_after: Optional[float]        # None if broken
    delta: Optional[float]
    kind: str                            # "broken" | "formed" | "stretched" | "compressed"


@dataclass
class CellChange:
    a_before: float
    a_after: float
    b_before: float
    b_after: float
    c_before: float
    c_after: float
    alpha_before: float
    alpha_after: float
    beta_before: float
    beta_after: float
    gamma_before: float
    gamma_after: float
    volume_before: float
    volume_after: float
    volume_change_frac: float            # (V_after - V_before) / V_before


@dataclass
class GeometryDiff:
    per_atom: list[AtomDiff]
    bond_changes: list[BondChange]
    cell: CellChange
    strain: list[list[float]]            # 3x3 symmetric strain tensor
    rotation: list[list[float]]          # 3x3 rotation
    rmsd: float
    max_displacement: float
    max_displacement_index: int
    formula: str
    n_atoms: int

    def to_dict(self) -> dict:
        return {
            "per_atom": [a.__dict__ for a in self.per_atom],
            "bond_changes": [b.__dict__ for b in self.bond_changes],
            "cell": self.cell.__dict__,
            "strain": self.strain,
            "rotation": self.rotation,
            "rmsd": self.rmsd,
            "max_displacement": self.max_displacement,
            "max_displacement_index": self.max_displacement_index,
            "formula": self.formula,
            "n_atoms": self.n_atoms,
        }


def compute_geometry_diff(
    before: Structure,
    after: Structure,
    mapping: SiteMapping,
    bond_change_threshold: float = 0.15,
) -> GeometryDiff:
    """Compute every geometric quantity we need for diagnosis."""
    aligned_after = mapping.aligned_after

    # Per-atom diff
    cn_before = _coordination_numbers(before)
    cn_after = _coordination_numbers(aligned_after)

    per_atom = [
        AtomDiff(
            index=i,
            element=before[i].species_string,
            displacement=float(mapping.distances[i]),
            displacement_vec=mapping.displacements[i].tolist(),
            cn_before=cn_before[i],
            cn_after=cn_after[i],
            cn_change=cn_after[i] - cn_before[i],
        )
        for i in range(len(before))
    ]

    # Bonds
    bond_changes = _bond_changes(
        before, aligned_after, cn_before, cn_after, bond_change_threshold
    )

    # Cell
    cell = _cell_change(before, aligned_after)

    # Strain (polar decomposition of F = A_after @ A_before^-1)
    A_b = np.array(before.lattice.matrix)
    A_a = np.array(aligned_after.lattice.matrix)
    F = A_a.T @ np.linalg.inv(A_b.T)
    U, P = _polar_decomposition(F)
    strain = (P - np.eye(3)).tolist()
    rotation = U.tolist()

    max_idx = int(np.argmax(mapping.distances))

    return GeometryDiff(
        per_atom=per_atom,
        bond_changes=bond_changes,
        cell=cell,
        strain=[list(map(float, row)) for row in strain],
        rotation=[list(map(float, row)) for row in rotation],
        rmsd=float(mapping.rmsd),
        max_displacement=float(mapping.distances[max_idx]),
        max_displacement_index=max_idx,
        formula=before.composition.reduced_formula,
        n_atoms=len(before),
    )


def _coordination_numbers(structure: Structure) -> list[int]:
    """CrystalNN coordination numbers; degrade gracefully on weird structures."""
    cnn = CrystalNN()
    cns = []
    for i in range(len(structure)):
        try:
            cns.append(int(cnn.get_cn(structure, i)))
        except Exception:
            cns.append(0)
    return cns


def _bond_changes(
    before: Structure,
    after: Structure,
    cn_before: list[int],
    cn_after: list[int],
    threshold: float,
) -> list[BondChange]:
    """Compare neighbor lists from CrystalNN and surface broken/formed/changed bonds."""
    cnn = CrystalNN()

    def neighbor_set(struct: Structure) -> dict[tuple[int, int], float]:
        result: dict[tuple[int, int], float] = {}
        for i in range(len(struct)):
            try:
                info = cnn.get_nn_info(struct, i)
            except Exception:
                continue
            for entry in info:
                j = entry["site_index"]
                key = (min(i, j), max(i, j))
                if key in result:
                    continue
                dist = float(struct[i].distance(entry["site"]))
                result[key] = dist
        return result

    before_bonds = neighbor_set(before)
    after_bonds = neighbor_set(after)

    changes: list[BondChange] = []
    keys = set(before_bonds) | set(after_bonds)
    for key in sorted(keys):
        i, j = key
        d_b = before_bonds.get(key)
        d_a = after_bonds.get(key)
        if d_b is None:
            kind = "formed"
            delta = None
        elif d_a is None:
            kind = "broken"
            delta = None
        else:
            delta = d_a - d_b
            if abs(delta) / d_b < threshold:
                continue
            kind = "stretched" if delta > 0 else "compressed"

        changes.append(BondChange(
            i=i, j=j,
            element_i=before[i].species_string,
            element_j=before[j].species_string,
            length_before=d_b,
            length_after=d_a,
            delta=delta,
            kind=kind,
        ))
    return changes


def _cell_change(before: Structure, after: Structure) -> CellChange:
    lb, la = before.lattice, after.lattice
    return CellChange(
        a_before=lb.a, a_after=la.a,
        b_before=lb.b, b_after=la.b,
        c_before=lb.c, c_after=la.c,
        alpha_before=lb.alpha, alpha_after=la.alpha,
        beta_before=lb.beta, beta_after=la.beta,
        gamma_before=lb.gamma, gamma_after=la.gamma,
        volume_before=lb.volume, volume_after=la.volume,
        volume_change_frac=(la.volume - lb.volume) / lb.volume,
    )


def _polar_decomposition(F: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Right polar decomposition F = U @ P, U orthogonal, P symmetric PSD."""
    U_svd, S, Vt = np.linalg.svd(F)
    U = U_svd @ Vt
    P = Vt.T @ np.diag(S) @ Vt
    return U, P
