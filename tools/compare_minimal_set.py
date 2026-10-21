"""
6. Compare knot pairs listed in minimal_set.txt.
"""

import compare
import sys
import os
import re

def split_aliases(text):
    aliases = []
    current = []
    depth = 0
    for ch in text:
        if ch == '(':
            depth += 1
        elif ch == ')' and depth > 0:
            depth -= 1

        if ch == ',' and depth == 0:
            alias = ''.join(current).strip()
            if alias:
                aliases.append(alias)
            current = []
        else:
            current.append(ch)

    alias = ''.join(current).strip()
    if alias:
        aliases.append(alias)
    return aliases

def canonical_quandle_name(name):
    name = name.strip()

    match = re.match(r'^Dihedral\((\d+)\)$', name)
    if match:
        return f"Dihedral_{match.group(1)}"

    match = re.match(r'^Alexander\(Z(\d+),\s*t=(\d+)\)$', name)
    if match:
        return f"Alexander_Z{match.group(1)}_t{match.group(2)}"

    return name

def parse_section(line):
    match = re.match(r'^(\d+)\.\s+(.*?)\s+\(.*unique\s+(\d+).*\)', line)
    if not match:
        return None

    section_idx = int(match.group(1))
    quandle_name = match.group(2).strip()
    unique_count = int(match.group(3))

    excluded = {canonical_quandle_name(quandle_name)}
    if ' (or ' in line:
        alias_part = line.split(' (or ', 1)[1]
        if alias_part.endswith(')'):
            alias_part = alias_part[:-1]
        excluded.update(canonical_quandle_name(a) for a in split_aliases(alias_part))

    return {
        'idx': section_idx,
        'name': quandle_name,
        'unique_count': unique_count,
        'excluded_quandles': excluded,
    }

def parse_minimal_set(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()
    
    records = []
    should_collect = False
    current_section = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        section = parse_section(line)
        if section:
            current_section = section
            should_collect = (section['unique_count'] <= 10)
            continue
            
        # Collect pairs from selected groups
        if should_collect and current_section:
            if line.startswith('and ') and line.endswith('more...'):
                continue
            if 'OK:' in line or 'Distinguished' in line:
                continue
                
            if ',' in line:
                part = line.split(' OK:')[0].strip()
                if ',' not in part:
                    continue
                    
                k1, k2 = [k.strip() for k in part.split(',', 1)]
                # Keep only knot name token
                k2 = k2.split(' ')[0]
                records.append({
                    'section_idx': current_section['idx'],
                    'section_name': current_section['name'],
                    'excluded_quandles': current_section['excluded_quandles'],
                    'pair': (k1, k2),
                })
                
    return records

def run_compare(records):
    original_count = len(records)
    unique_records = []
    seen_records = set()
    for rec in records:
        k1, k2 = rec['pair']
        key = (rec['section_idx'], k1, k2)
        if key not in seen_records:
            seen_records.add(key)
            unique_records.append(rec)
    records = unique_records
    print(f"Checking {len(records)} section-pairs (from {original_count})...")
    
    # 1. Collect unique knots from pairs
    unique_knots = {k for rec in records for k in rec['pair']}
    print(f"Loading data for {len(unique_knots)} knots...", end=' ', flush=True)
    
    # 2. Load knot data
    data_map = {}
    for k in unique_knots:
        try:
            data_map[k] = compare.load_knot_data(k)
        except Exception:
            pass
            
    # 3. Compute invariants
    quandles = compare.get_quandles()
    group_sizes = compare.FAST_MODE_GROUP_SIZES if compare.FAST_MODE else compare.FULL_GROUP_SIZES
    
    print("\nPhase 1: Computing Invariants")
    invariants_map = compare.compute_all_invariants_for_knots(data_map, quandles, group_sizes)
    compare.clear_caches()
    
    # 4. Compare pairs
    success_count = 0
    fail_count = 0
    results_map = {}
    
    print("Phase 2: Comparing Pairs")
    for i, rec in enumerate(records, 1):
        k1, k2 = rec['pair']
        if k1 not in data_map or k2 not in data_map:
            print(f"Warning: [{i}/{len(records)}] Missing data for {k1} vs {k2}.")
            fail_count += 1
            continue
            
        print(f"[{i}/{len(records)}] {k1} vs {k2} ... ", end='', flush=True)
        
        is_distinguished, reasons, details = compare.compare_pair_all(k1, k2, invariants_map, quandles, group_sizes)
        strict_reasons = [
            reason
            for reason, detail in zip(reasons, details)
            if detail.get('quandle') not in rec['excluded_quandles']
        ]
        
        if strict_reasons:
            if len(strict_reasons) == 1:
                reasons_str = strict_reasons[0]
                print(f"OK: Distinguished: {reasons_str}")
            else:
                reasons_str = "\n - " + "\n - ".join(strict_reasons)
                print(f"OK: Distinguished ({len(strict_reasons)} ways):{reasons_str}")
            success_count += 1
            results_map[(rec['section_idx'], k1, k2)] = reasons_str
        elif is_distinguished:
            excluded = ', '.join(sorted(rec['excluded_quandles']))
            print(f"SELF-ONLY: Distinguished only by excluded quandles: {excluded}.")
            fail_count += 1
        else:
            print("FAIL: Undistinguished.")
            fail_count += 1

    print(f"\nResults: {success_count} distinguished, {fail_count} undistinguished")
    return results_map

def update_minimal_set_file(file_path, results_map):
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    new_lines = []
    current_section_idx = None
    for line in lines:
        original_line = line
        line_stripped = line.strip()

        section = parse_section(line_stripped)
        if section:
            current_section_idx = section['idx']
        
        # Extract pair from unresolved line and append reason
        if ',' in line_stripped and not ('OK:' in line_stripped or 'Distinguished' in line_stripped):
            part = line.split(' OK:')[0].strip()
            if ',' in part:
                try:
                    k1_raw, k2_raw = part.split(',', 1)
                    k1 = k1_raw.strip()
                    k2 = k2_raw.strip().split(' ')[0]
                    key = (current_section_idx, k1, k2)
                    
                    if key in results_map:
                        reason = results_map[key]
                        new_lines.append(original_line.rstrip() + f" OK: Distinguished: {reason}\n")
                        continue
                except ValueError:
                    pass
                    
        new_lines.append(original_line)
        
    with open(file_path, 'w') as f:
        f.writelines(new_lines)

def summarize_refinement(file_path):
    with open(file_path, 'r') as f:
        lines = f.readlines()

    sections = []
    current_section = None

    for line in lines:
        line_stripped = line.strip()
        section = parse_section(line_stripped)
        if section:
            current_section = {
                'idx': section['idx'],
                'name': section['name'],
                'pairs': [],
            }
            sections.append(current_section)
            continue

        if current_section and ',' in line_stripped:
            if line_stripped.startswith('and ') and line_stripped.endswith('more...'):
                continue
            if re.match(r'^\S+,\s+\S+', line_stripped):
                current_section['pairs'].append({
                    'line': line_stripped,
                    'ok': 'OK: Distinguished' in line_stripped,
                })

    checked_sections = [s for s in sections if s['pairs']]
    removable = [s for s in checked_sections if all(p['ok'] for p in s['pairs'])]
    retained = [s for s in sections if s not in removable]

    checked_pairs = sum(len(s['pairs']) for s in checked_sections)
    covered_pairs = sum(1 for s in checked_sections for p in s['pairs'] if p['ok'])

    print("\nRefinement Summary")
    print(f"Checked sections: {len(checked_sections)}")
    print(f"Checked unique pairs: {covered_pairs}/{checked_pairs} covered")
    print(f"Removable quandles: {len(removable)}")
    for section in removable:
        print(f" - {section['idx']}. {section['name']}")

    print(f"Final set size: {len(sections)} -> {len(retained)}")
    print("Retained quandles:")
    for section in retained:
        print(f" - {section['idx']}. {section['name']}")

if __name__ == "__main__":
    minimal_set_path = os.path.join(os.path.dirname(__file__), 'io', 'minimal_set.txt')
    if not os.path.exists(minimal_set_path):
        print(f"File not found: {minimal_set_path}")
        sys.exit(1)
        
    target_pairs = parse_minimal_set(minimal_set_path)
    if not target_pairs:
        print("No pairs found matching criteria.")
    else:
        results_map = run_compare(target_pairs)
        if results_map:
            update_minimal_set_file(minimal_set_path, results_map)
        summarize_refinement(minimal_set_path)
