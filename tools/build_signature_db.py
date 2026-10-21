"""
Build the signature database for knot identification.

Generates logic/signature_db.py from the knot JSON files in data/.
Only uses valid quandles for the convention x ▷ y = t*x + (1-t)*y.
For Z_n types this means gcd(t, n) = 1, so right translations are bijective.
"""

import os
import sys
import json
import math
from collections import defaultdict

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
OUTPUT_PATH = os.path.join(PROJECT_DIR, 'logic', 'signature_db.py')
MAX_SIGNATURE_CROSSINGS = 9

sys.path.insert(0, os.path.join(PROJECT_DIR, 'logic'))
from solver import compute_quandle_colorings, dfs_solver


def generate_alexander_zn(n, t):
    """Alexander quandle over Z_n: x > y = t*x + (1-t)*y mod n."""
    elements = list(range(n))
    one_minus_t = (1 - t) % n
    op_table = []
    for x in elements:
        row = []
        for y in elements:
            row.append((t * x + one_minus_t * y) % n)
        op_table.append(row)
    return {"elements": elements, "operation_table": op_table}


def generate_alexander_zn_i(n, t_real, t_imag):
    """Alexander quandle over Z_n[i]: x > y = t*x + (1-t)*y."""
    size = n * n
    elements = list(range(size))

    def mul(u, v):
        a, b = u % n, u // n
        c, d = v % n, v // n
        real = (a * c - b * d) % n
        imag = (a * d + b * c) % n
        return imag * n + real

    def add(u, v):
        ra = (u % n + v % n) % n
        rb = (u // n + v // n) % n
        return rb * n + ra

    def sub(u, v):
        ra = (u % n - v % n) % n
        rb = (u // n - v // n) % n
        return rb * n + ra

    t_idx = t_imag * n + t_real
    one_minus_t = sub(1, t_idx)

    op_table = []
    for x in elements:
        row = []
        for y in elements:
            row.append(add(mul(t_idx, x), mul(one_minus_t, y)))
        op_table.append(row)
    return {"elements": elements, "operation_table": op_table}


def generate_alexander_f4(t_val):
    """F4 = F2[x]/(x^2+x+1): x > y = t*x + (1+t)*y (char 2)."""
    elements = [0, 1, 2, 3]
    mul_table = [
        [0, 0, 0, 0],
        [0, 1, 2, 3],
        [0, 2, 3, 1],
        [0, 3, 1, 2],
    ]
    add = lambda x, y: x ^ y
    mul = lambda x, y: mul_table[x][y]
    one_minus_t = add(1, t_val)
    op_table = []
    for x in elements:
        row = []
        for y in elements:
            row.append(add(mul(t_val, x), mul(one_minus_t, y)))
        op_table.append(row)
    return {"elements": elements, "operation_table": op_table}


def generate_alexander_f8(t_val):
    """F8 = F2[x]/(x^3+x+1), elements 0-7 as 3-bit vectors."""
    elements = list(range(8))

    def mul(a, b):
        res = 0
        for i in range(3):
            if (a >> i) & 1:
                for j in range(3):
                    if (b >> j) & 1:
                        res ^= (1 << (i + j))
        if (res >> 4) & 1:
            res ^= (1 << 4)
            res ^= 6
        if (res >> 3) & 1:
            res ^= (1 << 3)
            res ^= 3
        return res

    add = lambda x, y: x ^ y
    one_minus_t = add(1, t_val)
    op_table = []
    for x in elements:
        row = []
        for y in elements:
            row.append(add(mul(t_val, x), mul(one_minus_t, y)))
        op_table.append(row)
    return {"elements": elements, "operation_table": op_table}


# Quandle parameter definitions

ZN_QUANDLES = [
    # Representative 14-quandle coloring minimal set for prime knots with crossing number at most 9
    ("Dihedral(27)", 27, 26),
    ("Alexander(Z_29, t=3)", 29, 3),
    ("Dihedral(58)", 58, 57),
    ("Alexander(Z_69, t=20)", 69, 20),
    ("Dihedral(85)", 85, 84),
    ("Alexander(Z_91, t=6)", 91, 6),
    ("Alexander(Z_91, t=18)", 91, 18),
    ("Alexander(Z_91, t=48)", 91, 48),
    ("Dihedral(92)", 92, 91),
    ("Alexander(Z_95, t=17)", 95, 17),
    # Extra small quandles to avoid prime/composite signature collisions
    ("Dihedral(11)", 11, 10),
    ("Alexander(Z_11, t=8)", 11, 8),
]

DFS_QUANDLE_SPECS = [
    ("F4, t=a", 2, 2, 0, "f4"),
    ("Z3[i], t=i", 3, 0, 1, "zni"),
    ("Z7[i], t=i", 7, 0, 1, "zni"),
    ("Connected Quandle 6_1", 6, 0, 0, "table"),
]

CONNECTED_QUANDLE_6_1 = {
    "elements": [0, 1, 2, 3, 4, 5],
    "operation_table": [
        [0, 4, 0, 5, 1, 3],
        [4, 1, 5, 1, 0, 2],
        [2, 5, 2, 4, 3, 1],
        [5, 3, 4, 3, 2, 0],
        [1, 0, 3, 2, 4, 4],
        [3, 2, 1, 0, 5, 5],
    ],
}


def build_all_quandles():
    """Generate operation tables for all valid quandles."""
    quandles = []
    names = []
    sizes = []

    for name, n, t in ZN_QUANDLES:
        quandles.append(generate_alexander_zn(n, t))
        names.append(name)
        sizes.append(n)

    for spec in DFS_QUANDLE_SPECS:
        name, n, p1, p2, qtype = spec
        if qtype == "zni":
            quandles.append(generate_alexander_zn_i(n, p1, p2))
            sizes.append(n * n)
        elif qtype == "f4":
            quandles.append(generate_alexander_f4(p1))
            sizes.append(4)
        elif qtype == "f8":
            quandles.append(generate_alexander_f8(p1))
            sizes.append(8)
        elif qtype == "table":
            quandles.append(CONNECTED_QUANDLE_6_1)
            sizes.append(len(CONNECTED_QUANDLE_6_1["elements"]))
        names.append(name)

    return quandles, names, sizes


def snf_count(matrix, n):
    """Count solutions to Ax=0 mod n via Smith Normal Form."""
    if not matrix:
        return n
    A = [row[:] for row in matrix]
    nrows, ncols = len(A), len(A[0])
    for p in range(min(nrows, ncols)):
        for _ in range(500):
            min_val, min_pos = None, None
            for r in range(p, nrows):
                for c in range(p, ncols):
                    if A[r][c] != 0 and (min_val is None or abs(A[r][c]) < abs(min_val)):
                        min_val = A[r][c]
                        min_pos = (r, c)
            if min_pos is None:
                break
            r, c = min_pos
            if r != p:
                A[p], A[r] = A[r], A[p]
            if c != p:
                for row in A:
                    row[p], row[c] = row[c], row[p]
            if A[p][p] < 0:
                A[p] = [-x for x in A[p]]
            d = A[p][p]
            changed = False
            for r in range(nrows):
                if r != p and A[r][p] != 0:
                    q = A[r][p] // d
                    for k in range(ncols):
                        A[r][k] -= q * A[p][k]
                    if A[r][p] != 0:
                        changed = True
            for c in range(ncols):
                if c != p and A[p][c] != 0:
                    q = A[p][c] // d
                    for r in range(nrows):
                        A[r][c] -= q * A[r][p]
                    if A[p][c] != 0:
                        changed = True
            if not changed:
                break
    count = 1
    for i in range(ncols):
        if i < nrows and A[i][i] != 0:
            count *= math.gcd(abs(A[i][i]), n)
        else:
            count *= n
    return count


def compute_signature(knot, quandles, sizes):
    """Compute the coloring count signature for a knot."""
    arcs = knot['arcs']
    crossings = knot['crossings']
    arc_to_idx = {arc: i for i, arc in enumerate(arcs)}
    n_arcs = len(arcs)
    n_zn = len(ZN_QUANDLES)
    sig = []

    for i in range(len(quandles)):
        if i < n_zn:
            _, n, t = ZN_QUANDLES[i]
            if not crossings:
                sig.append(n)
                continue
            one_minus_t = 1 - t
            matrix = []
            for cr in crossings:
                row = [0] * n_arcs
                u_in = arc_to_idx[cr['under_in']]
                u_out = arc_to_idx[cr['under_out']]
                over = arc_to_idx[cr['over']]
                if cr['type'] == 'positive':
                    row[u_in] += t
                    row[over] += one_minus_t
                    row[u_out] -= 1
                else:
                    row[u_out] += t
                    row[over] += one_minus_t
                    row[u_in] -= 1
                matrix.append(row)
            sig.append(snf_count(matrix, n))
        else:
            if not crossings:
                sig.append(sizes[i])
                continue
            fixed_color_count = compute_quandle_colorings(
                quandles[i], knot, solver=dfs_solver, turbo=True
            )
            sig.append(fixed_color_count * sizes[i])

    return tuple(sig)


def extract_signatures(quandles, sizes):
    """Compute signatures for all prime knots up to MAX_SIGNATURE_CROSSINGS."""
    data_dir = os.path.join(PROJECT_DIR, 'data')
    knot_files = sorted([f for f in os.listdir(data_dir) if f.endswith('.json')])
    knot_files = [f for f in knot_files if int(f.split('_')[0]) <= MAX_SIGNATURE_CROSSINGS]

    prime_sigs = {}
    for f in knot_files:
        name = f.replace('.json', '')
        with open(os.path.join(data_dir, f)) as fp:
            knot = json.load(fp)
        prime_sigs[name] = compute_signature(knot, quandles, sizes)
        print(f"  {name}: {prime_sigs[name]}")

    return prime_sigs


def compute_composite_signatures(prime_sigs, sizes):
    """Compute theoretical signatures for composite knots up to MAX_SIGNATURE_CROSSINGS."""
    composites = {}
    sorted_primes = sorted(
        prime_sigs,
        key=lambda name: (int(name.split('_')[0]), int(name.split('_')[1])),
    )

    def signature_for_factors(factors):
        signature = []
        for i, size in enumerate(sizes):
            count = 1
            for factor in factors:
                count *= prime_sigs[factor][i]
            signature.append(count // (size ** (len(factors) - 1)))
        return tuple(signature)

    def add_factorizations(start_index, factors, crossing_sum):
        for index in range(start_index, len(sorted_primes)):
            name = sorted_primes[index]
            next_crossing_sum = crossing_sum + int(name.split('_')[0])
            if next_crossing_sum > MAX_SIGNATURE_CROSSINGS:
                break

            next_factors = factors + [name]
            if len(next_factors) >= 2:
                composites[" # ".join(next_factors)] = signature_for_factors(next_factors)

            add_factorizations(index, next_factors, next_crossing_sum)

    add_factorizations(0, [], 0)

    return composites


def verify_signatures(prime_sigs):
    """Check for collisions in the signature database."""
    sig_to_knots = defaultdict(list)
    for name, sig in prime_sigs.items():
        sig_to_knots[sig].append(name)
    return {sig: names for sig, names in sig_to_knots.items() if len(names) > 1}


def write_output(prime_sigs, composite_sigs, quandles, names, sizes):
    """Write the signature_db.py module."""
    lines = [
        '"""',
        'Signature database for knot identification.',
        'Auto-generated by tools/build_signature_db.py',
        '"""',
        '',
        f'QUANDLE_SIZES = {sizes}',
        '',
        'QUANDLE_NAMES = [',
    ]
    for name in names:
        lines.append(f'    "{name}",')
    lines.append(']')
    lines.append('')

    # Number of SNF quandles
    lines.append(f'N_SNF_QUANDLES = {len(ZN_QUANDLES)}')
    lines.append('')

    # SNF parameters
    zn_params = [(n, t) for _, n, t in ZN_QUANDLES]
    lines.append(f'ZN_PARAMS = {zn_params}')
    lines.append('')

    lines.append('QUANDLES = [')
    for q in quandles:
        lines.append(f'    {{"elements": {q["elements"]}, "operation_table": {q["operation_table"]}}},')
    lines.append(']')
    lines.append('')

    lines.append('PRIME_SIGNATURES = {')
    for name in sorted(prime_sigs, key=lambda x: (int(x.split("_")[0]), int(x.split("_")[1]))):
        lines.append(f'    "{name}": {prime_sigs[name]},')
    lines.append('}')
    lines.append('')

    lines.append('COMPOSITE_SIGNATURES = {')
    for name in sorted(composite_sigs):
        lines.append(f'    "{name}": {composite_sigs[name]},')
    lines.append('}')
    lines.append('')

    with open(OUTPUT_PATH, 'w') as f:
        f.write('\n'.join(lines))

    print(f"\nWritten {OUTPUT_PATH}")
    print(f"  {len(prime_sigs)} prime knot signatures")
    print(f"  {len(composite_sigs)} composite knot signatures")
    print(f"  {len(quandles)} quandle definitions ({len(ZN_QUANDLES)} SNF + {len(quandles)-len(ZN_QUANDLES)} DFS)")


if __name__ == '__main__':
    quandles, names, sizes = build_all_quandles()
    print(f"Built {len(quandles)} quandles")
    print("Computing signatures...")
    prime_sigs = extract_signatures(quandles, sizes)

    collisions = verify_signatures(prime_sigs)
    if collisions:
        print(f"\nWARNING: {len(collisions)} collision(s) found:")
        for sig, knot_names in collisions.items():
            print(f"  {knot_names}")
    else:
        print(f"\nAll {len(prime_sigs)} prime knots have unique signatures!")

    composite_sigs = compute_composite_signatures(prime_sigs, sizes)
    write_output(prime_sigs, composite_sigs, quandles, names, sizes)
