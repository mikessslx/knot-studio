"""
3. Copy knot JSON files for grouped results.
"""

import os
import shutil

def data_results(results_path=None, data_dir=None, output_dir=None):
    """
    Copy knot JSON files from data/ into data_results/{line_number}/.
    """
    if results_path is None:
        results_path = os.path.join(os.path.dirname(__file__), 'io', 'results.txt')
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
    if output_dir is None:
        output_dir = os.path.join(os.path.dirname(__file__), 'data_results')
    os.makedirs(output_dir, exist_ok=True)

    try:
        with open(results_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"Error: Results file not found: {results_path}.")
        return

    copied_count = 0
    missing_count = 0

    for line_num, line in enumerate(lines, 1):
        knots = line.strip().split()
        if not knots:
            continue
            
        # Create subdirectory for this group
        line_dir = os.path.join(output_dir, str(line_num))
        if not os.path.exists(line_dir):
            os.makedirs(line_dir)
            
        for knot in knots:
            json_filename = f"{knot}.json"
            source_path = os.path.join(data_dir, json_filename)
            destination_path = os.path.join(line_dir, json_filename)

            if os.path.exists(source_path):
                try:
                    shutil.copy2(source_path, destination_path)
                    copied_count += 1
                except Exception as e:
                    print(f"Error: Failed to copy {json_filename}: {e}.")
            else:
                print(f"Warning: {json_filename} not found in {data_dir}.")
                missing_count += 1

    print(f"Copied {copied_count} files ({len(lines)} groups).")
    if missing_count > 0:
        print(f"Missing files: {missing_count}.")
    rel_output_dir = os.path.relpath(output_dir, os.getcwd())
    print(f"Copied to subdirectories in {rel_output_dir}.")

if __name__ == "__main__":
    data_results()
