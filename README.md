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
| Minimum coloring set (minimum set cover) | **14 quandles** |
| Refined set after adding 2-cocycle invariants | **9 quandles** |
| Pairs still unresolved | (7₄, 9₂) and (8₁₄, 9₈) |

Every number above is recomputed by a command in [Reproducing the results](#reproducing-the-results), from the data and result files committed in this repository.

**The 14-quandle minimum coloring set** ([`tools/io/minimal_set_raw.txt`](tools/io/minimal_set_raw.txt)):

Dihedral(27), Alexander(ℤ₂₉, t=3), Dihedral(58), Alexander(ℤ₆₉, t=20), Dihedral(85), Alexander(ℤ₉₁, t=6), Alexander(ℤ₉₁, t=18), Alexander(ℤ₉₁, t=48), Dihedral(92), Alexander(ℤ₉₅, t=17), Alexander(𝔽₄, t=α), Alexander(ℤ₃[i], t=i), Alexander(ℤ₇[i], t=i), Connected Quandle 6₁.

**The refined 9-quandle set** after cocycle invariants ([`tools/io/minimal_set.txt`](tools/io/minimal_set.txt)):

Dihedral(27), Alexander(ℤ₂₉, t=3), Alexander(ℤ₆₉, t=20), Dihedral(85), Alexander(ℤ₉₁, t=48), Dihedral(92), Alexander(ℤ₉₅, t=17), Alexander(𝔽₄, t=α), Connected Quandle 6₁.

Of the 14, five quandles (Dihedral(58), Alexander(ℤ₉₁,t=6), Alexander(ℤ₉₁,t=18), Alexander(ℤ₃[i],t=i), Alexander(ℤ₇[i],t=i)) are dropped because every knot pair they uniquely witnessed is also distinguished by another retained quandle or by a cocycle invariant.

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

Both derive from **KnotInfo** (Livingston & Moore, <https://knotinfo.org>), which is publicly available; please cite KnotInfo if you reuse the data. `tools/knotinfo.py` regenerates `data/` from `tools/io/knotinfo.csv`.

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

| Result | Command | Runtime |
|---|---|---|
| All coloring counts (84 knots × 2,947 quandles) | `python3 tools/turbo_cli.py --data-dir data --max-crossings 9 -o tools/io/turbo_results.csv --overwrite` | ~18 s |
| Distinguished / unresolved pairs (3,484 and the 2 pairs) | `python3 tools/results.py` | <1 s |
| Minimum 14-quandle set (minimum set cover) | `python3 tools/minimal_set.py --solver ortools --max 1` | prints 14 in ~7 s; enumerating *all* optima runs much longer |
| Refine 14 → 9 with cocycle invariants | `python3 tools/compare_minimal_set.py` | ~1 min |

Notes:

- The first command reproduces `tools/io/turbo_results.csv` exactly (verified: 84 × 2,947 identical cells, 0 differing rows).
- `results.py` writes `tools/io/results.txt`, containing exactly the two unresolved pairs.
- `minimal_set.py` prints `Optimal size found: 14` in seconds; enumerating *all* optima is the slow part. The committed `minimal_set_raw.txt` used `--solver gurobi`. The optimum size (14) is solver-independent; which 14 quandles is not.
- `minimal_set.py` **overwrites** `tools/io/minimal_set.txt`. Back it up before running if you want to diff.
- `compare_minimal_set.py` checks whether each witness pair is *also* distinguished by quandles other than its own and its aliases. That strict criterion reports few "distinguished" pairs; the useful output is `Refinement Summary` (`Removable quandles: 5`, `Final set size: 14 -> 9`).
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

**Quandle selection** (`tools/minimal_set.py`). Each quandle induces a signature on the census. Choosing a small family that separates the most pairs is cast as **minimum set cover** and solved by integer programming (OR-Tools or Gurobi).

**Identification** (`logic/identifier.py`). `logic/signature_db.py` stores coloring counts for 16 quandles and matches an input diagram by signature. The 16 are the 14-quandle set plus `Dihedral(11)` and `Alexander(Z_11, t=8)`, added so prime knots do not collide with connected sums in drawing mode. This does not change the 14/9 results above.

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
  compare_minimal_set.py    Recheck witness pairs, refine 14 -> 9
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

The numbers in this repository come from a project report of the same title, which is not distributed here.

Please also cite [KnotInfo](https://knotinfo.org) for the knot data.

## License

Code: [Apache 2.0](LICENSE). Knot data derives from KnotInfo; see [Data](#data).

## Acknowledgements

Supervised by Prof. Marco Farinati (GTIIT). Knot data from KnotInfo (Livingston & Moore). Set cover solved with [OR-Tools](https://developers.google.com/optimization) and Gurobi.
