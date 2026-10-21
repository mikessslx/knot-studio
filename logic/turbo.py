import os
import json

def turbo_ipynb(knot_files, quandles, method='algebra', turbo=True):
    """
    Generate a Jupyter Notebook JSON structure for selected calculations.
    """
    # 1. Solver
    solver_code = ""
    try:
        # Read solver code from the logic directory
        with open(os.path.join(os.path.dirname(__file__), 'solver.py'), 'r') as f:
            solver_code = f.read()
    except Exception as e:
        solver_code = f"# Error: Failed to read solver.py: {e}"

    # Format quandles for display
    def format_quandle_str(q):
        elements_str = json.dumps(q["elements"])
        # Format operation table rows with indentation
        rows = [json.dumps(row) for row in q["operation_table"]]
        op_table_str = "[\n" + ",\n".join([f"            {row}" for row in rows]) + "\n        ]"
        
        return f'''    {{
        "name": "{q.get('name', 'Unknown')}",
        "elements": {elements_str},
        "operation_table": {op_table_str}
    }}'''

    # Generate formatted string for quandles
    quandles_code_str = "[\n" + ",\n".join([format_quandle_str(q) for q in quandles]) + "\n    ]"

    # 2. Turbo
    # Inject quandle data from the frontend
    main_code = f"""
import json
import os
import time
import csv

def main():
    # --- Configuration ---
    DATA_DIR = "data"
    OUTPUT_FILE = "turbo_results.csv"
    METHOD = "{method}"
    TURBO = {turbo}
    
    # --- Quandles ---
    # Data injected directly from Knot Studio Web
    quandles = {quandles_code_str}
    
    # --- Knots ---
    selected_knots = {json.dumps(knot_files)}
    
    # --- Load Data ---
    if not os.path.exists(DATA_DIR):
        print(f"Error: Data directory '{{DATA_DIR}}' not found. Upload knot JSON files to a folder named '{{DATA_DIR}}'.")
        return

    print(f"Starting {{METHOD}} turbo.")
    
    # --- Initialize CSV ---
    fieldnames = ["Knot"] + [q.get("name", "Unknown Quandle") for q in quandles]
    try:
        with open(OUTPUT_FILE, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
    except Exception as e:
        print(f"Error: Failed to initialize CSV: {{e}}")
        return
    
    results = []
    if METHOD == 'dfs':
        solver_func = dfs_solver
    elif METHOD == 'algebra':
        solver_func = algebraic_solver
    elif METHOD == 'propagation':
        solver_func = propagation_solver
    elif METHOD == 'linear':
        solver_func = linear_solver
    elif METHOD == 'snf':
        solver_func = snf_solver
    else:
        solver_func = enum_solver
    
    for k_idx, knot_file in enumerate(selected_knots):
        file_path = os.path.join(DATA_DIR, knot_file)
        if not os.path.exists(file_path):
            print(f"Warning: {{knot_file}} not found in {{DATA_DIR}}.")
            continue
            
        try:
            with open(file_path, 'r') as f:
                knot = json.load(f)
        except Exception as e:
            print(f"Error: Failed to load {{knot_file}}: {{e}}")
            continue
            
        print(f"[{{k_idx+1}}/{{len(selected_knots)}}] Processing {{knot_file}}...", end="", flush=True)
        start_time = time.time()
        
        row = {{"Knot": knot_file}}
        
        for q in quandles:
            # Ensure name exists
            q_name = q.get("name", "Unknown Quandle")
            
            try:
                colorings = compute_quandle_colorings(q, knot, solver=solver_func, turbo=TURBO)
                if isinstance(colorings, int):
                    count = colorings
                else:
                    count = len(colorings)
                
                if TURBO:
                    count *= len(q["elements"])
                    
                row[q_name] = count
            except Exception as e:
                print(f"  Error: Failed to process {{q_name}}: {{e}}")
                row[q_name] = -1
        
        duration = time.time() - start_time
        print(f" ({{duration:.3f}}s)")
        
        # --- Save Results ---
        try:
            with open(OUTPUT_FILE, 'a', newline='') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writerow(row)
        except Exception as e:
            print(f"Error: Failed to save row for {{knot_file}}: {{e}}")

        results.append(row)
        
    print(f"\\nDone. Results saved to {{OUTPUT_FILE}}.")
    
    print("\\nPreview:")
    for i, row in enumerate(results[:6]):
        print(row)

if __name__ == "__main__":
    main()
"""

    # 3. Upload
    upload_code_1 = """
import ipywidgets as widgets
from IPython.display import display

# Create the widget allowing the selection of MULTIPLE files
uploader = widgets.FileUpload(
    accept='.json',  # Accepts .json files
    multiple=True 
)
display(uploader)
"""

    upload_code_2 = """
# Shows the names of the uploaded files
try:
    display(uploader.value.keys())
except:
    display([f['name'] for f in uploader.value])
"""

    upload_code_3 = """
import os
import json

DATA_DIR = 'data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

if uploader.value:
    # Adaptation for compatibility
    uploaded_items = uploader.value
    if not isinstance(uploaded_items, dict):
        uploaded_items = {f['name']: f for f in uploaded_items}

    # uploader.value is now a dictionary with all the uploaded files
    for file_name, file_info in uploaded_items.items():
        
        # 1. Write binary content to Colab disk
        content = file_info['content']
        file_path = os.path.join(DATA_DIR, file_name)
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        print(f"\\nOK: File '{file_name}' saved to '{DATA_DIR}'.")

        # 2. Read the file based on its type
        try:
            if file_name.endswith('.json'):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                print(" -> Loaded as JSON.")
                
            else:
                print(" -> Warning: File type not recognized for automatic upload.")

        except Exception as e:
            print(f" -> Error: Failed to process {file_name}: {e}")

else:
    print("Error: No uploaded files detected. Select files in the cell above.")
"""

    # Format lists for display
    def format_list_concise(items, max_items=6):
        if len(items) <= max_items:
            return ", ".join([f"`{i}`" for i in items])
        else:
            return ", ".join([f"`{i}`" for i in items[:max_items]]) + f", ... (+{len(items)-max_items} more)"

    knots_list_str = format_list_concise(knot_files)
    quandles_list_str = format_list_concise([q.get('name', 'Unknown') for q in quandles])

    # Construct IPYNB JSON structure
    notebook = {
        "cells": [
            {
                "cell_type": "markdown",
                "id": "cell-intro",
                "metadata": {},
                "source": [
                    "# Knot Studio Turbo - IPYNB\n",
                    "This notebook is generated by [Knot Studio Web](https://github.com/mikessslx/knot-studio).\n",
                    "\n",
                    "### Configuration:\n",
                    f"1. Knots ({len(knot_files)}):\n",
                    f"- {knots_list_str}\n",
                    f"2. Quandles ({len(quandles)}):\n",
                    f"- {quandles_list_str}\n",
                    "\n",
                    "### Instructions:\n",
                    "1. Run the `Upload` cells below to upload `JSON`.\n",
                    "2. Run the remaining cells to calculate."
                ]
            },
            {
                "cell_type": "markdown",
                "id": "cell-header-upload",
                "metadata": {},
                "source": ["### 1. Upload"]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "cell-upload-1",
                "metadata": {},
                "outputs": [],
                "source": upload_code_1.splitlines(keepends=True)
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "cell-upload-2",
                "metadata": {},
                "outputs": [],
                "source": upload_code_2.splitlines(keepends=True)
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "cell-upload-3",
                "metadata": {},
                "outputs": [],
                "source": upload_code_3.splitlines(keepends=True)
            },
            {
                "cell_type": "markdown",
                "id": "cell-header-solver",
                "metadata": {},
                "source": ["### 2. Solver"]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "cell-solver",
                "metadata": {},
                "outputs": [],
                "source": solver_code.splitlines(keepends=True)
            },
            {
                "cell_type": "markdown",
                "id": "cell-header-main",
                "metadata": {},
                "source": ["### 3. Turbo"]
            },
            {
                "cell_type": "code",
                "execution_count": None,
                "id": "cell-main",
                "metadata": {},
                "outputs": [],
                "source": main_code.splitlines(keepends=True)
            }
        ],
        "metadata": {
            "colab": {
                "collapsed_sections": [
                    "cell-header-upload",
                    "cell-header-solver",
                    "cell-header-main"
                ],
                "name": "Knot Studio Turbo",
                "provenance": []
            },
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3
                },
                "file_extension": ".py",
                "mimetype": "text/x-python",
                "name": "python",
                "nbconvert_exporter": "python",
                "pygments_lexer": "ipython3",
                "version": "3.13.5"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 4
    }

    return notebook

def turbo_gap(knot_files, quandles, turbo=True):
    """
    Generate a GAP script string for selected calculations.
    """
    # Prepare JSON strings for GAP embedding
    quandles_json = json.dumps(quandles)
    knots_json = json.dumps(knot_files)
    
    # Escape for GAP string literals
    # 1. Escape backslashes
    # 2. Escape double quotes
    def escape_gap_string(s):
        return s.replace('\\', '\\\\').replace('"', '\\"')

    quandles_str_escaped = escape_gap_string(quandles_json)
    knots_str_escaped = escape_gap_string(knots_json)
    
    gap = f"""# Knot Studio Turbo - GAP
# Generated by [Knot Studio Web](https://github.com/mikessslx/knot-studio)

LoadPackage("json");

# --- Configuration ---
Turbo := {str(turbo).lower()};
DataDir := "data";
OutputFile := "turbo_results.csv";

# --- Load Data ---
Print("Loading Data...\\n");

# Embed Quandles
QuandlesStr := "{quandles_str_escaped}";
Quandles := JsonStringToGap(QuandlesStr);

# Embed Knots
KnotFilesStr := "{knots_str_escaped}";
KnotFiles := JsonStringToGap(KnotFilesStr);

# --- Solver Implementation ---
GlobalDFSSolver := function(m, k, op_table, left_inv, checks, coloring, Turbo)
    local Solve, count;
    
    count := 0;
    
    Solve := function(arc_idx)
        local c, valid, chk, c_in, c_out, c_over, c_pos, v_in, v_out, v_over, forced_val;
        
        # Base case: all arcs colored
        if arc_idx > m then
            count := count + 1;
            return;
        fi;
        
        # Turbo: fix the first arc to the first color
        if Turbo and arc_idx = 1 then
            coloring[1] := 1;
            Solve(2);
            coloring[1] := 0;
            return;
        fi;
        
        # Optimization: Lookahead / Deduction with fast index comparison
        forced_val := 0;
        for chk in checks[arc_idx] do
            c_in := chk[1]; c_out := chk[2]; c_over := chk[3]; c_pos := chk[4];
            
            # Case 1: arc_idx is u_out (max) and u_in & over are known (< arc_idx)
            if c_out = arc_idx and c_in < arc_idx and c_over < arc_idx then
                v_in := coloring[c_in]; v_over := coloring[c_over];
                if c_pos = 1 then
                    forced_val := op_table[v_in][v_over];
                else
                    forced_val := left_inv[v_over][v_in];
                fi;
                break;
            
            # Case 2: arc_idx is u_in (max) and u_out & over are known (< arc_idx)
            elif c_in = arc_idx and c_out < arc_idx and c_over < arc_idx then
                v_out := coloring[c_out]; v_over := coloring[c_over];
                if c_pos = 0 then
                    forced_val := op_table[v_out][v_over];
                else
                    forced_val := left_inv[v_over][v_out];
                fi;
                break;
            
            # Case 3: arc_idx is over (max), u_in & u_out known - skip (expensive)
            fi;
        od;

        if forced_val <> 0 then
            # Fast path: only try the forced value
            coloring[arc_idx] := forced_val;
            valid := true;
            
            # Verify constraints
            for chk in checks[arc_idx] do
                c_in := chk[1]; c_out := chk[2]; c_over := chk[3]; c_pos := chk[4];
                
                if (c_out = arc_idx and c_in < arc_idx and c_over < arc_idx) or
                   (c_in = arc_idx and c_out < arc_idx and c_over < arc_idx) then
                    continue;
                fi;
                
                v_in := coloring[c_in]; v_out := coloring[c_out]; v_over := coloring[c_over];
                
                if c_pos = 1 then
                    if op_table[v_in][v_over] <> v_out then valid := false; break; fi;
                else
                    if op_table[v_out][v_over] <> v_in then valid := false; break; fi;
                fi;
            od;
            
            if valid then Solve(arc_idx + 1); fi;
            coloring[arc_idx] := 0;
            return;
        fi;
        
        # Slow path: try all colors
        for c in [1..k] do
            coloring[arc_idx] := c;
            valid := true;
            
            # Verify constraints (all are fully assigned since arc_idx is max)
            for chk in checks[arc_idx] do
                c_in := chk[1]; c_out := chk[2]; c_over := chk[3]; c_pos := chk[4];
                v_in := coloring[c_in]; v_out := coloring[c_out]; v_over := coloring[c_over];
                
                if c_pos = 1 then
                    if op_table[v_in][v_over] <> v_out then valid := false; break; fi;
                else
                    if op_table[v_out][v_over] <> v_in then valid := false; break; fi;
                fi;
            od;
            
            if valid then
                Solve(arc_idx + 1);
            fi;
        od;
        coloring[arc_idx] := 0;
    end;
    
    Solve(1);
    return count;
end;

# Helper to optimize knot arc ordering
# Native arrays instead of Dictionary
OptimizeKnot := function(knot)
    local arcs, m, arc_to_idx, crossings, adj, perm, visited, 
          best_score, best_arc, best_degree, score, i, j, c, u_in, u_out, over,
          old_to_new, checks, max_idx, entry, arc_indices, is_pos;

    if IsBound(knot.optimized_checks) then
        return;
    fi;

    arcs := knot.arcs;
    m := Length(arcs);
    crossings := knot.crossings;
    
    arc_to_idx := function(arc_name)
        local idx;
        for idx in [1..m] do
            if arcs[idx] = arc_name then return idx; fi;
        od;
        return fail;
    end;
    
    # Precompute arc indices for all crossings
    arc_indices := [];
    for c in crossings do
        u_in := arc_to_idx(c.under_in);
        u_out := arc_to_idx(c.under_out);
        over := arc_to_idx(c.over);
        if c.type = "positive" then is_pos := 1; else is_pos := 0; fi;
        Add(arc_indices, [u_in, u_out, over, is_pos]);
    od;

    # 1. Build adjacency
    adj := List([1..m], x -> []);
    for j in [1..Length(arc_indices)] do
        Add(adj[arc_indices[j][1]], j);
        Add(adj[arc_indices[j][2]], j);
        Add(adj[arc_indices[j][3]], j);
    od;

    # 2. Compute greedy ordering with tie-breaker
    perm := [1];
    visited := ListWithIdenticalEntries(m, false);
    visited[1] := true;
    
    while Length(perm) < m do
        best_score := -1;
        best_arc := -1;
        best_degree := -1;
        
        for i in [1..m] do
            if visited[i] then continue; fi;
            
            # Score = number of visited neighbors
            score := 0;
            for j in adj[i] do
                c := arc_indices[j];
                if visited[c[1]] then score := score + 1; fi;
                if visited[c[2]] then score := score + 1; fi;
                if visited[c[3]] then score := score + 1; fi;
            od;
            
            # Tie-breaker: degree (number of adjacent crossings)
            if score > best_score or (score = best_score and Length(adj[i]) > best_degree) then
                best_score := score;
                best_arc := i;
                best_degree := Length(adj[i]);
            fi;
        od;
        
        # Handle disconnected components
        if best_arc = -1 then
            for i in [1..m] do
                if not visited[i] then best_arc := i; break; fi;
            od;
        fi;
        
        Add(perm, best_arc);
        visited[best_arc] := true;
    od;

    # 3. Build old_to_new mapping array
    old_to_new := ListWithIdenticalEntries(m, 0);
    for i in [1..m] do
        old_to_new[perm[i]] := i;
    od;
    
    # 4. Build constraints array: [u_in, u_out, over, is_positive]
    checks := List([1..m], x -> []);
    
    for c in arc_indices do
        u_in := old_to_new[c[1]];
        u_out := old_to_new[c[2]];
        over := old_to_new[c[3]];
        
        max_idx := Maximum(u_in, u_out, over);
        
        Add(checks[max_idx], [u_in, u_out, over, c[4]]);
    od;

    # Cache the optimized plan
    knot.optimized_checks := checks;
    knot.m := m;
end;

CountColorings := function(quandle, knot)
    local elements, k, elem_to_idx, op_table, left_inv, row, val, i, j, c, a, b, coloring, count;
    
    # Ensure knot is optimized
    OptimizeKnot(knot);

    elements := quandle.elements;
    k := Length(elements);
    
    # Map elements to 1..k
    elem_to_idx := function(e)
        local idx;
        for idx in [1..k] do
            if elements[idx] = e then return idx; fi;
        od;
        return fail;
    end;
    
    op_table := [];
    for row in quandle.operation_table do
        val := [];
        for i in row do
            Add(val, elem_to_idx(i));
        od;
        Add(op_table, val);
    od;
    
    # Build left inverse table
    left_inv := List([1..k], x -> ListWithIdenticalEntries(k, 0));
    for a in [1..k] do
        for b in [1..k] do
            c := op_table[a][b];
            left_inv[b][c] := a;
        od;
    od;
    
    coloring := ListWithIdenticalEntries(knot.m, 0);
    count := GlobalDFSSolver(knot.m, k, op_table, left_inv, knot.optimized_checks, coloring, Turbo);
    
    if Turbo then
        return count * k;
    else
        return count;
    fi;
end;

# --- Main Execution ---
RunTurboCalculation := function()
    local FileString, q, k_file, f, json_content, knot, row_str, count, EscapeCsv, outStream, t_start;

    EscapeCsv := function(s)
        if ',' in s then
            return Concatenation("\\\"", s, "\\\"");
        else
            return s;
        fi;
    end;

    outStream := OutputTextFile(OutputFile, false);
    if outStream = fail then
        Print("Error: Cannot open output file ", OutputFile, "\\n");
        return;
    fi;

    # Initialize CSV
    FileString := "Knot";
    for q in Quandles do
        FileString := Concatenation(FileString, ",", EscapeCsv(q.name));
    od;
    FileString := Concatenation(FileString, "\\n");

    WriteAll(outStream, FileString);

    Print("Starting Turbo...\\n");

    for k_file in KnotFiles do
        AppendTo("*errout*", "Processing ", k_file, "...");
        t_start := Runtime();
        
        f := InputTextFile(Concatenation(DataDir, "/", k_file));
        if f = fail then
            AppendTo("*errout*", "Error: Could not open file ", k_file, "\\n");
            continue;
        fi;
        json_content := ReadAll(f);
        CloseStream(f);
        
        knot := JsonStringToGap(json_content);
        
        row_str := k_file;
        
        for q in Quandles do
            count := CountColorings(q, knot);
            row_str := Concatenation(row_str, ",", String(count));
        od;
        
        row_str := Concatenation(row_str, "\\n");
        WriteAll(outStream, row_str);
        
        AppendTo("*errout*", " (", Float(Runtime() - t_start)/1000.0, "s)\\n");
    od;

    CloseStream(outStream);
    Print("\\nDone! Results saved to ", OutputFile, "\\n");
end;

RunTurboCalculation();
"""
    return gap
