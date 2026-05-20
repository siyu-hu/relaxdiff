"""RelaxDiff — crystal structure relaxation sanity checker."""

__version__ = "0.1.0"

from relaxdiff.io import load
from relaxdiff.matching import match_sites
from relaxdiff.geometry import compute_geometry_diff
from relaxdiff.symmetry import compare_symmetry
from relaxdiff.diagnose import run_diagnosis
from relaxdiff.narrative import generate_narrative
from relaxdiff.render import render_report

__all__ = [
    "load",
    "match_sites",
    "compute_geometry_diff",
    "compare_symmetry",
    "run_diagnosis",
    "generate_narrative",
    "render_report",
]
