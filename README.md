<p align="center">
  <img src="docs/assets/logo.svg" alt="RelaxDiff" height="64" />
</p>

<h3 align="center">Drop in two structures. Get a relax sanity check, not a trajectory player.</h3>

<p align="center">
  A diagnostic viewer for <b>DFT geometry-relaxation</b> output &mdash;
  diff two crystal structures, surface every meaningful change
  (atomic displacement, bond &amp; coordination shifts, cell strain,
  symmetry breaking) and read a one-paragraph LLM narrative that explains
  whether the relaxation looks reasonable.
</p>

<p align="center">
  <a href="https://siyu-hu.github.io/relaxdiff/"><b>Live demo</b></a> ·
  <a href="#showcase">Showcase</a> ·
  <a href="#install">Install</a> ·
  <a href="#how-it-works">How it works</a>
</p>

<p align="center">
  <a href="https://siyu-hu.github.io/relaxdiff/">
    <img src="docs/assets/screenshot-gallery.png" alt="RelaxDiff demo gallery" width="100%" />
  </a>
</p>

## Quick start

```bash
git clone https://github.com/siyu-hu/relaxdiff && cd relaxdiff
python -m venv .venv && source .venv/bin/activate
pip install -e .
relaxdiff before.cif after.cif -o report.html
open report.html        # macOS — use xdg-open on Linux
```

Don't want to install anything locally? Spin up a preconfigured Codespace in your browser:

<p>
  <a href="https://codespaces.new/siyu-hu/relaxdiff?quickstart=1">
    <img src="https://github.com/codespaces/badge.svg" alt="Open in GitHub Codespaces" />
  </a>
</p>

The Codespace auto-runs `pip install -e .` on first boot, so once it's ready you can run the CLI directly in the integrated terminal.

---

> **Built for:** VASP, Quantum ESPRESSO, ABINIT, CP2K, ASE, pymatgen, MACE / CHGNet relaxations — anything that writes a CIF / POSCAR / extxyz before-and-after pair.

Most crystal structure viewers let you **see** a relaxation. RelaxDiff tells you **whether it looks reasonable**.

It diffs two structures along every axis a researcher cares about &mdash; per-atom displacement, bond breaking / forming, coordination changes, cell strain, space group changes &mdash; and produces a self-contained HTML report with a 3D viewer, severity-tagged findings, and a short natural-language narrative. One command. No server. No toolchain.

```bash
relaxdiff before.cif after.cif -o report.html
```

**Supported input formats:** CIF · POSCAR / CONTCAR / `.vasp` · `.xyz` / `.extxyz` · pymatgen JSON · ASE `Atoms` (when used as a library). Both structures must share composition and atom count.

## What you get

<table>
  <tr>
    <td width="50%">
      <b>Interactive 3D diff viewer</b><br/>
      Toggle Before / After / Overlay / Diff heatmap. In <i>Diff heatmap</i> mode every atom is colored by how far it moved &mdash; small movement blue, big movement red &mdash; so problem atoms jump out at a glance.<br/><br/>
      <img src="docs/assets/screenshot-diff-heatmap.png" alt="Diff heatmap mode" width="100%"/>
    </td>
    <td width="50%">
      <b>Severity-tagged diagnosis</b><br/>
      Eleven rules turn raw geometry into severity-tagged findings: large displacement, runaway atoms, cell collapse, bond breaking, coordination changes, broken or elevated symmetry, large shear. Every report gets an overall OK / INFO / WARN / ALERT chip.<br/><br/>
      <img src="docs/assets/screenshot-collapse.png" alt="Alert-level report" width="100%"/>
    </td>
  </tr>
  <tr>
    <td>
      <b>LLM narrative (optional)</b><br/>
      Reads the structured diagnosis JSON &mdash; never raw coordinates &mdash; and produces a three-paragraph plain-English read of the result, citing specific atom indices. Works with any OpenAI-compatible LLM endpoint (see <a href="#llm-narrative">below</a>). Without an API key, a deterministic template covers the same ground.
    </td>
    <td>
      <b>Adaptive symmetry detection</b><br/>
      Runs a tolerance scan with <code>spglib</code> and picks an effective <code>symprec</code> automatically, so a small rattle doesn't get misread as full P1 collapse but a real distortion still trips the rule.
    </td>
  </tr>
</table>

## Showcase

Four predefined cases, auto-built and deployed to the gallery:

| Case | Severity | What it shows |
|---|---|---|
| [MgO normal relax](https://siyu-hu.github.io/relaxdiff/cases/mgo_normal.html) | ![](https://img.shields.io/badge/-OK-1a7f37?style=flat-square) | Clean baseline &mdash; what an unremarkable relaxation looks like |
| [SrTiO₃ octahedral tilting](https://siyu-hu.github.io/relaxdiff/cases/srtio3_tilting.html) | ![](https://img.shields.io/badge/-WARN-9a6700?style=flat-square) | Cubic → tetragonal-tilted variant; symmetry breaking + coordination shifts |
| [Si cell collapse](https://siyu-hu.github.io/relaxdiff/cases/collapse.html) | ![](https://img.shields.io/badge/-ALERT-cf222e?style=flat-square) | Cell pressed to ~78% of original volume; full symmetry loss |
| [TiO₂ strained variant](https://siyu-hu.github.io/relaxdiff/cases/tio2_phase.html) | ![](https://img.shields.io/badge/-WARN-9a6700?style=flat-square) | Large shear + heavy rattle; broken bonds + coordination changes |

Rebuild them locally in seconds (no DFT, no ML potential &mdash; just geometric construction):

```bash
python examples/build.py
```

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Use

```bash
relaxdiff before.cif after.cif -o report.html
```

Open `report.html` in any browser. Self-contained, no server required.

### Options

```
--title TEXT             Report title shown in the header
--no-llm                 Skip the LLM narrative, use the deterministic template
--json PATH              Also dump structured diagnosis as JSON
--threshold-displacement Override the default 0.5 Å warn threshold (Å)
```

### LLM narrative

RelaxDiff talks to **any OpenAI-compatible chat-completions endpoint** &mdash; OpenAI, DeepSeek, Together, Groq, Fireworks, Ollama, your own vLLM server, etc.

```bash
cp .env.example .env
# edit .env with your LLM provider's API key, model, and base URL
export $(grep -v '^#' .env | xargs)
relaxdiff before.cif after.cif -o report.html
```

Without `RELAXDIFF_LLM_API_KEY` (or with `--no-llm`), the report falls back to a deterministic three-paragraph template. No internet required.

| Provider | `RELAXDIFF_LLM_MODEL` | `RELAXDIFF_LLM_BASE_URL` |
|---|---|---|
| DeepSeek | `deepseek-chat` | `https://api.deepseek.com` |
| OpenAI | `gpt-4o-mini` | `https://api.openai.com/v1` |
| Together | e.g. `meta-llama/Llama-3-8b-chat-hf` | `https://api.together.xyz/v1` |
| Groq | e.g. `llama-3.1-70b-versatile` | `https://api.groq.com/openai/v1` |
| Ollama (local) | e.g. `llama3` | `http://localhost:11434/v1` |

### CI / Secrets

CI auto-rebuilds and deploys the gallery on every push to `main`. It uses the deterministic narrative by default &mdash; no API calls, no token cost.

To regenerate narratives with an LLM from CI:

1. Repo → **Settings** → **Secrets and variables** → **Actions** → add a repo secret named `RELAXDIFF_LLM_API_KEY`. Optionally add `RELAXDIFF_LLM_MODEL` and `RELAXDIFF_LLM_BASE_URL` as variables (not secrets).
2. Repo → **Actions** → *Deploy demo site to GitHub Pages* → **Run workflow** → tick `use_llm`.

`.env` is gitignored. CI only sees the secret on the manual `use_llm=true` path. Nothing in this repo ever stores a key in plain text.

## How it works

```
two structures
   ↓ pymatgen StructureMatcher (Hungarian fallback)   site-by-site mapping
   ↓ geometry + symmetry analysis                     deterministic
   ↓ 11 rules + adaptive symprec                      severity-tagged findings
   ↓ OpenAI-compatible LLM (or fallback template)     3-paragraph narrative
   ↓ Jinja2 + 3Dmol.js                                self-contained HTML
report.html
```

The LLM is the **last** thing in the pipeline and only ever sees structured JSON &mdash; atom indices, magnitudes, rule outputs &mdash; not raw coordinates. Hallucination surface stays small. See [PLAN.md](PLAN.md) for the full design.

## What it is not

- Not a general structure viewer (use [matterviz](https://github.com/janosh/matterviz))
- Not an MD defect analyzer (use [OVITO](https://www.ovito.org))
- Not a VESTA plugin (VESTA has no plugin API)
- Not a real-time interactive editor

## Keywords

DFT relaxation · ionic relaxation diagnostics · crystal structure diff · before/after relaxation comparison · VASP / Quantum ESPRESSO / ABINIT / CP2K post-processing · pymatgen + ASE · spglib symmetry analysis · materials informatics · interactive 3D structure viewer · LLM for materials science

## License

MIT
