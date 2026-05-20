# RelaxDiff

> Drop in two POSCARs. Get a relax sanity check, not a trajectory player.

Most crystal structure viewers let you *see* a relaxation. RelaxDiff tells you **whether it looks reasonable** — surfacing displacement, bond, coordination, cell, and symmetry changes, then writing a short narrative explaining what likely happened.

## Install

```bash
pip install -e .
```

## Use

```bash
relaxdiff before.vasp after.vasp -o report.html
```

Open `report.html` in a browser. Self-contained, no server required.

### Options

```
--title TEXT             Report title
--no-llm                 Skip Claude narrative, use deterministic template
--json PATH              Also dump structured diagnosis as JSON
--threshold-displacement Override default 0.5 Å warning threshold
```

### Without an API key

`relaxdiff` works fully offline with `--no-llm`. The LLM narrative requires `ANTHROPIC_API_KEY`.

## Showcase

Four predefined cases under `examples/`:

1. **MgO normal relax** — baseline, everything green
2. **SrTiO3 octahedral tilting** — cubic ↔ tetragonal polymorph diff
3. **Cell collapse** — deliberately broken initial guess, runaway relaxation
4. **TiO2 anatase → rutile** — phase transition diff

Build all four reports:

```bash
pip install -e ".[demo]"
python examples/build.py
```

## What it is not

- Not a general structure viewer (use [matterviz](https://github.com/janosh/matterviz))
- Not an MD defect analyzer (use [OVITO](https://www.ovito.org))
- Not a VESTA plugin (VESTA has no plugin API)
- Not a real-time interactive editor

## How it works

```
two structures
   ↓ pymatgen StructureMatcher        site-by-site mapping
   ↓ geometry / symmetry analysis     deterministic
   ↓ rule-based diagnosis             findings with severity
   ↓ Claude Haiku narrative           reads JSON only, never raw coords
   ↓ Jinja2 + 3Dmol.js                self-contained HTML
report.html
```

See [PLAN.md](PLAN.md) for the full design.

## License

MIT
