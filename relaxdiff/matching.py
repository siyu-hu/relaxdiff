"""Site matching — find one-to-one atomic correspondence between two structures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from pymatgen.analysis.structure_matcher import StructureMatcher
from pymatgen.core import Structure
from scipy.optimize import linear_sum_assignment


@dataclass
class SiteMapping:
    """Mapping from before-indices to after-indices, with displacement vectors."""
    pairs: list[tuple[int, int]]
    displacements: np.ndarray            # shape (N, 3) Cartesian, before -> after
    distances: np.ndarray                # shape (N,) magnitude
    method: Literal["structure_matcher", "hungarian"]
    rmsd: float
    aligned_after: Structure             # after, reordered to match before


def match_sites(before: Structure, after: Structure) -> SiteMapping:
    """Match atoms in `after` back to the order in `before`.

    Strategy:
        1. Try pymatgen StructureMatcher.get_s2_like_s1 (works for small to
           moderate deformations and exact composition match).
        2. Fall back to per-element Hungarian assignment minimizing the sum
           of squared displacements under minimum-image convention.
    """
    if len(before) != len(after):
        raise ValueError(
            f"Atom count mismatch: before={len(before)} after={len(after)}. "
            "MVP requires same composition and atom count."
        )

    try:
        return _match_with_structure_matcher(before, after)
    except Exception:
        return _match_with_hungarian(before, after)


def _match_with_structure_matcher(before: Structure, after: Structure) -> SiteMapping:
    matcher = StructureMatcher(
        ltol=0.3, stol=0.5, angle_tol=10, primitive_cell=False, scale=False
    )
    reordered = matcher.get_s2_like_s1(before, after)
    if reordered is None:
        raise RuntimeError("StructureMatcher could not align structures.")

    disps = _min_image_displacements(before, reordered)
    dists = np.linalg.norm(disps, axis=1)
    pairs = [(i, i) for i in range(len(before))]
    rmsd = float(np.sqrt((dists ** 2).mean()))
    return SiteMapping(
        pairs=pairs,
        displacements=disps,
        distances=dists,
        method="structure_matcher",
        rmsd=rmsd,
        aligned_after=reordered,
    )


def _match_with_hungarian(before: Structure, after: Structure) -> SiteMapping:
    """Per-element Hungarian assignment under minimum-image convention.

    Uses `before` lattice for MIC; assumes the cells are similar enough that
    this approximation holds. For very different cells, this still gives a
    reasonable mapping although displacement magnitudes will be approximate.
    """
    lat = before.lattice
    n = len(before)
    assignment = [-1] * n

    species_groups: dict[str, list[int]] = {}
    for i, site in enumerate(before):
        species_groups.setdefault(site.species_string, []).append(i)

    after_by_species: dict[str, list[int]] = {}
    for j, site in enumerate(after):
        after_by_species.setdefault(site.species_string, []).append(j)

    for species, before_idxs in species_groups.items():
        after_idxs = after_by_species.get(species, [])
        if len(before_idxs) != len(after_idxs):
            raise ValueError(f"Composition mismatch for element {species}.")

        # Build cost matrix using MIC distance in fractional coords
        cost = np.zeros((len(before_idxs), len(after_idxs)))
        for a, bi in enumerate(before_idxs):
            fb = np.array(before[bi].frac_coords)
            for b, aj in enumerate(after_idxs):
                fa = np.array(after[aj].frac_coords)
                df = fa - fb
                df -= np.round(df)
                d_cart = lat.matrix.T @ df
                cost[a, b] = np.dot(d_cart, d_cart)

        row_ind, col_ind = linear_sum_assignment(cost)
        for a, b in zip(row_ind, col_ind):
            assignment[before_idxs[a]] = after_idxs[b]

    # Build reordered after structure
    reordered_species = [after[assignment[i]].species_string for i in range(n)]
    reordered_coords = [after[assignment[i]].frac_coords for i in range(n)]
    aligned_after = Structure(after.lattice, reordered_species, reordered_coords)

    disps = _min_image_displacements(before, aligned_after)
    dists = np.linalg.norm(disps, axis=1)
    pairs = [(i, assignment[i]) for i in range(n)]
    rmsd = float(np.sqrt((dists ** 2).mean()))

    return SiteMapping(
        pairs=pairs,
        displacements=disps,
        distances=dists,
        method="hungarian",
        rmsd=rmsd,
        aligned_after=aligned_after,
    )


def _min_image_displacements(before: Structure, after: Structure) -> np.ndarray:
    """Cartesian displacements with MIC, using the average lattice."""
    avg = 0.5 * (np.array(before.lattice.matrix) + np.array(after.lattice.matrix))
    df = after.frac_coords - before.frac_coords
    df -= np.round(df)
    return df @ avg
