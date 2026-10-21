"""
6. Recompute cocycles and solve set cover over every census knot pair.
"""

import argparse
import csv
import itertools
import json
from pathlib import Path

import compare
from minimal_set import solve_ortools, solve_scipy
from turbo_cli import build_quandle_specs

IO_DIR = Path(__file__).resolve().parent / 'io'
PUBLISHED_NINE = [
    'Dihedral(27)', 'Alexander(Z29, t=3)', 'Alexander(Z69, t=20)',
    'Dihedral(85)', 'Alexander(Z91, t=48)', 'Dihedral(92)',
    'Alexander(Z95, t=17)', 'Alexander(F4, t=α)', 'Connected Quandle 6_1',
]


def count_bits(mask):
    return bin(mask).count('1')


def pair_mask(values, pairs):
    return sum(1 << p for p, (i, j) in enumerate(pairs) if values[i] != values[j])


def minimum_cover(coverage, solver_name='ortools'):
    """
    Count each quandle supplying either colorings or cocycles once.
    """
    aliases = {}
    for name, mask in coverage.items():
        if mask:
            aliases.setdefault(mask, []).append(name)
    masks = list(aliases)
    target = 0
    for mask in masks:
        target |= mask
    covering = {}
    for j, mask in enumerate(masks):
        while mask:
            bit = mask & -mask
            covering.setdefault(bit.bit_length() - 1, []).append(j)
            mask ^= bit
    selections = []
    solve = solve_scipy if solver_name == 'scipy' else solve_ortools
    solve(len(masks), covering, max=1, callback=selections.append)
    if not selections:
        raise RuntimeError('No set-cover solution was returned.')
    selected = [aliases[masks[j]][0] for j in selections[0]]
    actual = 0
    for name in selected:
        actual |= coverage[name]
    if actual != target:
        raise RuntimeError('The selected family does not cover every target pair.')
    return selected, target, [aliases[masks[j]][1:] for j in selections[0]]


def recompute(csv_path, output_dir, solver_name='ortools'):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    with open(csv_path, newline='') as stream:
        reader = csv.DictReader(stream)
        names = reader.fieldnames[1:]
        rows = list(reader)
    knots = [row['Knot'].replace('.json', '') for row in rows]
    pairs = list(itertools.combinations(range(len(knots)), 2))
    counts = {name: [int(row[name]) for row in rows] for name in names}
    coloring_coverage = {name: pair_mask(counts[name], pairs) for name in names}
    coloring_set, coloring_target, _ = minimum_cover(coloring_coverage, solver_name)

    quandles = compare.get_quandles()
    seen = {q['name'] for q in quandles}

    for spec in build_quandle_specs():
        if (spec['kind'] == 'table' and spec['size'] <= 9
                and spec['name'].startswith('Alexander(') and spec['name'] not in seen):
            quandles.append(dict(spec['quandle'], name=spec['name']))
            seen.add(spec['name'])
    unique_quandles = {}
    for quandle in quandles:
        name = compare.map_quandle_name_to_csv(quandle['name'])
        previous = unique_quandles.get(name)
        if previous is not None and previous['operation_table'] != quandle['operation_table']:
            raise ValueError(f'Conflicting operation tables for {name}.')
        unique_quandles.setdefault(name, quandle)
    quandles = list(unique_quandles.values())
    groups = compare.FAST_MODE_GROUP_SIZES
    data = {name: compare.load_knot_data(name) for name in knots}
    compare.clear_caches()
    invariants = compare.compute_all_invariants_for_knots(
        data, quandles, groups, turbo_cache=compare.load_turbo_results(csv_path),
    )
    coverage = coloring_coverage.copy()
    cocycle_data = []
    for quandle in quandles:
        q_name = quandle['name']
        csv_name = compare.map_quandle_name_to_csv(q_name)
        if csv_name not in coverage:
            raise ValueError(f'No coloring column for {q_name}.')
        for i, name in enumerate(knots):
            actual = invariants[name].get((q_name, 'coloring_count'))
            expected = counts[csv_name][i]
            if actual != expected:
                raise ValueError(f'Coloring disagreement: {name}, {q_name}: {actual} != {expected}')
        for group in groups:
            cocycles = compare.COCYCLE_CACHE.get((q_name, group))
            if cocycles is None or len(cocycles) > 10000:
                continue
            op = quandle['operation_table']
            n = len(op)
            for phi in cocycles:
                if any(phi[x][x] % group for x in range(n)) or any(
                    (phi[x][y] + phi[op[x][y]][z] - phi[x][z] - phi[op[x][z]][op[y][z]]) % group
                    for x, y, z in itertools.product(range(n), repeat=3)
                ):
                    raise ValueError(f'Invalid cocycle generated for {q_name} over Z_{group}.')
            values = []
            for i, name in enumerate(knots):
                value = invariants[name].get((q_name, group))
                if value is None:
                    if counts[csv_name][i] != n:
                        raise ValueError(f'Missing nonconstant invariant: {name}, {q_name}, Z_{group}')
                    value = [str(n)] * len(cocycles)
                values.append(value)
            coverage[csv_name] |= pair_mask(values, pairs)
            cocycle_data.append({
                'quandle': csv_name, 'group_size': group,
                'cocycles': cocycles, 'polynomials_by_knot': dict(zip(knots, values)),
            })
    same_coverage_selected, _, _ = minimum_cover(
        {name: mask & coloring_target for name, mask in coverage.items()}, solver_name,
    )
    selected, target, selected_aliases = minimum_cover(coverage, solver_name)
    old_mask = 0
    for name in PUBLISHED_NINE:
        old_mask |= coverage[name]

    def knot_pairs(mask):
        return [[knots[i], knots[j]] for p, (i, j) in enumerate(pairs) if mask & (1 << p)]

    all_pairs = (1 << len(pairs)) - 1
    summary = {
        'knot_count': len(knots), 'quandle_count': len(names), 'pair_count': len(pairs),
        'coloring_distinguished_pairs': count_bits(coloring_target),
        'coloring_minimum_size': len(coloring_set), 'coloring_selected': coloring_set,
        'same_coverage_combined_minimum_size': len(same_coverage_selected),
        'same_coverage_combined_selected': same_coverage_selected,
        'cocycle_group_sizes': groups,
        'cocycle_quandles': sorted({item['quandle'] for item in cocycle_data}),
        'cocycle_evaluations': len(cocycle_data),
        'combined_distinguished_pairs': count_bits(target),
        'combined_minimum_size': len(selected), 'combined_selected': selected,
        'combined_aliases': selected_aliases,
        'unresolved_pairs': knot_pairs(all_pairs ^ target),
        'newly_distinguished_pairs': knot_pairs(target & ~coloring_target),
        'published_nine': PUBLISHED_NINE,
        'published_nine_uncovered_pairs': knot_pairs(target & ~old_mask),
        'solver': solver_name, 'optimum_proved': True,
    }
    (output_dir / 'refinement_summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    (output_dir / 'cocycle_results.json').write_text(json.dumps(cocycle_data, indent=2) + '\n')
    lines = [
        f"Distinguishing {count_bits(target)} pairs from {len(knots)} knots...",
        f'Solver: {solver_name}; optimum proved; all pairs verified', '', 'Solution #1:',
    ]
    for index, (name, aliases) in enumerate(zip(selected, selected_aliases), 1):
        others = 0
        for other in selected:
            if other != name:
                others |= coverage[other]
        unique = coverage[name] & ~others
        line = f'{index}. {name} (total {count_bits(coverage[name])}, unique {count_bits(unique)})'
        if aliases:
            line += f" (or {', '.join(aliases)})"
        lines.append(line)
        lines.extend(f'   {a}, {b}' for a, b in knot_pairs(unique))
    lines.extend([
        '', f'Coloring-only minimum: {len(coloring_set)}',
        f'Combined minimum preserving coloring coverage: {len(same_coverage_selected)}',
        f'Combined minimum for the evaluated tests: {len(selected)}',
        'Unresolved pairs: ' + '; '.join(', '.join(pair) for pair in summary['unresolved_pairs']),
    ])
    (output_dir / 'minimal_set.txt').write_text('\n'.join(lines) + '\n')
    compare.clear_caches()
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=IO_DIR / 'turbo_results.csv')
    parser.add_argument('--output-dir', type=Path, default=IO_DIR)
    parser.add_argument('--solver', choices=['ortools', 'scipy'], default='ortools')
    args = parser.parse_args()
    recompute(args.csv, args.output_dir, args.solver)
