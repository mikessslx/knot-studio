"""
1. Regression checks for crossing weights, total counts and full-pair cover.
"""

import contextlib
import csv
import io
import itertools
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'logic'), str(ROOT / 'tools')]
os.environ['PUBLIC_DEMO_MODE'] = '0'

import cocycle
import solver
from turbo_cli import generate_conjugation
from turbo import turbo_ipynb

PHI = [[0, 0, 1, 0], [1, 0, 1, 1], [0, 0, 0, 1], [1, 0, 0, 0]]
QUANDLE = next(q['data'] for q in json.loads((ROOT / 'static/quandle.json').read_text())
               if q['id'] == 'connected_4_1')
RII = {'arcs': [0, 1, 2], 'crossings': [
    {'type': 'positive', 'over': 2, 'under_in': 0, 'under_out': 1},
    {'type': 'negative', 'over': 2, 'under_in': 1, 'under_out': 0},
]}


def knot(name):
    return json.loads((ROOT / 'data' / (name + '.json')).read_text())


def scalar_weights(diagram, colorings, phi, modulus):
    return [sum(
        (phi[c[cr['under_in']]][c[cr['over']]] if cr['type'] == 'positive'
         else -phi[c[cr['under_out']]][c[cr['over']]])
        for cr in diagram['crossings']) % modulus for c in colorings]


class CocycleTests(unittest.TestCase):
    def test_fixed_cocycle_distinguishes_seven_four_and_nine_two(self):
        import compare
        item = next(v for v in json.loads((ROOT / 'tools/io/cocycle_results.json').read_text())
                    if v['quandle'] == 'Connected Quandle 9_7' and v['group_size'] == 3)
        q = next(q['data'] for q in json.loads((ROOT / 'static/quandle.json').read_text())
                 if q['id'] == 'connected_9_7')
        phi = item['cocycles'][1]
        values = []
        for name in ['7_4', '9_2']:
            diagram = knot(name)
            cols = solver.dfs_solver(q, diagram)
            propagated = solver.propagation_solver(q, diagram)
            freeze = lambda colorings: {tuple(c[a] for a in diagram['arcs']) for c in colorings}
            self.assertEqual(freeze(cols), freeze(propagated))
            actual = cocycle.compute_cocycle_invariant(diagram, q, phi, 3, cols)
            self.assertEqual(actual['raw_weights'], scalar_weights(diagram, cols, phi, 3))
            self.assertEqual(len(cols), 81)
            values.append(actual['polynomial'])
        self.assertEqual(set(values), {'27 + 54t', '27 + 54t^2'})
        self.assertEqual(set(item['polynomials_by_knot']['7_4']), set(item['polynomials_by_knot']['9_2']))
        mapping = {name: {('Connected Quandle 9_7', 3): item['polynomials_by_knot'][name]} for name in ['7_4', '9_2']}
        self.assertTrue(compare.compare_pair_fast('7_4', '9_2', mapping, [{'name': 'Connected Quandle 9_7'}], [3])[0])

    def test_reidemeister_two_even_and_odd_coefficients(self):
        # A genuine cocycle over Z_2, then a coboundary over Z_5
        op = QUANDLE['operation_table']
        coboundary = [[(x - op[x][y]) % 5 for y in range(4)] for x in range(4)]
        for phi, modulus in [(PHI, 2), (coboundary, 5)]:
            with self.subTest(modulus=modulus):
                result = cocycle.compute_cocycle_invariant(RII, QUANDLE, phi, modulus)
                batch = cocycle.compute_all_cocycle_invariant(RII, QUANDLE, modulus, [phi])[0]
                self.assertEqual(result['weights'], {0: 16})
                self.assertEqual(batch['raw_weights'], result['raw_weights'])

    def test_all_census_weights_match_scalar_reference(self):
        for path in sorted((ROOT / 'data').glob('*.json')):
            if int(path.stem.split('_')[0]) > 9:
                continue
            diagram = json.loads(path.read_text())
            cols = solver.compute_quandle_colorings(QUANDLE, diagram, solver=solver.dfs_solver)
            single = cocycle.compute_cocycle_invariant(diagram, QUANDLE, PHI, 2, cols)
            batch = cocycle.compute_all_cocycle_invariant(diagram, QUANDLE, 2, [PHI], cols)[0]
            with self.subTest(knot=path.stem):
                self.assertEqual(single['raw_weights'], scalar_weights(diagram, cols, PHI, 2))
                self.assertEqual(batch['raw_weights'], single['raw_weights'])
                self.assertEqual(sum(single['weights'].values()), len(cols))
                op = QUANDLE['operation_table']
                coboundary = [[(x - op[x][y]) % 3 for y in range(4)] for x in range(4)]
                result = cocycle.compute_cocycle_invariant(diagram, QUANDLE, coboundary, 3, cols)
                self.assertEqual(result['weights'], {0: len(cols)})
        self.assertEqual(cocycle.compute_cocycle_invariant(knot('8_10'), QUANDLE, PHI, 2)['polynomial'], '16')
        self.assertEqual(cocycle.compute_cocycle_invariant(knot('8_1'), QUANDLE, PHI, 2)['polynomial'], '4 + 12t')

    def test_linear_cocycles_match_exhaustive_enumeration(self):
        op = [[(2 * y - x) % 3 for y in range(3)] for x in range(3)]
        for modulus in [2, 3]:
            actual = cocycle.compute_cocycle(op, modulus, just_reps=False)
            expected = cocycle.compute_cocycle(op, modulus, solver=cocycle.enum_cocycle_solver)
            freeze = lambda matrices: {tuple(v for row in phi for v in row) for phi in matrices}
            self.assertEqual(freeze(actual), freeze(expected))

    def test_empty_colorings_and_no_crossings(self):
        empty = cocycle.compute_cocycle_invariant(RII, QUANDLE, PHI, 2, [])
        self.assertEqual(empty['total_colorings'], 0)
        self.assertEqual(empty['raw_weights'], [])
        batch = cocycle.compute_all_cocycle_invariant(RII, QUANDLE, 2, [PHI], [])[0]
        self.assertEqual(batch['total_colorings'], 0)
        self.assertEqual(batch['raw_weights'], [])
        unknot = {'arcs': [10], 'crossings': []}
        self.assertEqual(cocycle.compute_cocycle_invariant(unknot, QUANDLE, PHI, 2)['weights'], {0: 4})
        with self.assertRaises(ValueError):
            cocycle.compute_cocycle_invariant(RII, QUANDLE, PHI, 0)

    def test_nonzero_single_weight_is_nontrivial(self):
        diagram = knot('3_1')
        cols = solver.dfs_solver(QUANDLE, diagram)
        chosen = next(c for c, w in zip(cols, scalar_weights(diagram, cols, PHI, 2)) if w)
        result = cocycle.compute_cocycle_invariant(diagram, QUANDLE, PHI, 2, [chosen])
        self.assertFalse(result['is_trivial'])

    def test_noninteger_color_labels_and_sparse_arc_ids(self):
        labels = ['a', 'b', 'c', 'd']
        q = {'elements': labels, 'operation_table': [[labels[v] for v in row] for row in QUANDLE['operation_table']]}
        diagram = {'arcs': [10, 20, 30], 'crossings': [
            dict(cr, **{key: [10, 20, 30][cr[key]] for key in ['under_in', 'under_out', 'over']})
            for cr in RII['crossings']]}
        self.assertEqual(cocycle.compute_cocycle_invariant(diagram, q, PHI, 2)['weights'], {0: 16})


class CountTests(unittest.TestCase):
    def test_conjugation_columns_match_full_enumeration(self):
        with (ROOT / 'tools/io/turbo_results.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        for n in [3, 4]:
            q = generate_conjugation(n)
            for row in rows:
                diagram = knot(row['Knot'].replace('.json', ''))
                with self.subTest(n=n, knot=row['Knot']):
                    self.assertEqual(len(solver.dfs_solver(q, diagram)), int(row[f'Conjugation(S{n})']))

    def test_nontransitive_conjugation_counts(self):
        for n, name, expected in [(3, '3_1', 12), (4, '3_1', 96), (4, '4_1', 48)]:
            q = generate_conjugation(n)
            diagram = knot(name)
            enumerated = solver.compute_quandle_colorings(q, diagram, solver=solver.enum_solver)
            self.assertEqual(len(enumerated), expected)
            for method in [solver.dfs_solver, solver.algebraic_solver, solver.propagation_solver, solver.linear_solver, solver.snf_solver]:
                with self.subTest(n=n, knot=name, method=method.__name__):
                    self.assertEqual(solver.count_quandle_colorings(q, diagram, solver=method), expected)

    def test_disconnected_alexander_counts(self):
        q = {'elements': list(range(4)), 'operation_table': [[(2 * y - x) % 4 for y in range(4)] for x in range(4)]}
        for diagram in [RII, knot('3_1'), knot('4_1')]:
            self.assertEqual(solver.count_quandle_colorings(q, diagram), len(solver.enum_solver(q, diagram)))

    def test_api_and_notebook_use_total_counts(self):
        import app
        q = dict(generate_conjugation(3), name='Conjugation(S3)')
        with app.app.test_client() as client:
            response = client.post('/api/turbo_calculate', json={
                'knot_files': ['3_1.json'], 'quandles': [q], 'method': 'dfs', 'turbo': True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()['results']['3_1.json'][q['name']]['count'], 12)
            response = client.post('/api/cocycle_invariant', json={
                'knot': knot('8_10'), 'quandle': QUANDLE, 'cocycle': PHI, 'group_size': 2})
            self.assertEqual(response.get_json()['polynomial'], '16')
        notebook = turbo_ipynb(['3_1.json'], [q], method='dfs', turbo=True)
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                Path('data').mkdir()
                Path('data/3_1.json').write_text(json.dumps(knot('3_1')))
                namespace = {'__name__': '__main__'}
                with contextlib.redirect_stdout(io.StringIO()):
                    for cell in notebook['cells']:
                        if cell['cell_type'] == 'code' and cell['id'] in ['cell-solver', 'cell-main']:
                            exec(''.join(cell['source']), namespace)
                with open('turbo_results.csv') as stream:
                    self.assertEqual(int(next(csv.DictReader(stream))[q['name']]), 12)
            finally:
                os.chdir(previous)

    def test_cover_checks_joint_deletions_and_provider_cost(self):
        from compare_minimal_set import minimum_cover
        backend = 'ortools' if importlib.util.find_spec('ortools') else 'scipy'
        with contextlib.redirect_stdout(io.StringIO()):
            selected, target, _ = minimum_cover({'A': 0b011, 'B': 0b101, 'C': 0b110}, backend)
        self.assertEqual(len(selected), 2)
        self.assertEqual(target, 0b111)

    def test_saved_families_cover_the_complete_census(self):
        summary = json.loads((ROOT / 'tools/io/refinement_summary.json').read_text())
        cocycles = json.loads((ROOT / 'tools/io/cocycle_results.json').read_text())
        with (ROOT / 'tools/io/turbo_results.csv').open() as stream:
            rows = list(csv.DictReader(stream))
        for kind, expected in [('coloring', 3484), ('combined', 3485)]:
            selected = summary[kind + '_selected']
            self.assertEqual(len(selected), 13)
            signatures = []
            for row in rows:
                signature = [row[name] for name in selected]
                if kind == 'combined':
                    for item in cocycles:
                        if item['quandle'] in selected:
                            signature.extend(item['polynomials_by_knot'][row['Knot'].replace('.json', '')])
                signatures.append(tuple(signature))
            self.assertEqual(sum(a != b for a, b in itertools.combinations(signatures, 2)), expected)
        self.assertEqual(summary['unresolved_pairs'], [['8_14', '9_8']])


if __name__ == '__main__':
    unittest.main()
