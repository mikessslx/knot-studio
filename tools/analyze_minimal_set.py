"""
7. Analyze minimal_set.txt outputs.
"""

import os
import re
import argparse
import statistics
from collections import Counter, defaultdict

def check_consistency(file_path):
    """
    Verify representative and alias consistency in the file.
    """
    with open(file_path, 'r') as f:
        lines = f.readlines()

    rep_to_aliases = defaultdict(set)
    all_reps = set()
    all_aliases = set()
    
    for line in lines:
        if ' (total ' not in line: continue
        parts = line.split(' (total ')
        if len(parts) < 2: continue
        
        prefix = parts[0].strip()
        if '. ' not in prefix: continue
        try:
            rep_name = prefix.split('. ', 1)[1].strip()
        except IndexError: continue
            
        all_reps.add(rep_name)
        
        if ' (or ' in line:
            try:
                alias_part = line.split(' (or ')[1].strip().rstrip(')')
                aliases = [a.strip() for a in alias_part.split(',')]
                rep_to_aliases[rep_name].add(tuple(sorted(aliases)))
                all_aliases.update(aliases)
            except IndexError: continue
        else:
            rep_to_aliases[rep_name].add(tuple())

    issues = sum(1 for alias_sets in rep_to_aliases.values() if len(alias_sets) > 1)
    overlap = all_reps.intersection(all_aliases)
    
    if issues == 0 and not overlap:
        print("OK: Consistency check passed.")
    else:
        if issues > 0:
            print(f"Warning: {issues} unstable representatives found.")
        if overlap:
            print(f"Warning: {len(overlap)} overlapping names found.")

def analyze_solutions(file_path):
    """
    Analyze solution frequency and composition.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    solutions_raw = re.split(r'Solution #\d+:', content)
    solutions_data = [s.strip() for s in solutions_raw[1:] if s.strip()]
    num_solutions = len(solutions_data)
    
    if num_solutions == 0:
        print("No solutions found.")
        return

    quandle_counts = Counter()
    quandle_unique_stats = defaultdict(list)
    solution_compositions = []

    for sol_text in solutions_data:
        current_quandles = set()
        for line in sol_text.split('\n'):
            line = line.strip()
            # Match quandle summary rows
            match = re.match(r'^\d+\.\s+(.*?)\s+\(total\s+(\d+),\s+unique\s+(\d+)\)', line)
            if match:
                name = match.group(1).split(" (or ")[0]
                unique_cov = int(match.group(3))
                current_quandles.add(name)
                quandle_counts[name] += 1
                quandle_unique_stats[name].append(unique_cov)
        solution_compositions.append(current_quandles)

    # 1. Print summary
    unique_solutions = set(frozenset(s) for s in solution_compositions)
    duplicates = num_solutions - len(unique_solutions)
    
    sol_sizes = [len(s) for s in solution_compositions]
    avg_size = statistics.mean(sol_sizes)
    
    if duplicates == 0:
        print(f"OK: All {num_solutions} solutions are unique (avg {avg_size:.2f}, min {min(sol_sizes)} and max {max(sol_sizes)})")
    else:
        print(f"Warning: {duplicates} duplicates found.")

    # 2. Build per-quandle stats
    all_stats = []
    for name, count in quandle_counts.items():
        pct = (count / num_solutions) * 100
        uniques = quandle_unique_stats[name]
        avg_u = statistics.mean(uniques) if uniques else 0
        all_stats.append({
            'name': name,
            'count': count,
            'pct': pct,
            'avg_unique': avg_u
        })
        
    # Sort by frequency then average unique count
    all_stats.sort(key=lambda x: (x['count'], x['avg_unique']), reverse=True)
    
    core_count = sum(1 for s in all_stats if s['pct'] == 100.0)
    print(f"Core set size: {core_count}")
    print("-" * 80)
    print(f"{'Rank':<4} | {'Name':<35} | {'Freq':<8} | {'Avg Unique'}")
    print("-" * 80)

    # 3. Print top entries
    limit = 30
    for i, item in enumerate(all_stats[:limit], 1):
        print(f"{i:<4} | {item['name']:<35} | {item['pct']:>5.1f}%  | {item['avg_unique']:>10.2f}")
    
    # Print hidden-count gap when needed
    remaining = len(all_stats) - limit
    bottom_limit = 30
    
    if remaining > bottom_limit:
        print(f"... ({remaining - bottom_limit} hidden) ...")
        print("-" * 80)
        
        # Print bottom entries
        start = len(all_stats) - bottom_limit
        for i in range(start, len(all_stats)):
            item = all_stats[i]
            print(f"{i+1:<4} | {item['name']:<35} | {item['pct']:>5.1f}%  | {item['avg_unique']:>10.2f}")
    elif remaining > 0:
        # Print remaining entries
        for i in range(limit, len(all_stats)):
            item = all_stats[i]
            print(f"{i+1:<4} | {item['name']:<35} | {item['pct']:>5.1f}%  | {item['avg_unique']:>10.2f}")

def minimal_set_analysis(file_path=None, check_consistency_flag=True, analyze_flag=True):
    if file_path is None:
        base_dir = os.path.dirname(__file__)
        file_path = os.path.join(base_dir, 'io', 'minimal_set.txt')

    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return

    if check_consistency_flag:
        check_consistency(file_path)
    
    if analyze_flag:
        analyze_solutions(file_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze minimal_set.txt')
    parser.add_argument('file_path', nargs='?', help='Path to minimal_set.txt')
    parser.add_argument('-c', '--consistency', action='store_true', help='Run only consistency checks')
    parser.add_argument('-a', '--analyze', action='store_true', help='Run only data analysis')
    
    args = parser.parse_args()
    
    run_consistency = True
    run_analysis = True
    
    if args.consistency:
        run_analysis = False
    if args.analyze:
        run_consistency = False
        
    minimal_set_analysis(args.file_path, run_consistency, run_analysis)
