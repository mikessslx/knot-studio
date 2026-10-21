"""
5. Find minimal quandle sets that distinguish knot pairs.
"""

import time
import csv
import os
import argparse
from collections import defaultdict

def solve_ortools(n_groups, groups_covering_pair, max=1, callback=None):
    from ortools.sat.python import cp_model
    
    model = cp_model.CpModel()
    
    # 1. Build selection variables
    x = {}
    
    for j in range(n_groups):
        x[j] = model.NewBoolVar(f'x_{j}')
    
    # 2. Minimize selected groups
    objective = sum(x.values())
    model.Minimize(objective)

    # 3. Add pair-coverage constraints
    unique_constraints = set()
    for p_idx, covering_groups in groups_covering_pair.items():
        if covering_groups:
            unique_constraints.add(tuple(sorted(covering_groups)))
            
    for groups in unique_constraints:
        model.Add(sum(x[j] for j in groups) >= 1)
    
    # 4. Solve once to get optimal size
    solver = cp_model.CpSolver()
    
    # Phase 1: Find one
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return
        
    min_cost = int(solver.ObjectiveValue())
    print(f"Optimal size found: {min_cost}")
    
    # Phase 2: Find all
    model.Add(objective == min_cost)

    if hasattr(model, "ClearObjective"):
        model.ClearObjective()
    else:
        model.Proto().ClearField('objective')
    
    # Collect selected group indices
    class LimitedSolutionPrinter(cp_model.CpSolverSolutionCallback):
        def __init__(self, variables, max, callback):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self.__variables = variables
            self.__max = max
            self.__callback = callback
            self.__solution_count = 0

        def on_solution_callback(self):
            if self.__solution_count >= self.__max:
                self.StopSearch()
                return
                
            self.__solution_count += 1
            selected = [j for j in self.__variables if self.Value(self.__variables[j]) == 1]
            if self.__callback:
                self.__callback(selected)
        
        def solution_count(self):
            return self.__solution_count

    solution_printer = LimitedSolutionPrinter(x, max, callback)
    solver.parameters.enumerate_all_solutions = True
    
    try:
        solver.Solve(model, solution_printer)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    
def solve_gurobi(n_groups, groups_covering_pair, max=1, callback=None):
    import gurobipy as gp
    from gurobipy import GRB
    
    try:
        model = gp.Model("SetCover")
        model.setParam('OutputFlag', 0)
        
        # Configure solution pool for multiple optimal solutions
        model.setParam('PoolSearchMode', 2)
        model.setParam('PoolSolutions', max)
        model.setParam('PoolGapAbs', 0.5)

        # 1. Build selection variables
        x = model.addVars(n_groups, vtype=GRB.BINARY, name="x")
        
        # 2. Minimize selected groups
        model.setObjective(x.sum(), GRB.MINIMIZE)
        
        # 3. Add pair-coverage constraints
        unique_constraints = set()
        for p_idx, covering_groups in groups_covering_pair.items():
            if covering_groups:
                unique_constraints.add(tuple(sorted(covering_groups)))
                
        for groups in unique_constraints:
            model.addConstr(gp.quicksum(x[j] for j in groups) >= 1)
            
        # 4. Solve model
        try:
            model.optimize()
        except KeyboardInterrupt:
            print("\nInterrupted by user.")

        if model.SolCount > 0:
            print(f"Optimal size found: {int(model.ObjVal)}")
            nSolutions = min(model.SolCount, max)
            for e in range(nSolutions):
                model.setParam('SolutionNumber', e)
                selected = [j for j in range(n_groups) if x[j].Xn > 0.5]
                if callback:
                    callback(selected)

    except Exception as e:
        print(f"Error: Gurobi failed: {e}")

def minimal_set(csv_path=None, solver_name='ortools', max=1):
    """
    Find minimal sets of quandles that distinguish all knot pairs.
    """
    if csv_path is None:
        csv_path = os.path.join(os.path.dirname(__file__), 'io', 'turbo_results.csv')

    output_path = os.path.join(os.path.dirname(__file__), 'io', 'minimal_set.txt')

    # 1. Load input data
    with open(csv_path, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        quandle_names = headers[1:]
        rows = list(reader)

    knots = [r[0] for r in rows]
    data = [r[1:] for r in rows]
    n_quandles = len(quandle_names)
    n_knots = len(knots)

    # 2. Build distinguishable knot pairs
    full_signatures = [tuple(data[i]) for i in range(n_knots)]
    knot_groups = defaultdict(list)
    for i, sig in enumerate(full_signatures):
        knot_groups[sig].append(i)
        
    knot_group_id = [-1] * n_knots
    for gid, (sig, indices) in enumerate(knot_groups.items()):
        for idx in indices:
            knot_group_id[idx] = gid
            
    pairs_to_distinguish = []
    for i in range(n_knots):
        for j in range(i + 1, n_knots):
            if knot_group_id[i] != knot_group_id[j]:
                pairs_to_distinguish.append((i, j))
                
    total_pairs = len(pairs_to_distinguish)
    print(f"Distinguishing {total_pairs} pairs from {n_knots} knots...")

    # 3. Group equivalent quandle columns
    col_map = defaultdict(list)
    for c in range(n_quandles):
        col_values = tuple(data[k][c] for k in range(n_knots))
        col_map[col_values].append(c)
        
    unique_cols = list(col_map.values()) 
    n_unique_quandles = len(unique_cols)
    repr_indices = [g[0] for g in unique_cols]
    
    # 4. Build reduced coverage matrix
    reduced_matrix = []
    for k in range(n_knots):
        row = [data[k][repr_indices[j]] for j in range(n_unique_quandles)]
        reduced_matrix.append(row)

    group_coverage = [set() for _ in range(n_unique_quandles)]
    groups_covering_pair = defaultdict(list)
    
    for p_idx, (k1, k2) in enumerate(pairs_to_distinguish):
        row1 = reduced_matrix[k1]
        row2 = reduced_matrix[k2]
        
        diff_indices = [j for j, (v1, v2) in enumerate(zip(row1, row2)) if v1 != v2]
        
        groups_covering_pair[p_idx] = diff_indices
        for j in diff_indices:
            group_coverage[j].add(p_idx)

    # 5. Run set-cover optimization
    print(f"Distinguishing by {solver_name}...")
    
    # Initialize output file
    with open(output_path, 'w') as f:
        f.write(f"Distinguishing {total_pairs} pairs from {n_knots} knots...\n")
        f.write(f"Solver: {solver_name}\n\n")
        
        solution_idx = 0
        
        def on_solution(final_selected):
            nonlocal solution_idx
            solution_idx += 1
            
            # Accumulate lines for one solution
            sol_lines = []
            sol_lines.append(f"Solution #{solution_idx}:")
            print(f"Processing solution #{solution_idx}...")
            
            # Count pair coverage within this solution
            pair_counts = [0] * total_pairs
            for group_j in final_selected:
                for p_idx in group_coverage[group_j]:
                    pair_counts[p_idx] += 1
                            
            for idx, group_j in enumerate(final_selected):
                group_indices = unique_cols[group_j]
                names = [quandle_names[c] for c in group_indices]
                
                total_count = len(group_coverage[group_j])
                
                unique_pairs_indices = [p_idx for p_idx in group_coverage[group_j] 
                                        if pair_counts[p_idx] == 1]
                
                uni_count = len(unique_pairs_indices)
                msg = f"{idx+1}. {names[0]} (total {total_count}, unique {uni_count})"
                if len(names) > 1:
                    msg += f" (or {', '.join(names[1:])})"
                sol_lines.append(msg)
                
                if unique_pairs_indices:
                    unique_pairs_indices.sort()
                    for i, p_idx in enumerate(unique_pairs_indices[:30]):
                        k1_idx, k2_idx = pairs_to_distinguish[p_idx]
                        k1_name = knots[k1_idx].replace('.json', '')
                        k2_name = knots[k2_idx].replace('.json', '')
                        sol_lines.append(f"   {k1_name}, {k2_name}")
                    
                    if len(unique_pairs_indices) > 30:
                        sol_lines.append(f"   and {len(unique_pairs_indices) - 30} more...")
            
            # Write solution block
            f.write('\n'.join(sol_lines) + '\n\n')
            f.flush()

        start_time = time.time()
        
        if solver_name == 'ortools':
            solve_ortools(n_unique_quandles, groups_covering_pair, max=max, callback=on_solution)
        else:
            solve_gurobi(n_unique_quandles, groups_covering_pair, max=max, callback=on_solution)
            
        duration = time.time() - start_time
        print(f"Solver finished in {duration:.2f}s")
        
        if solution_idx == 0:
            f.write("No solutions found!")
        else:
            f.write(f"\nSolver finished in {duration:.2f}s. Total {solution_idx} minimal sets found!")
    
    rel_path = os.path.relpath(output_path, os.getcwd())
    print(f"\nResult saved to {rel_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Find minimal set of quandles')
    parser.add_argument('-s', '--solver', choices=['ortools', 'gurobi'], default='ortools', 
                        help='Solver to use (ortools or gurobi)')
    parser.add_argument('-m', '--max', type=int, default=1, 
                        help='Maximum number of solutions to find')
    args = parser.parse_args()
    
    minimal_set(solver_name=args.solver, max=args.max)
