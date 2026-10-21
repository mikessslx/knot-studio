"""
Command-line version of the web turbo mode.

This mirrors the quandle list in static/script.js. Z_n and dihedral quandles are counted directly via Smith normal form so the command-line run stays light.

Usage:
  python3 tools/turbo_cli.py                                      # Generate tools/io/turbo_results_cli.csv
  python3 tools/turbo_cli.py -o tools/io/turbo_results.csv        # Write to a specific CSV file
  python3 tools/turbo_cli.py --data-dir data                      # Read knot JSON files from a directory
  python3 tools/turbo_cli.py --max-crossings 9                    # Only process knots with <= 9 crossings
  python3 tools/turbo_cli.py --only-knots 3_1,4_1                 # Only process selected knots
  python3 tools/turbo_cli.py --limit-knots 5 --limit-quandles 20  # Quick debug run
  python3 tools/turbo_cli.py -o tools/io/turbo_results.csv --overwrite # Replace an existing CSV
  python3 tools/turbo_cli.py -o tools/io/turbo_results.csv --resume # Append missing knot rows
"""

import argparse
import csv
import itertools
import json
import math
import os
import sys
import time


SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
LOGIC_DIR = os.path.join(PROJECT_DIR, "logic")
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)
if LOGIC_DIR not in sys.path:
    sys.path.insert(0, LOGIC_DIR)

from solver import compute_quandle_colorings, dfs_solver, _build_linear_matrix, _snf_solution_count
from build_signature_db import (
    generate_alexander_f4,
    generate_alexander_f8,
    generate_alexander_zn_i,
)


ZNI_CONFIGS = {
    3: [("i", 0, 1), ("1+i", 1, 1), ("2", 2, 0), ("2+i", 2, 1)],
    5: [("2i", 0, 2), ("1+i", 1, 1), ("2", 2, 0), ("2+2i", 2, 2), ("4", 4, 0)],
    7: [("i", 0, 1), ("2i", 0, 2), ("1+i", 1, 1), ("2", 2, 0), ("3", 3, 0)],
}


def is_prime_power(n):
    if n <= 1:
        return False
    temp = n
    divisor = 2
    while divisor * divisor <= temp:
        if temp % divisor == 0:
            break
        divisor += 1
    if temp % divisor != 0:
        return True
    while temp > 1 and temp % divisor == 0:
        temp //= divisor
    return temp == 1


def generate_conjugation(n):
    perms = list(itertools.permutations(range(n)))
    perm_to_index = {perm: index for index, perm in enumerate(perms)}

    def multiply(p1, p2):
        return tuple(p1[value] for value in p2)

    def inverse(p):
        inv = [0] * len(p)
        for index, value in enumerate(p):
            inv[value] = index
        return tuple(inv)

    op_table = []
    for x in perms:
        row = []
        for y in perms:
            result = multiply(multiply(y, x), inverse(y))
            row.append(perm_to_index[result])
        op_table.append(row)

    return {"elements": list(range(len(perms))), "operation_table": op_table}


def load_connected_quandles():
    path = os.path.join(PROJECT_DIR, "static", "quandle.json")
    with open(path) as f:
        raw_quandles = json.load(f)

    specs = []
    for item in raw_quandles:
        quandle = item["data"]
        quandle["name"] = item["label"]
        specs.append({
            "name": item["label"],
            "kind": "table",
            "quandle": quandle,
            "size": len(quandle["elements"]),
        })
    return specs


def make_table_spec(name, quandle):
    return {
        "name": name,
        "kind": "table",
        "quandle": quandle,
        "size": len(quandle["elements"]),
    }


def build_quandle_specs():
    specs = []
    for n in range(3, 100):
        # if not (n < 30 or is_prime_power(n)):
        #     continue

        specs.append({
            "name": f"Dihedral({n})",
            "kind": "zn",
            "n": n,
            "t": n - 1,
            "size": n,
        })

        for t in range(2, n - 1):
            if math.gcd(n, t) == 1:
                specs.append({
                    "name": f"Alexander(Z{n}, t={t})",
                    "kind": "zn",
                    "n": n,
                    "t": t,
                    "size": n,
                })

    specs.append(make_table_spec("Alexander(F4, t=\u03b1)", generate_alexander_f4(2)))
    specs.append(make_table_spec("Alexander(F8, t=\u03b1)", generate_alexander_f8(2)))
    specs.append(make_table_spec("Alexander(F8, t=\u03b1+1)", generate_alexander_f8(3)))

    for n, configs in ZNI_CONFIGS.items():
        for label, real, imag in configs:
            specs.append(make_table_spec(
                f"Alexander(Z{n}[i], t={label})",
                generate_alexander_zn_i(n, real, imag),
            ))

    specs.append(make_table_spec("Conjugation(S3)", generate_conjugation(3)))
    specs.append(make_table_spec("Conjugation(S4)", generate_conjugation(4)))
    specs.extend(load_connected_quandles())
    return specs


def load_knots(data_dir, max_crossings, only_knots=None, limit=None):
    only = None
    if only_knots:
        only = {name.strip().replace(".json", "") for name in only_knots.split(",") if name.strip()}

    files = []
    for filename in os.listdir(data_dir):
        if not filename.endswith(".json"):
            continue
        name = filename[:-5]
        crossing_text = name.split("_", 1)[0]
        if not crossing_text.isdigit():
            continue
        if max_crossings is not None and int(crossing_text) > max_crossings:
            continue
        if only is not None and name not in only:
            continue
        files.append(filename)

    files.sort()

    if limit is not None:
        files = files[:limit]

    knots = []
    for filename in files:
        with open(os.path.join(data_dir, filename)) as f:
            knots.append((filename, json.load(f)))
    return knots


def table_count(knot, spec):
    fixed_count = compute_quandle_colorings(
        spec["quandle"],
        knot,
        solver=dfs_solver,
        turbo=True,
    )
    return fixed_count * spec["size"]


def snf_count_colorings(knot, n, t, matrix_cache):
    """Count all colorings for a Z_n Alexander/dihedral quandle."""
    if t not in matrix_cache:
        matrix_cache[t] = _build_linear_matrix(knot, n, t, modulo=False)
    return _snf_solution_count(
        matrix_cache[t],
        n,
        len(knot["arcs"]),
    )


def count_colorings(knot, spec, matrix_cache):
    if spec["kind"] == "zn":
        return snf_count_colorings(knot, spec["n"], spec["t"], matrix_cache)
    return table_count(knot, spec)


def write_turbo_csv(args):
    data_dir = os.path.abspath(args.data_dir)
    output_path = os.path.abspath(args.output)

    if os.path.exists(output_path) and not args.overwrite and not args.resume:
        raise SystemExit(
            f"Output already exists: {output_path}\n"
            "Use --overwrite to replace it, or --resume to append missing knots."
        )

    specs = build_quandle_specs()
    if args.limit_quandles is not None:
        specs = specs[:args.limit_quandles]

    knots = load_knots(
        data_dir,
        max_crossings=args.max_crossings,
        only_knots=args.only_knots,
        limit=args.limit_knots,
    )
    if not knots:
        raise SystemExit(f"No knot JSON files found in {data_dir}.")

    fieldnames = ["Knot"] + [spec["name"] for spec in specs]
    completed = set()
    mode = "w"

    if args.resume and os.path.exists(output_path):
        with open(output_path, newline="") as f:
            reader = csv.DictReader(f)
            existing_fieldnames = reader.fieldnames
            if existing_fieldnames != fieldnames:
                raise SystemExit("Cannot resume: existing CSV header does not match this run.")
            completed = {row["Knot"] for row in reader}
        mode = "a"

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    print(f"Quandles: {len(specs)}")
    print(f"Knots: {len(knots)} loaded from {data_dir}")
    print(f"Output: {output_path}")

    start_all = time.time()
    with open(output_path, mode, newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        if mode == "w":
            writer.writeheader()

        pending = [(name, knot) for name, knot in knots if name not in completed]
        for index, (filename, knot) in enumerate(pending, 1):
            row_start = time.time()
            row = {"Knot": filename}
            matrix_cache = {}
            for spec in specs:
                row[spec["name"]] = count_colorings(knot, spec, matrix_cache)
            writer.writerow(row)
            f.flush()

            elapsed = time.time() - row_start
            print(f"[{index}/{len(pending)}] {filename} ({elapsed:.2f}s)", flush=True)

    print(f"Done in {time.time() - start_all:.2f}s.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate the web turbo mode coloring-count CSV with CLI."
    )
    parser.add_argument(
        "--data-dir",
        default=os.path.join(PROJECT_DIR, "data"),
        help="Directory containing knot JSON files.",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=os.path.join(SCRIPT_DIR, "io", "turbo_results_cli.csv"),
        help="CSV output path.",
    )
    parser.add_argument("--max-crossings", type=int, default=10)
    parser.add_argument("--only-knots", help="Comma-separated knot names, e.g. 3_1,4_1.")
    parser.add_argument("--limit-knots", type=int, help="Debug helper: only process the first N knots.")
    parser.add_argument("--limit-quandles", type=int, help="Debug helper: only process the first N quandles.")
    parser.add_argument("--overwrite", action="store_true", help="Replace an existing output file.")
    parser.add_argument("--resume", action="store_true", help="Append missing knot rows to an existing CSV.")
    return parser.parse_args()


if __name__ == "__main__":
    write_turbo_csv(parse_args())
