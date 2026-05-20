"""Pull a couple of real relax trajectories from Materials Project for showcase use.

Requires the [demo] extras and MP_API_KEY env var.
"""

from __future__ import annotations

import os
from pathlib import Path

from ase.io import write as ase_write

DATA = Path(__file__).resolve().parent.parent / "examples" / "data"


def fetch(material_id: str, slug: str):
    from mp_api.client import MPRester

    key = os.environ.get("MP_API_KEY")
    if not key:
        raise SystemExit("Set MP_API_KEY first.")

    out_dir = DATA / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    with MPRester(key) as mpr:
        tasks = mpr.tasks.search(material_ids=[material_id])
        if not tasks:
            raise SystemExit(f"No tasks found for {material_id}")
        task = tasks[0]
        initial = task.input.structure
        final = task.output.structure

    from pymatgen.io.ase import AseAtomsAdaptor
    ase_write(out_dir / "before.vasp", AseAtomsAdaptor.get_atoms(initial), format="vasp", sort=True)
    ase_write(out_dir / "after.vasp", AseAtomsAdaptor.get_atoms(final), format="vasp", sort=True)
    print(f"  wrote {out_dir}/before.vasp + after.vasp from {material_id}")


def main():
    # Examples; user can override.
    fetch("mp-1265", "mgo_real")
    fetch("mp-5229", "srtio3_real")
    fetch("mp-390",  "tio2_anatase_real")


if __name__ == "__main__":
    main()
