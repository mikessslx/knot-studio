"""
2. Group knots with identical coloring counts across all quandles.
"""

import csv
import os
from collections import defaultdict

def results(csv_path=None, output_path=None):
    """
    Group knots with identical coloring counts across all quandles.
    """
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), 'io', 'turbo_results.csv')
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), 'io', 'results.txt')
    knot_signatures = {}
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            knot_name = row['Knot'].replace('.json', '')
            # Build signature from all coloring counts
            signature = tuple(row[col] for col in reader.fieldnames[1:])
            knot_signatures[knot_name] = signature
    
    # Group knots by signature
    signature_groups = defaultdict(list)
    for knot, sig in knot_signatures.items():
        signature_groups[sig].append(knot)

    def sort_key(name):
        parts = name.split('_')
        crossing_num = int("".join(filter(str.isdigit, parts[0])))
        return (crossing_num, parts[0], int(parts[1]))
    
    # Keep only groups with at least two knots
    result_lines = []
    for sig, knots in signature_groups.items():
        if len(knots) >= 2:
            sorted_knots = sorted(knots, key=sort_key)
            result_lines.append(' '.join(sorted_knots))
    
    # Sort groups by their first knot
    result_lines.sort(key=lambda line: sort_key(line.split()[0]))
    
    with open(output_path, 'w') as f:
        f.write('\n'.join(result_lines))
        if result_lines:
            f.write('\n')
    
    print(f"Found {len(result_lines)} groups with identical colorings:")
    for line in result_lines:
        print(f"  {line}")

if __name__ == "__main__":
    results()
