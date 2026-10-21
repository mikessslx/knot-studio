"""
1. Convert knotinfo.csv PD notation into Knot Studio JSON.
"""

import csv
import json
import os
import re

def _parse_pd_notation(pd_str):
    """
    Parse PD notation string into crossing rows.
    """
    pd_str = pd_str.strip()
    inner = pd_str[1:-1]
    crossing_strs = re.split(r'\]\s*;\s*\[', inner)
    
    crossings = []
    for cs in crossing_strs:
        cs = cs.replace('[', '').replace(']', '')
        nums = [int(x) for x in cs.split(';')]
        crossings.append(nums)
    
    return crossings

def _pd_to_knot_json(name, pd_crossings):
    """
    Convert PD crossing rows into knot JSON.
    """
    n = len(pd_crossings)
    
    all_edges = set()
    for crossing in pd_crossings:
        for e in crossing:
            all_edges.add(e)
    
    # Union-find over edges
    parent = {e: e for e in all_edges}
    
    def find(x):
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]
    
    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py
    
    # Merge edges that belong to the same over-arc
    for a, b, c, d in pd_crossings:
        union(d, b)
    
    # Build contiguous arc ids
    roots = set(find(e) for e in all_edges)
    root_to_arc = {r: i for i, r in enumerate(sorted(roots))}
    edge_to_arc = {e: root_to_arc[find(e)] for e in all_edges}
    
    if len(roots) != n:
        print(f"Warning: {name} has {len(roots)} arcs but {n} crossings.")
    
    # Convert crossings to Knot Studio fields
    num_edges = len(all_edges)
    json_crossings = []
    for i, (a, b, c, d) in enumerate(pd_crossings):
        is_forward = (b == (d % num_edges) + 1)
        
        c_type = "positive" if is_forward else "negative"
            
        json_crossings.append({
            "id": i,
            "type": c_type,
            "over": edge_to_arc[d],
            "under_in": edge_to_arc[a],
            "under_out": edge_to_arc[c]
        })
    
    return {
        "name": name,
        "arcs": list(range(len(roots))),
        "crossings": json_crossings
    }

def knotinfo(csv_path=None, output_dir=None):
    """
    Convert knotinfo.csv rows into knot JSON files.
    """
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), 'io', 'knotinfo.csv')
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), 'data')
    os.makedirs(output_dir, exist_ok=True)
    
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['Name']
            pd_str = row['PD Notation']
            
            pd_crossings = _parse_pd_notation(pd_str)
            knot_json = _pd_to_knot_json(name, pd_crossings)
            
            output_path = os.path.join(output_dir, f"{name}.json")
            with open(output_path, 'w') as out:
                json.dump(knot_json, out, indent=2)
            
            rel_path = os.path.relpath(output_path, os.getcwd())
            print(f"Created {rel_path}: {len(knot_json['arcs'])} arcs, {len(knot_json['crossings'])} crossings")

if __name__ == "__main__":
    knotinfo()
