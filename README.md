# Knot Studio

Interactive demo and research code for distinguishing prime knots using **quandle coloring** and **quandle 2-cocycle** invariants. Draw or paste a knot diagram, and the app identifies it by its coloring signature.

**Live demo:** <https://knot.cc.cd>

This repository accompanies a research project (Oct 2025 – Feb 2026) at Guangdong Technion - Israel Institute of Technology (GTIIT), supervised by Prof. Marco Farinati. It implements the full experimental pipeline: encode KnotInfo diagrams, count quandle colorings, select a small distinguishing family of quandles via minimum set cover, and refine it with cocycle invariants.

## Results

The census of **84 prime knots with fewer than 10 crossings** (from [KnotInfo](https://knotinfo.org)) is evaluated against a pool of **2,947 finite quandles**.

| Result | Value |
|---|---|
| Prime knots (crossing number < 10) | 84 |
| Candidate quandles | 2,947 |
| Knot pairs distinguished by coloring invariants | 3,484 of 3,486 |
| Minimum coloring set (minimum set cover) | **13 quandles** |
| Knot pairs distinguished after adding 2-cocycle invariants | 3,485 of 3,486 |
| Minimum set with coloring and 2-cocycle invariants | **13 quandles** |
| Pair still unresolved | (8₁₄, 9₈) |

Every number above is recomputed by a command in [Reproducing the results](#reproducing-the-results), from the data and result files committed in this repository.

**One 13-quandle minimum coloring set** ([`tools/io/minimal_set_raw.txt`](tools/io/minimal_set_raw.txt)):

Alexander(Z54, t=5), Alexander(Z55, t=4), Dihedral(69), Alexander(Z85, t=33), Alexander(Z87, t=5), Alexander(Z87, t=32), Dihedral(91), Alexander(Z91, t=11), Alexander(Z91, t=48), Alexander(Z92, t=15), Alexander(Z3[i], t=i), Alexander(Z7[i], t=i), Conjugation(S4).

**One 13-quandle minimum set with cocycle invariants** ([`tools/io/minimal_set.txt`](tools/io/minimal_set.txt)):

Dihedral(41), Alexander(Z67, t=32), Dihedral(69), Alexander(Z81, t=2), Alexander(Z85, t=33), Dihedral(87), Alexander(Z91, t=6), Alexander(Z91, t=9), Dihedral(95), Alexander(F4, t=α), Alexander(Z3[i], t=i), Alexander(Z7[i], t=i), Connected Quandle 9_7.

The cocycle search tests 35 small quandles with coefficients in Z_2, Z_3, Z_5 and Z_7. Cocycle matrices and state sums are in [`tools/io/cocycle_results.json`](tools/io/cocycle_results.json); coverage and minimum sizes are in [`tools/io/refinement_summary.json`](tools/io/refinement_summary.json).

## Installation

Tested with Python 3.9.6 on macOS 26 (Apple Silicon, no GPU required).

```bash
git clone https://github.com/mikessslx/knot-studio.git
cd knot-studio
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Quick start

The 84-knot census is committed under `data/`, so the app works immediately after cloning:

```bash
PUBLIC_DEMO_MODE=0 python3 app.py
```

Open <http://127.0.0.1:5001>. `PUBLIC_DEMO_MODE=0` enables the CPU-heavy endpoints (coloring, cocycle, turbo); the public deployment sets it to `1`.

In the UI, draw a diagram or load a preset (`0_1`, `3_1`, `4_1`, `5_1`), then use **Recognize Knot** to turn strokes into arcs and crossings and **Identify Knot** to match against the signature database. Identification handles single-component knots with at most 9 crossings, including connected sums summing to at most 9.

Docker also works:

```bash
cp .env.example .env    # optionally set PROJECT_REPO_URL
docker compose up --build
```

## Data

| Path | Contents |
|---|---|
| `data/` | 84 knot JSON files, one per prime knot with < 10 crossings |
| `tools/io/knotinfo.csv` | Source PD notation, 249 rows (the 84 knots used here, plus 165 ten-crossing knots) |

Both derive from **KnotInfo** (Livingston & Moore, <https://knotinfo.org>), which is publicly available; please cite KnotInfo if you reuse the data. `python3 tools/knotinfo.py` converts `tools/io/knotinfo.csv` into 249 JSON files in `tools/data/`.

Each knot JSON uses a signed crossing-arc encoding:

```json
{
  "name": "7_4",
  "arcs": [0, 1, 2, 3, 4, 5, 6],
  "crossings": [
    {"id": 0, "type": "positive", "over": 4, "under_in": 0, "under_out": 1}
  ]
}
```

`type` is the crossing sign; `over` is the arc passing over; `under_in` / `under_out` are the incoming and outgoing under-arcs (following the knot's orientation).

## Reproducing the results

All commands are run from the repository root with the virtualenv active. Committed result files are in `tools/io/`; regenerate them to verify.

| Result | Command |
|---|---|
| All coloring counts (84 knots × 2,947 quandles) | `python3 tools/turbo_cli.py --data-dir data --max-crossings 9 -o tools/io/turbo_results.csv --overwrite` |
| Distinguished / unresolved pairs (3,484 and the 2 pairs) | `python3 tools/results.py` |
| Minimum 13-quandle set (minimum set cover) | `python3 tools/minimal_set.py --solver ortools --max 1` |
| Minimum set with coloring and cocycle invariants | `python3 tools/compare_minimal_set.py --solver ortools` |
| Regression checks | `python3 -m unittest discover -s tests -v` |

Notes:

- `results.py` writes `tools/io/results.txt`, containing exactly the two pairs unresolved by coloring counts.
- `minimal_set.py` writes `tools/io/minimal_set_raw.txt`. The optimum size (13) is solver-independent; which 13 quandles is not. Enumerating all optima runs much longer than finding one.
- `compare_minimal_set.py` recomputes cocycles and optimizes coverage over all knot pairs, writing `minimal_set.txt`, `refinement_summary.json` and `cocycle_results.json` under `tools/io/`.
- Both selection commands also support SciPy/HiGHS through `--solver scipy` (`pip install scipy`).
- Counting one knot against a few quandles is instant; use `--limit-knots` / `--limit-quandles` for a quick sanity check.

## How it works

**Solvers** (`logic/solver.py`). Coloring counts are computed by one of several methods, which the app can cross-check against each other:

| Method | Approach |
|---|---|
| Enumeration | Search every arc coloring |
| DFS | Depth-first search with quandle constraints, connectivity-based variable ordering, inverse-table lookahead, symmetry breaking |
| Linear | Gaussian elimination over 𝔽ₚ for Alexander quandles of prime modulus |
| Propagation | Constraint propagation |
| SNF | Smith normal form, for count-only computations over ℤₙ |

**Cocycles** (`logic/cocycle.py`). 2-cocycles are found by solving the linear cocycle condition, then quotienting out coboundaries to get `H²`; the state-sum invariant is `Φ_φ(K) = Σ t^{W(C)}` over all colorings.

**Quandle selection** (`tools/minimal_set.py`). Each quandle induces a signature on the census. Choosing a small family that separates all distinguishable pairs is cast as **minimum set cover** and solved by integer programming (OR-Tools, Gurobi or SciPy/HiGHS).

**Identification** (`logic/identifier.py`). `logic/signature_db.py` stores coloring counts for 16 quandles and matches an input diagram by signature.

## Repository structure

```
app.py                      Flask entry point and API routes
logic/
  geometry.py               Stroke geometry and intersection detection
  graph.py                  Crossing graph, arc traversal, over/under state
  recognition.py            Stroke data to knot diagram
  solver.py                 Quandle coloring solvers (enum/DFS/linear/SNF)
  cocycle.py                2-cocycles and cocycle invariants
  identifier.py             Coloring-signature knot identification
  turbo.py                  Notebook and GAP export
  signature_db.py           Generated identification database
static/                     Front-end (canvas drawing, UI, quandle tables)
templates/index.html        Single-page UI
tools/
  knotinfo.py               KnotInfo CSV/PD notation to knot JSON
  turbo_cli.py              Batch coloring counts -> CSV
  results.py                Group knots with identical coloring counts
  compare.py                Distinguish a pair by colorings and cocycles
  minimal_set.py            Minimum distinguishing quandle set (set cover)
  compare_minimal_set.py    Recompute cocycles and optimize full-pair coverage
  analyze_minimal_set.py    Summarize set-cover output
  data_results.py           Copy grouped knot JSON files
  build_signature_db.py     Build logic/signature_db.py
  io/                       Committed evidence: source CSV and result files
data/                       84 prime-knot JSON files
```

## Citation

If you use this code, please cite it as:

```bibtex
@misc{li2026knotstudio,
  title        = {Knot Studio: quandle coloring and cocycle invariants for
                  distinguishing prime knots with fewer than 10 crossings},
  author       = {Li, Xiang},
  year         = {2026},
  howpublished = {\url{https://github.com/mikessslx/knot-studio}},
  note         = {Supervised by Prof. Marco Farinati, Guangdong Technion - Israel Institute of Technology}
}
```

Please also cite [KnotInfo](https://knotinfo.org) for the knot data.

## License

Code: [Apache 2.0](LICENSE). Knot data derives from KnotInfo; see [Data](#data).

## Acknowledgements

Supervised by Prof. Marco Farinati (GTIIT). Knot data from KnotInfo (Livingston & Moore). Set cover solved with [OR-Tools](https://developers.google.com/optimization), Gurobi and SciPy/HiGHS.
