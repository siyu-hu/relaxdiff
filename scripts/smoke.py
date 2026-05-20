"""Generate a pair of test structures so we can smoke-test the CLI without DFT."""

from pathlib import Path

from ase.build import bulk
from ase.io import write as ase_write

out = Path(__file__).parent.parent / "examples" / "data" / "smoke"
out.mkdir(parents=True, exist_ok=True)

before = bulk("MgO", "rocksalt", a=4.25).repeat((2, 2, 2))
ase_write(out / "before.vasp", before, format="vasp", sort=True)

after = before.copy()
after.rattle(0.08, seed=42)
after.set_cell(after.cell * 1.02, scale_atoms=True)
ase_write(out / "after.vasp", after, format="vasp", sort=True)

print(f"wrote {out}/before.vasp and after.vasp")
