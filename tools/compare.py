"""
4. Compare knots using quandle colorings and cocycle invariants.
"""

import math
import time
import json
import sys
import os
import argparse
import itertools
import csv
from typing import List, Dict, Tuple, Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../logic')))

from cocycle import compute_all_cocycle_invariant, compute_cocycle, linear_cocycle_solver
from solver import compute_quandle_colorings, linear_solver

DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../data'))
FAST_MODE = True
FAST_MODE_MAX_DIHEDRAL = 10
FAST_MODE_GROUP_SIZES = [2, 3, 5, 7]
FULL_GROUP_SIZES = [2, 3, 5, 7, 11, 13, 17, 19, 23, 29]

# Cache computed cocycles and colorings
COCYCLE_CACHE = {}
COLORING_CACHE = {}

def clear_caches():
    """Clear global caches to free memory."""
    COCYCLE_CACHE.clear()
    COLORING_CACHE.clear()

def get_available_knots() -> List[str]:
    """Retrieve all available knot names from the data directory."""
    knots = []
    if not os.path.exists(DATA_DIR):
        print(f"Warning: Data directory not found: {DATA_DIR}")
        return []
        
    for f in os.listdir(DATA_DIR):
        if f.endswith('.json'):
            knots.append(f[:-5])
    return sorted(knots)

def get_quandles() -> List[Dict]:
    """Return a list of predefined quandles for testing."""
    quandles = []

    def is_prime(num):
        if num < 2: return False
        for i in range(2, int(math.sqrt(num)) + 1):
            if num % i == 0:
                return False
        return True

    # 1. Build dihedral quandles
    dihedral = [n for n in range(4, 30) if not is_prime(n)]
    if FAST_MODE:
        dihedral = [n for n in dihedral if n <= FAST_MODE_MAX_DIHEDRAL]
    
    for n in dihedral:
        elements = list(range(n))
        op_table = []
        for x in elements:
            row = []
            for y in elements:
                # 2y - x (mod n)
                res = (2 * y - x) % n
                row.append(res)
            op_table.append(row)
        quandles.append({
            'name': f'Dihedral_{n}',
            'elements': elements,
            'operation_table': op_table
        })

    # 2. Build Alexander quandles
    alex = [n for n in range(4, 10) if not is_prime(n)]
    
    for n in alex:
        units = [t for t in range(2, n) if math.gcd(n, t) == 1]
        
        for t in units:
            elements = list(range(n))
            omt = (1 - t) % n
            op_table = [[(t*x + omt*y) % n for y in range(n)] for x in range(n)]
            quandles.append({
                'name': f'Alexander_Z{n}_t{t}',
                'elements': elements,
                'operation_table': op_table
            })

    # 3. Load connected quandles
    try:
        json_path = os.path.join(os.path.dirname(__file__), '../static/quandle.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                conn_data = json.load(f)
            
            for q_data in conn_data:
                q = {
                    'name': q_data['label'],
                    'elements': q_data['data']['elements'],
                    'operation_table': q_data['data']['operation_table']
                }
                quandles.append(q)
    except Exception as e:
        print(f"Warning: Failed to load connected quandles: {e}", flush=True)

    return quandles

def load_knot_data(name: str) -> Dict:
    """Load knot data from JSON file."""
    filepath = os.path.join(DATA_DIR, f'{name}.json')
    if not os.path.exists(filepath):
        raise ValueError(f"Knot data not found: {name}")
    with open(filepath, 'r') as f:
        return json.load(f)

def get_cached_cocycles(quandle: Dict, group_size: int):
    """Get cocycles from cache or compute them."""
    key = (quandle['name'], group_size)
    if key not in COCYCLE_CACHE:
        # Convert operation table values to index form
        elements = quandle['elements']
        elem_to_idx = {e: i for i, e in enumerate(elements)}
        op_table = [[elem_to_idx[val] for val in row] for row in quandle['operation_table']]
        
        # Cache representative cocycles
        COCYCLE_CACHE[key] = compute_cocycle(op_table, group_size, solver=linear_cocycle_solver, just_representatives=True)
        
    return COCYCLE_CACHE[key]

def get_cached_colorings(knot_name: str, knot_data: Dict, quandle: Dict):
    """Get colorings from cache or compute them."""
    key = (knot_name, quandle['name'])
    if key not in COLORING_CACHE:
        COLORING_CACHE[key] = compute_quandle_colorings(quandle, knot_data, solver=linear_solver)
    return COLORING_CACHE[key]

def load_turbo_results() -> Dict[str, Dict[str, int]]:
    """Load pre-computed coloring results from CSV."""
    csv_path = os.path.join(os.path.dirname(__file__), 'io/turbo_results.csv')
    if not os.path.exists(csv_path):
        print(f"Warning: {csv_path} not found. Skipping.", flush=True)
        return {}

    mapping = {}
    try:
        with open(csv_path, 'r', newline='') as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            for row in reader:
                knot_name = row['Knot'].replace('.json', '')
                knot_map = {}
                for field in fields[1:]:
                    val = row.get(field)
                    if val:
                        try:
                            knot_map[field] = int(val)
                        except ValueError:
                            pass
                mapping[knot_name] = knot_map
    except Exception as e:
        print(f"Error: Failed to load turbo results: {e}", flush=True)
        return {}
    return mapping

def map_quandle_name_to_csv(name: str) -> str:
    """Map internal quandle name to CSV header format."""
    # Convert Dihedral_* to Dihedral(*)
    if name.startswith('Dihedral_'):
        n = name.split('_')[1]
        return f"Dihedral({n})"
    
    # Convert Alexander_* to Alexander(*, t=*)
    if name.startswith('Alexander_'):
        parts = name.split('_')
        zn = parts[1]
        t_val = parts[2][1:]
        return f"Alexander({zn}, t={t_val})"
    
    return name

def compute_all_invariants_for_knots(knots_data_map: Dict, quandles: List[Dict], group_sizes: List[int]) -> Dict:
    """Computes invariants for all knots efficiently."""
    results = {k: {} for k in knots_data_map}
    
    # Reuse precomputed coloring counts when available
    turbo_cache = load_turbo_results()
    
    total_steps = len(quandles)
    for idx, q in enumerate(quandles):
        q_name = q['name']
        q_csv_name = map_quandle_name_to_csv(q_name)
        q_size = len(q['elements'])
        
        print(f"[{idx+1}/{total_steps}] Computing invariants for {q_name}...", flush=True)
        
        # 1. Compute colorings for knots that are not trivially filtered
        current_colorings = {} 
        
        knots_to_compute = []
        
        for k_name in knots_data_map:
            # Skip knots with trivial known coloring counts
            if k_name in turbo_cache:
                known_count = turbo_cache[k_name].get(q_csv_name)
                if known_count is not None and known_count <= q_size:
                    results[k_name][(q_name, 'coloring_count')] = known_count
                    if known_count == 0:
                         current_colorings[k_name] = []
                    continue
            
            knots_to_compute.append(k_name)

        if not knots_to_compute:
            print("Skipped all knots (all trivial colorings).", flush=True)
            continue

        for k_name in knots_to_compute:
            k_data = knots_data_map[k_name]
            try:
                cols = get_cached_colorings(k_name, k_data, q)
                current_colorings[k_name] = cols
                count = len(cols) if isinstance(cols, list) else 0
                results[k_name][(q_name, 'coloring_count')] = count
            except Exception as e:
                print(f"Error: Failed to compute colorings for {k_name}: {e}")
                results[k_name][(q_name, 'coloring_count')] = -1
                current_colorings[k_name] = []

        # 2. Compute cocycle invariants by group size
        for g in group_sizes:
            try:
                # Skip if no non-empty coloring set is available
                knots_with_colorings = [k for k in knots_to_compute if k in current_colorings and current_colorings[k]]
                if not knots_with_colorings:
                    continue

                cocycles = get_cached_cocycles(q, g)
                if len(cocycles) > 10000:
                    print(f"Warning: Skipping {q_name} Z_{g} (too many cocycles: {len(cocycles)}).", flush=True)
                    for k_iter in knots_data_map:
                        results[k_iter][(q_name, g)] = ['SKIPPED']
                    break
                
                # 3. Compute invariants only for non-trivial coloring sets
                for k_name in knots_with_colorings:
                    cols = current_colorings[k_name]
                    
                    if len(cols) <= q_size:
                        continue 
                        
                    invs = compute_all_cocycle_invariant(knots_data_map[k_name], q, g, cocycles=cocycles, colorings=cols)
                    polys = sorted([i['polynomial'] for i in invs])
                    unique_polys = sorted(list(set(polys)))
                    results[k_name][(q_name, g)] = unique_polys
                    
            except Exception as e:
                print(f"Error: Failed to compute cocycle invariants for {q_name} Z_{g}: {e}")
                
    return results

def compare_pair_fast(k1: str, k2: str, invariants_map: Dict, quandles: List[Dict], group_sizes: List[int]) -> Tuple[bool, str, Optional[Dict]]:
    """Fast comparison using pre-computed invariants."""
    # 1. Check coloring counts
    for q in quandles:
        q_name = q['name']
        c1 = invariants_map[k1].get((q_name, 'coloring_count'), -1)
        c2 = invariants_map[k2].get((q_name, 'coloring_count'), -1)
        
        if c1 != -1 and c2 != -1 and c1 != c2:
            return True, f"Colorings Invariant with {q_name}", {
                'type': 'coloring_count',
                'quandle': q_name,
                k1: c1,
                k2: c2
            }

    # 2. Check cocycle invariants
    for q in quandles:
        q_name = q['name']
        for g in group_sizes:
            key = (q_name, g)
            p1 = invariants_map[k1].get(key)
            p2 = invariants_map[k2].get(key)
            
            if p1 is not None and p2 is not None and p1 != p2:
                 return True, f"Cocycle Invariant with {q_name} over Z_{g}", {
                     'type': 'cocycle_invariant',
                     'quandle': q_name,
                     'group': f"Z_{g}",
                     k1: p1,
                     k2: p2
                 }
                 
    return False, "Unable to distinguish with current set of quandles", None

def compare_pair_all(k1: str, k2: str, invariants_map: Dict, quandles: List[Dict], group_sizes: List[int]) -> Tuple[bool, List[str], List[Dict]]:
    """Compare and return ALL differences found."""
    differences = []
    reasons = []
    
    # 1. Collect coloring-count differences
    for q in quandles:
        q_name = q['name']
        c1 = invariants_map[k1].get((q_name, 'coloring_count'), -1)
        c2 = invariants_map[k2].get((q_name, 'coloring_count'), -1)
        
        if c1 != -1 and c2 != -1 and c1 != c2:
            reason = f"Colorings Invariant with {q_name}"
            reasons.append(reason)
            differences.append({
                'type': 'coloring_count',
                'quandle': q_name,
                k1: c1,
                k2: c2
            })

    # 2. Collect cocycle invariant differences
    for q in quandles:
        q_name = q['name']
        for g in group_sizes:
            key = (q_name, g)
            p1 = invariants_map[k1].get(key)
            p2 = invariants_map[k2].get(key)
            
            if p1 is not None and p2 is not None and p1 != p2:
                 reason = f"Cocycle Invariant with {q_name} over Z_{g}"
                 reasons.append(reason)
                 differences.append({
                     'type': 'cocycle_invariant',
                     'quandle': q_name,
                     'group': f"Z_{g}",
                     k1: p1,
                     k2: p2
                 })
                 
    if differences:
        return True, reasons, differences
    return False, ["Unable to distinguish"], []

def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Compare knots using Quandle Colorings and Cocycle Invariants.')
    parser.add_argument('knots', metavar='K', type=str, nargs='*',
                        help='Names of knots to compare (e.g., 6_3 10_123)')
    return parser.parse_args()

def main():
    args = parse_arguments()
    available_knots = get_available_knots()
    
    selected_knots = []
    
    # Fall back to interactive input when no knots are provided
    if not args.knots:
        print("Knots:", ", ".join(available_knots[:10]), "...")
        print("Enter knots:")
        user_input = sys.stdin.readline().strip()
        if not user_input:
            print("No input provided. Exiting.")
            return
        selected_knots = user_input.split()
    else:
        selected_knots = args.knots
        
    # Keep only knots that exist in data
    valid_knots = []
    for k in selected_knots:
        if k in available_knots:
            valid_knots.append(k)
        else:
            print(f"Warning: Knot data not found for '{k}'. Skipping.")
            
    if len(valid_knots) < 2:
        print("Error: Need at least two valid knots to compare.")
        return

    print(f"\nComparing: {', '.join(valid_knots)}")
    
    # Load data
    data_map = {}
    for k in valid_knots:
        try:
            data_map[k] = load_knot_data(k)
        except Exception as e:
            print(f"Error: Failed to load {k}: {e}")
            return

    quandles = get_quandles()
    group_sizes = FAST_MODE_GROUP_SIZES if FAST_MODE else FULL_GROUP_SIZES
    if FAST_MODE:
        print(
            f"Fast mode: Dihedral <= {FAST_MODE_MAX_DIHEDRAL}, coefficient groups {group_sizes}"
        )
    
    # Phase 1: compute invariants
    print("\nPhase 1: Computing Invariants")
    start_time = time.time()
    invariants_map = compute_all_invariants_for_knots(data_map, quandles, group_sizes)
    duration = time.time() - start_time
    print(f"Computation finished in {duration:.2f}s.\n")
    
    # Phase 2: compare knot pairs
    print("Phase 2: Comparing Pairs")
    pairs = list(itertools.combinations(valid_knots, 2))
    print(f"{len(pairs)} pairs for comparison:\n")
    
    results = []
    
    for k1, k2 in pairs:
        print(f"Comparing {k1} vs {k2} ...", end=" ", flush=True)
        is_distinguished, reason, details = compare_pair_fast(k1, k2, invariants_map, quandles, group_sizes)
        
        if is_distinguished:
            print(f"OK: Distinguished: {reason}")
            results.append((k1, k2, True, reason))
        else:
            print("FAIL: Undistinguished.")
            results.append((k1, k2, False, "Tried: Dihedral, Alexander and Connected Quandles"))
            
    print("Summary")
    
    all_distinguished = True
    for k1, k2, success, note in results:
        status = "OK" if success else "FAIL"
        print(f"{status} {k1} vs {k2}: {note}")
        if not success:
            all_distinguished = False
            
    if all_distinguished:
        print("All pairs were distinguished.")
    else:
        print("Some pairs remain undistinguished. Consider adding more quandles.")

if __name__ == "__main__":
    main()
