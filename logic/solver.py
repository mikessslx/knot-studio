import itertools
import math
from typing import Dict, List, Callable, Optional, Tuple

# region Validation Helpers

def _validate_quandle(quandle: Dict) -> None:
    if "elements" not in quandle or "operation_table" not in quandle:
        raise ValueError("Invalid quandle: missing 'elements' or 'operation_table'.")
    
    elements = quandle["elements"]
    op_table = quandle["operation_table"]
    k = len(elements)
    
    if len(elements) != len(set(elements)):
        raise ValueError("Invalid quandle: 'elements' must be unique.")
    
    if len(op_table) != k or any(len(row) != k for row in op_table):
        raise ValueError(f"Invalid quandle: 'operation_table' must be {k}x{k}.")
    
    for row in op_table:
        for val in row:
            if val not in elements:
                raise ValueError(f"Invalid quandle: operation_table value {val} is not in elements.")

def _validate_knot(knot: Dict) -> None:
    if "arcs" not in knot or "crossings" not in knot:
        raise ValueError("Invalid knot: missing 'arcs' or 'crossings'.")
    
    arcs = knot["arcs"]
    
    if len(arcs) != len(set(arcs)):
        raise ValueError("Invalid knot: arcs must be unique.")
    
    for idx, crossing in enumerate(knot["crossings"]):
        required = ["type", "over", "under_in", "under_out"]
        if not all(key in crossing for key in required):
            raise ValueError(f"Invalid knot: crossing {idx} missing keys {required}.")
        if crossing["type"] not in ["positive", "negative"]:
            raise ValueError(f"Invalid knot: crossing {idx} has type {crossing['type']}.")
        for arc_key in ["over", "under_in", "under_out"]:
            arc_id = crossing[arc_key]
            if arc_id not in arcs:
                raise ValueError(f"Invalid knot: crossing {idx} {arc_key}={arc_id} not in arcs.")

def _validate_colorings(colorings: List[Dict], quandle: Dict, knot: Dict) -> None:
    elements = quandle["elements"]
    arcs = knot["arcs"]

    for idx, coloring in enumerate(colorings):
        if set(coloring.keys()) != set(arcs):
            raise ValueError(f"Invalid coloring {idx}: missing arcs {set(arcs) - set(coloring.keys())}.")
        
        for val in coloring.values():
            if val not in elements:
                raise ValueError(f"Invalid coloring {idx}: value {val} not in elements.")

def _build_inverse_tables(op_table_indices: List[List[int]], k: int) -> tuple:
    # left_inv[b][c] -> a
    left_inv = [[-1] * k for _ in range(k)]
    
    # right_inv[a][c] -> [b...]
    right_inv = [[[] for _ in range(k)] for _ in range(k)]
    
    for a in range(k):
        for b in range(k):
            c = op_table_indices[a][b]
            
            # Left inverse from known b and c
            left_inv[b][c] = a
            
            # Right inverse from known a and c
            right_inv[a][c].append(b)
            
    return left_inv, right_inv
    
def _is_prime(n: int) -> bool:
    if n <= 1: return False
    if n <= 3: return True
    if n % 2 == 0 or n % 3 == 0: return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True

def solve_linear_system(matrix: List[List[int]], p: int) -> List[List[int]]:
    if not matrix:
        return []
        
    n_rows = len(matrix)
    n_cols = len(matrix[0])
    
    m = [row[:] for row in matrix]
    pivots = [] 
    next_row = 0
    
    # Forward elimination
    for col in range(n_cols):
        if next_row >= n_rows:
            break
            
        pivot_row = -1
        for r in range(next_row, n_rows):
            if m[r][col] % p != 0:
                pivot_row = r
                break
        
        if pivot_row == -1:
            continue
            
        m[next_row], m[pivot_row] = m[pivot_row], m[next_row]
        pivot_val = m[next_row][col]
        inv = pow(pivot_val, p - 2, p)
        m[next_row] = [(x * inv) % p for x in m[next_row]]

        # Eliminate other rows
        for r in range(n_rows):
            if r != next_row and m[r][col] != 0:
                factor = m[r][col]
                m[r] = [(m[r][k] - factor * m[next_row][k]) % p for k in range(n_cols)]
        
        pivots.append((next_row, col))
        next_row += 1

    # Find basis vectors
    pivot_cols = {c for r, c in pivots}
    free_vars = [c for c in range(n_cols) if c not in pivot_cols]
    
    # Back substitution to build basis vectors
    basis = []
    
    for free_var in free_vars:
        sol = [0] * n_cols
        sol[free_var] = 1
        for r, c in pivots:
            coef = m[r][free_var]
            sol[c] = (-coef * sol[free_var]) % p
        basis.append(sol)
        
    return basis

def _build_linear_matrix(knot: Dict, n: int, t: int, modulo: bool = False) -> List[List[int]]:
    arcs = knot['arcs']
    crossings = knot['crossings']
    arc_to_idx = {arc: i for i, arc in enumerate(arcs)}
    matrix = []
    one_minus_t = (1 - t) % n if modulo else 1 - t

    def add(row: List[int], idx: int, value: int) -> None:
        if modulo:
            row[idx] = (row[idx] + value) % n
        else:
            row[idx] += value

    for crossing in crossings:
        row = [0] * len(arcs)
        u_in = arc_to_idx[crossing['under_in']]
        u_out = arc_to_idx[crossing['under_out']]
        over = arc_to_idx[crossing['over']]

        if crossing['type'] == 'positive':
            add(row, u_in, t)
            add(row, over, one_minus_t)
            add(row, u_out, -1)
        else:
            add(row, u_out, t)
            add(row, over, one_minus_t)
            add(row, u_in, -1)

        matrix.append(row)

    return matrix

def _snf_solution_count(matrix: List[List[int]], n: int, n_vars: int) -> int:
    if n_vars == 0:
        return 1
    if not matrix:
        return n ** n_vars

    A = [row[:] for row in matrix]
    nrows = len(A)
    ncols = n_vars

    for p in range(min(nrows, ncols)):
        for _ in range(500):
            min_val, min_pos = None, None
            for r in range(p, nrows):
                for c in range(p, ncols):
                    if A[r][c] != 0 and (min_val is None or abs(A[r][c]) < abs(min_val)):
                        min_val = A[r][c]
                        min_pos = (r, c)

            if min_pos is None:
                break

            r, c = min_pos
            if r != p:
                A[p], A[r] = A[r], A[p]
            if c != p:
                for row in A:
                    row[p], row[c] = row[c], row[p]
            if A[p][p] < 0:
                A[p] = [-x for x in A[p]]

            d = A[p][p]
            changed = False
            for r in range(nrows):
                if r != p and A[r][p] != 0:
                    q = A[r][p] // d
                    for k in range(ncols):
                        A[r][k] -= q * A[p][k]
                    if A[r][p] != 0:
                        changed = True

            for c in range(ncols):
                if c != p and A[p][c] != 0:
                    q = A[p][c] // d
                    for r in range(nrows):
                        A[r][c] -= q * A[r][p]
                    if A[p][c] != 0:
                        changed = True

            if not changed:
                break

    count = 1
    for i in range(ncols):
        if i < nrows and A[i][i] != 0:
            count *= math.gcd(abs(A[i][i]), n)
        else:
            count *= n
    return count

def _detect_linear_params(quandle: Dict) -> Optional[Tuple[int, int]]:
    elements = quandle['elements']
    n = len(elements)
    
    # Turbo mode: check name first
    name = quandle.get('name', '')
    if name.startswith('Dihedral('):
        # Dihedral quandle
        try:
            n_val = int(name[9:-1])
            if n == n_val:
                return n, n - 1
        except:
            pass
            
    if name.startswith('Alexander(Z'):
        # Alexander quandle
        try:
            parts = name.split(',')
            q_part = parts[0][11:]
            t_part = parts[1].split('=')[1][:-1]
            
            q_val = int(q_part)
            t_val = int(t_part)
            
            if n == q_val:
                return n, t_val
        except:
            pass

    # Fallback to brute-force detection
    op_table = quandle.get('operation_table')
    if not op_table:
        return None

    if sorted(elements) != list(range(n)):
        return None
        
    t = op_table[1][0]
    
    # Check operation table consistency
    one_minus_t = (1 - t) % n
    
    for x in range(n):
        for y in range(n):
            expected = (t * x + one_minus_t * y) % n
            if op_table[x][y] != expected:
                return None
                
    return n, t

# endregion

# region Coloring Solvers

def enum_solver(quandle: Dict, knot: Dict, turbo: bool = False, stop: Callable = None, **kwargs) -> List[Dict]:
    elements = quandle["elements"]
    op_table = quandle["operation_table"]
    arcs = knot["arcs"]
    crossings = knot["crossings"]
    m = len(arcs)
    
    valid_colorings = []
    elem_to_index = {e: i for i, e in enumerate(elements)}
    
    # Turbo mode: fix the first arc to the first color
    if turbo:
        iterables = [[elements[0]]] + [elements] * (m - 1)
    else:
        iterables = [elements] * m
        
    all_combinations = itertools.product(*iterables)

    for combo in all_combinations:
        if stop:
            stop()
        coloring = {arc: val for arc, val in zip(arcs, combo)}
        valid = True

        for crossing in crossings:
            c_type = crossing["type"]
            over_arc = crossing["over"]
            under_in_arc = crossing["under_in"]
            under_out_arc = crossing["under_out"]

            a = coloring[over_arc]
            b = coloring[under_in_arc]
            c = coloring[under_out_arc]

            idx_a = elem_to_index[a]
            idx_b = elem_to_index[b]
            idx_c = elem_to_index[c]

            if c_type == "positive":
                if op_table[idx_b][idx_a] != c:
                    valid = False
                    break
            elif c_type == "negative":
                if op_table[idx_c][idx_a] != b:
                    valid = False
                    break

        if valid:
            valid_colorings.append(coloring)
    
    return valid_colorings

def dfs_solver(quandle: Dict, knot: Dict, turbo: bool = False, stop: Callable = None, **kwargs) -> List[Dict]:
    elements = quandle["elements"]
    op_table = quandle["operation_table"]
    arcs = knot["arcs"]
    crossings = knot["crossings"]
    
    m = len(arcs)
    k = len(elements)
    
    elem_to_idx = {e: i for i, e in enumerate(elements)}
    arc_to_idx = {arc: i for i, arc in enumerate(arcs)}
    
    # Precompute operation table indices
    op_table_indices = [[elem_to_idx[val] for val in row] for row in op_table]
    
    # Build inverse tables
    left_inv, right_inv = _build_inverse_tables(op_table_indices, k)
    
    # Adjacency list for ordering
    adj = [[] for _ in range(m)]
    
    # Precompute crossing tuples
    crossing_tuples = []
    for idx, crossing in enumerate(crossings):
        u_in = arc_to_idx[crossing["under_in"]]
        u_out = arc_to_idx[crossing["under_out"]]
        over = arc_to_idx[crossing["over"]]
        is_positive = 1 if crossing["type"] == "positive" else 0
        crossing_tuples.append((u_in, u_out, over, is_positive))
        
        # Build adjacency
        adj[u_in].append(idx)
        adj[u_out].append(idx)
        adj[over].append(idx)
    
    # Connectivity-based variable ordering
    sorted_arc_indices = []
    visited = [False] * m
    
    # Start from arc 0
    start_node = 0
    visited[start_node] = True
    sorted_arc_indices.append(start_node)
    
    while len(sorted_arc_indices) < m:
        best_candidate = -1
        max_connected_score = -1
        # Tie-breaker by degree
        max_degree = -1
        
        for i in range(m):
            if not visited[i]:
                # Score by visited neighbors
                score = 0
                for cidx in adj[i]:
                    ct = crossing_tuples[cidx]
                    if visited[ct[0]]: score += 1
                    if visited[ct[1]]: score += 1
                    if visited[ct[2]]: score += 1
                
                degree = len(adj[i])
                
                if score > max_connected_score or (score == max_connected_score and degree > max_degree):
                    max_connected_score = score
                    best_candidate = i
                    max_degree = degree
        
        if best_candidate != -1:
            visited[best_candidate] = True
            sorted_arc_indices.append(best_candidate)
        else:
            # Disconnected component fallback
            for i in range(m):
                if not visited[i]:
                    visited[i] = True
                    sorted_arc_indices.append(i)
                    break
    
    # Build position mapping
    arc_to_position = [0] * m
    for pos, arc_idx in enumerate(sorted_arc_indices):
        arc_to_position[arc_idx] = pos
    
    # Build checks at the max position index
    checks = [[] for _ in range(m)]
    for ct in crossing_tuples:
        u_in_pos = arc_to_position[ct[0]]
        u_out_pos = arc_to_position[ct[1]]
        over_pos = arc_to_position[ct[2]]
        max_pos = max(u_in_pos, u_out_pos, over_pos)
        checks[max_pos].append((u_in_pos, u_out_pos, over_pos, ct[3]))
    
    valid_colorings = []
    solution_count = 0
    current_coloring = [-1] * m # Indexed by position
    all_colors = list(range(k))
    
    def backtrack(position):
        if stop:
            stop()
        nonlocal solution_count
        if position == m:
            if turbo:
                solution_count += 1
            else:
                coloring = {arcs[sorted_arc_indices[i]]: elements[current_coloring[i]] for i in range(m)}
                valid_colorings.append(coloring)
            return
        
        # Turbo mode: fix the first arc to the first color
        if turbo and position == 0:
            current_coloring[0] = 0
            backtrack(1)
            current_coloring[0] = -1
            return
        
        # Lookahead / Deduction
        forced_val = -1
        for chk in checks[position]:
            c_in, c_out, c_over, c_pos = chk
            
            # Case 1: position is u_out (max), u_in & over are known
            if c_out == position and c_in < position and c_over < position:
                v_in, v_over = current_coloring[c_in], current_coloring[c_over]
                if c_pos == 1:
                    forced_val = op_table_indices[v_in][v_over]
                else:
                    forced_val = left_inv[v_over][v_in]
                break
            
            # Case 2: position is u_in (max), u_out & over are known
            elif c_in == position and c_out < position and c_over < position:
                v_out, v_over = current_coloring[c_out], current_coloring[c_over]
                if c_pos == 0:
                    forced_val = op_table_indices[v_out][v_over]
                else:
                    forced_val = left_inv[v_over][v_out]
                break
            
            # Case 3: position is over (max), u_in & u_out known
            elif c_over == position and c_in < position and c_out < position:
                v_in, v_out = current_coloring[c_in], current_coloring[c_out]
                if c_pos == 1:
                    sols = right_inv[v_in][v_out]
                else:
                    sols = right_inv[v_out][v_in]
                if len(sols) == 1:
                    forced_val = sols[0]
                    break
        
        candidates = [forced_val] if forced_val != -1 else all_colors
        
        for color_idx in candidates:
            current_coloring[position] = color_idx
            
            # Verify constraints
            valid = True
            for chk in checks[position]:
                c_in, c_out, c_over, c_pos = chk
                v_in = current_coloring[c_in]
                v_out = current_coloring[c_out]
                v_over = current_coloring[c_over]
                
                if c_pos == 1:
                    if op_table_indices[v_in][v_over] != v_out:
                        valid = False
                        break
                else:
                    if op_table_indices[v_out][v_over] != v_in:
                        valid = False
                        break
            
            if valid:
                backtrack(position + 1)
            
            current_coloring[position] = -1
    
    backtrack(0)
    
    if turbo:
        return solution_count
    return valid_colorings

def algebraic_solver(quandle: Dict, knot: Dict, turbo: bool = False, stop: Callable = None, **kwargs) -> List[Dict]:
    """
    Implement the algebraic method for solving quandle colorings:
    1. Variable modeling
    2. Equation modeling with closure
    3. Axiomatic simplification
    4. Space enumeration and verification
    """
    elements = quandle["elements"]
    op_table = quandle["operation_table"]
    arcs = knot["arcs"]
    crossings = knot["crossings"]
    k = len(elements)
    
    # Precompute operation table indices
    elem_to_idx = {e: i for i, e in enumerate(elements)}
    op_table_indices = [[elem_to_idx[val] for val in row] for row in op_table]
    
    def apply_op_idx(i1, i2):
        return op_table_indices[i1][i2]

    # Symbolic term representation
    # Term = ("var", arc_id) | ("const", idx) | ("op", left_term, right_term)
    def simplify_term(term):
        if term[0] == "op":
            _, left, right = term
            left = simplify_term(left)
            right = simplify_term(right)
            
            # Axiom 1: Idempotence
            if left == right:
                return left
            
            # Axiom 3: Self-distributivity
            if left[0] == "op" and right[0] == "op":
                # left = (op, A, B), right = (op, C, D)
                if left[1] == right[1]:
                    new_inner = simplify_term(("op", left[2], right[2]))
                    return simplify_term(("op", left[1], new_inner))
            
            # Constant folding
            if left[0] == "const" and right[0] == "const":
                result_idx = apply_op_idx(left[1], right[1])
                return ("const", result_idx)
                
            return ("op", left, right)
        return term

    def get_term_vars(term):
        vars_ = set()
        stack = [term]
        while stack:
            t = stack.pop()
            if t[0] == "var":
                vars_.add(t[1])
            elif t[0] == "op":
                stack.append(t[1])
                stack.append(t[2])
        return vars_

    def substitute_term(term, target_var, replacement):
        if term[0] == "var":
            return replacement if term[1] == target_var else term
        elif term[0] == "op":
            new_left = substitute_term(term[1], target_var, replacement)
            new_right = substitute_term(term[2], target_var, replacement)
            return simplify_term(("op", new_left, new_right))
        return term

    def eval_term(term, assignment):
        if term[0] == "const":
            return term[1]
        if term[0] == "var":
            return assignment[term[1]]
        if term[0] == "op":
            left_val = eval_term(term[1], assignment)
            right_val = eval_term(term[2], assignment)
            return apply_op_idx(left_val, right_val)
        raise ValueError(f"Invalid term: {term}.")

    # Step 1 and 2: Modeling
    independent_vars = set(arcs)
    current_terms = {arc: ("var", arc) for arc in arcs}
    
    # Store constraints as (lhs_term, rhs_term)
    raw_constraints = []

    # Turbo mode: fix the first arc to the first color
    if turbo:
        fixed_arc = arcs[0]
        fixed_idx = 0
        replacement = ("const", fixed_idx)
        
        if fixed_arc in independent_vars:
            independent_vars.remove(fixed_arc)
            # Substitute immediately
            for arc in arcs:
                current_terms[arc] = substitute_term(current_terms[arc], fixed_arc, replacement)

    # Build initial constraints from crossings
    for crossing in crossings:
        c_type = crossing["type"]
        u_in = crossing["under_in"]
        u_out = crossing["under_out"]
        over = crossing["over"]
        
        t_in = current_terms[u_in]
        t_over = current_terms[over]
        t_out = current_terms[u_out]
        
        if c_type == "positive":
            # u_in * over = u_out
            rhs = simplify_term(("op", t_in, t_over))
            lhs = t_out
        else:
            # u_out * over = u_in
            rhs = simplify_term(("op", t_out, t_over))
            lhs = t_in
            
        raw_constraints.append((lhs, rhs))

    # Step 3: Simplification
    def count_vars_in_term(term, counter):
        stack = [term]
        while stack:
            t = stack.pop()
            if t[0] == "var":
                counter[t[1]] = counter.get(t[1], 0) + 1
            elif t[0] == "op":
                stack.append(t[1])
                stack.append(t[2])

    # Main elimination loop
    active_constraints = raw_constraints
    
    while True:
        if stop:
            stop()
        # 1. Identify candidates for elimination
        candidates = []
        
        # Count variable frequencies in active constraints
        var_counts = {}
        for lhs, rhs in active_constraints:
            count_vars_in_term(lhs, var_counts)
            count_vars_in_term(rhs, var_counts)
            
        if not var_counts:
            break
            
        for i, (lhs, rhs) in enumerate(active_constraints):
            # Check lhs = var
            if lhs[0] == "var":
                v = lhs[1]
                if v in independent_vars and v not in get_term_vars(rhs):
                    candidates.append((v, rhs, i))
                    
            # Check rhs = var
            elif rhs[0] == "var":
                v = rhs[1]
                if v in independent_vars and v not in get_term_vars(lhs):
                    candidates.append((v, lhs, i))
        
        if not candidates:
            break
            
        # 2. Pick best candidate by frequency
        best_cand = None
        min_score = float('inf')
        
        for v, expr, idx in candidates:
            score = var_counts.get(v, 0) 
            if score < min_score:
                min_score = score
                best_cand = (v, expr, idx)
        
        if not best_cand:
            break
            
        # 3. Eliminate the selected variable
        target_var, target_expr, constr_idx = best_cand
        
        # Remove the defining constraint
        active_constraints.pop(constr_idx)
        independent_vars.remove(target_var)
        
        # Substitute in constraints
        new_constraints = []
        for lhs, rhs in active_constraints:
            new_lhs = substitute_term(lhs, target_var, target_expr)
            new_rhs = substitute_term(rhs, target_var, target_expr)
            new_constraints.append((new_lhs, new_rhs))
            
        active_constraints = new_constraints
        
        # Update global term definitions
        for arc in arcs:
            current_terms[arc] = substitute_term(current_terms[arc], target_var, target_expr)

    # Remaining active constraints are final constraints
    constraints = active_constraints
    unique_constraints = list(set(constraints))

    # Step 4: Enumeration
    valid_colorings = []
    solution_count = 0
    sorted_indep = sorted(list(independent_vars))
    n_indep = len(sorted_indep)
    
    # Use bytecode-like lists (opcode, value)
    def compile_to_bytecode(term, var_map):
        code = []
        def _visit(t):
            if t[0] == "const":
                code.append((0, t[1]))
            elif t[0] == "var":
                code.append((1, var_map[t[1]]))
            elif t[0] == "op":
                _visit(t[1]) # Left
                _visit(t[2]) # Right
                code.append((2, 0))
        _visit(term)
        return code

    var_map = {v: i for i, v in enumerate(sorted_indep)}
    
    compiled_constraints = []
    for c1, c2 in unique_constraints:
        compiled_constraints.append((
            compile_to_bytecode(c1, var_map),
            compile_to_bytecode(c2, var_map)
        ))
        
    compiled_terms = {arc: compile_to_bytecode(current_terms[arc], var_map) for arc in arcs}
    
    # Stack-based evaluator
    def fast_eval(bytecode, assignment_arr):
        stack = []
        for op, val in bytecode:
            if op == 0: # CONST
                stack.append(val)
            elif op == 1: # VAR
                stack.append(assignment_arr[val])
            else: # OP
                r = stack.pop()
                l = stack.pop()
                stack.append(op_table_indices[l][r])
        return stack[0]

    # Integer counting for assignments
    total = k ** n_indep
    
    # Pre-allocate assignment array
    assignment_arr = [0] * n_indep
    
    for i in range(total):
        if stop and i % 1000 == 0:
            stop()
        temp = i
        for j in range(n_indep):
            assignment_arr[j] = temp % k
            temp //= k
            
        # Check constraints
        valid = True
        for code1, code2 in compiled_constraints:
            if fast_eval(code1, assignment_arr) != fast_eval(code2, assignment_arr):
                valid = False
                break
        
        if valid:
            if turbo:
                solution_count += 1
            else:
                # Construct full coloring
                coloring = {}
                for arc in arcs:
                    idx = fast_eval(compiled_terms[arc], assignment_arr)
                    coloring[arc] = elements[idx]
                valid_colorings.append(coloring)
            
    if turbo:
        return solution_count
    return valid_colorings

def propagation_solver(quandle: Dict, knot: Dict, turbo: bool = False, stop: Callable = None, **kwargs) -> List[Dict]:
    """
    Implement constraint propagation for quandle colorings:
    1. Use a global history stack
    2. Avoid frequent list allocations during recursion
    """
    elements = quandle["elements"]
    op_table = quandle["operation_table"]
    arcs = knot["arcs"]
    crossings = knot["crossings"]
    
    m = len(arcs)
    k = len(elements)
    
    elem_to_idx = {e: i for i, e in enumerate(elements)}
    arc_to_idx = {arc: i for i, arc in enumerate(arcs)}
    op_table_indices = [[elem_to_idx[val] for val in row] for row in op_table]
    
    # Build inverse tables
    left_inv, right_inv = _build_inverse_tables(op_table_indices, k)
    
    # Precompute crossing structures
    # crossing_structs[i] = (type, u_in, u_out, over)
    crossing_structs = []
    # arc_in_crossings[arc_idx] = [crossing_idx, ...]
    arc_in_crossings = [[] for _ in range(m)]
    
    for c_idx, crossing in enumerate(crossings):
        u_in = arc_to_idx[crossing["under_in"]]
        u_out = arc_to_idx[crossing["under_out"]]
        over = arc_to_idx[crossing["over"]]
        
        crossing_structs.append({
            "id": c_idx,
            "type": crossing["type"],
            "u_in": u_in,
            "u_out": u_out,
            "over": over
        })
        
        arc_in_crossings[u_in].append(c_idx)
        arc_in_crossings[u_out].append(c_idx)
        arc_in_crossings[over].append(c_idx)

    valid_colorings = []
    solution_count = 0
    current_coloring = [-1] * m
    
    # History stack for backtracking
    history_stack = []

    def propagate(start_arc_idx):
        """
        Propagate constraints from start_arc_idx.
        Return True if consistent, False if conflict.
        Record changes in history_stack.
        """
        # Local stack for propagation traversal
        stack = [start_arc_idx]
        
        while stack:
            curr_arc = stack.pop()
            
            # Check crossings involving this arc
            for c_idx in arc_in_crossings[curr_arc]:
                c = crossing_structs[c_idx]
                
                u_in, u_out, over = c["u_in"], c["u_out"], c["over"]
                v_in, v_out, v_over = current_coloring[u_in], current_coloring[u_out], current_coloring[over]
                
                # Count known assignments
                known_count = 0
                if v_in != -1: known_count += 1
                if v_out != -1: known_count += 1
                if v_over != -1: known_count += 1
                
                if known_count == 3:
                    # Check consistency
                    if c["type"] == "positive":
                        if op_table_indices[v_in][v_over] != v_out:
                            return False
                    else:
                        if op_table_indices[v_out][v_over] != v_in:
                            return False
                            
                elif known_count == 2:
                    # Deduce the third value
                    target_idx = -1
                    new_val = -1
                    
                    if v_out == -1: # Deduce u_out
                        if c["type"] == "positive" and v_in != -1 and v_over != -1:
                            target_idx = u_out
                            new_val = op_table_indices[v_in][v_over]
                        elif c["type"] == "negative" and v_in != -1 and v_over != -1:
                             target_idx = u_out
                             new_val = left_inv[v_over][v_in]
                    
                    elif v_in == -1: # Deduce u_in
                         if c["type"] == "negative" and v_out != -1 and v_over != -1:
                            target_idx = u_in
                            new_val = op_table_indices[v_out][v_over]
                         elif c["type"] == "positive" and v_out != -1 and v_over != -1:
                            target_idx = u_in
                            new_val = left_inv[v_over][v_out]
                    
                    elif v_over == -1: # Deduce over
                        if v_in != -1 and v_out != -1:
                            if c["type"] == "positive":
                                sols = right_inv[v_in][v_out]
                                if len(sols) == 1:
                                    target_idx = over
                                    new_val = sols[0]
                            else:
                                sols = right_inv[v_out][v_in]
                                if len(sols) == 1:
                                    target_idx = over
                                    new_val = sols[0]
                    
                    # Apply deduction
                    if target_idx != -1:
                        # Check for conflicts
                        curr_target_val = current_coloring[target_idx]
                        if curr_target_val != -1:
                            if curr_target_val != new_val:
                                return False
                        else:
                            # Assign and record
                            current_coloring[target_idx] = new_val
                            history_stack.append(target_idx)
                            stack.append(target_idx)
                            
        return True

    def solve_recursive():
        if stop:
            stop()
        # 1. Check completion
        try:
            next_arc = current_coloring.index(-1)
        except ValueError:
            # All arcs colored
            if turbo:
                nonlocal solution_count
                solution_count += 1
            else:
                res = {arcs[i]: elements[current_coloring[i]] for i in range(m)}
                valid_colorings.append(res)
            return

        # 2. Variable selection heuristic
        best_arc = -1
        
        # Scan for connected arcs
        for c in crossing_structs:
            u_in, u_out, over = c["u_in"], c["u_out"], c["over"]
            v_in, v_out, v_over = current_coloring[u_in], current_coloring[u_out], current_coloring[over]
            
            if v_in == -1 and v_out == -1 and v_over == -1:
                continue
            
            if v_over == -1:
                best_arc = over
                break
            if v_in == -1:
                best_arc = u_in
                break
            if v_out == -1:
                best_arc = u_out
                break
        
        if best_arc == -1:
            best_arc = next_arc

        # 3. Branching
        # Record history point
        history_ptr = len(history_stack)
        
        for val in range(k):
            current_coloring[best_arc] = val
            history_stack.append(best_arc)
            
            if propagate(best_arc):
                solve_recursive()
            
            # Backtrack
            # Restore changes since history_ptr
            while len(history_stack) > history_ptr:
                idx = history_stack.pop()
                current_coloring[idx] = -1
                
    # Initial setup
    if turbo and len(crossings) > 0:
        c0 = crossing_structs[0]
        over_arc = c0["over"]
        
        # Fix first arc
        current_coloring[over_arc] = 0
        history_stack.append(over_arc)
        
        if propagate(over_arc):
            solve_recursive()
            
    else:
        if turbo and len(crossings) == 0 and m > 0:
             current_coloring[0] = 0
             history_stack.append(0)
             solve_recursive()
        else:
            solve_recursive()

    if turbo:
        return solution_count
    return valid_colorings

def linear_solver(quandle: Dict, knot: Dict, turbo: bool = False, stop: Callable = None, **kwargs) -> List[Dict]:
    """
    Linear algebra solver for Alexander or Dihedral quandles.
    Solve t*x + (1-t)*y - z = 0 mod n.
    """
    # 1. Check prerequisites
    params = _detect_linear_params(quandle)
    if params is None or not _is_prime(params[0]):
        return dfs_solver(quandle, knot, turbo, stop, **kwargs)
        
    n, t = params
    arcs = knot['arcs']
    n_arcs = len(arcs)
    
    # 2. Build linear system Ax = 0
    matrix = _build_linear_matrix(knot, n, t, modulo=True)
        
    # 3. Solve for basis
    if not matrix and n_arcs > 0:
        basis = []
        for i in range(n_arcs):
            vec = [0] * n_arcs
            vec[i] = 1
            basis.append(vec)
    else:
        basis = solve_linear_system(matrix, n)
    dim = len(basis)
    
    # Turbo mode: calculate directly
    if turbo:
        return n ** (dim - 1) if dim > 0 else 0
        
    # 4. Enumerate solutions
    valid_colorings = []
    elements = quandle['elements']
    
    import itertools
    coeffs_iter = itertools.product(range(n), repeat=dim)
    
    for coeffs in coeffs_iter:
        if stop and len(valid_colorings) % 1000 == 0:
            stop()
            
        # Linear combination of basis vectors
        sol = [0] * n_arcs
        for i, c in enumerate(coeffs):
            if c == 0: continue
            basis_vec = basis[i]
            for k in range(n_arcs):
                sol[k] = (sol[k] + c * basis_vec[k]) % n
        
        # Convert to dictionary
        coloring = {arcs[i]: elements[sol[i]] for i in range(n_arcs)}
        valid_colorings.append(coloring)
        
    return valid_colorings

def snf_solver(quandle: Dict, knot: Dict, turbo: bool = False, stop: Callable = None, **kwargs) -> List[Dict]:
    """
    Count colorings of Alexander or Dihedral quandles over Z_n via Smith Normal Form.
    """
    params = _detect_linear_params(quandle)
    if params is None:
        return dfs_solver(quandle, knot, turbo, stop, **kwargs)

    if not turbo:
        if _is_prime(params[0]):
            return linear_solver(quandle, knot, turbo, stop, **kwargs)
        return dfs_solver(quandle, knot, turbo, stop, **kwargs)

    if stop:
        stop()

    n, t = params
    n_arcs = len(knot['arcs'])
    matrix_cache = kwargs.get('matrix_cache')
    if matrix_cache is not None:
        if t not in matrix_cache:
            matrix_cache[t] = _build_linear_matrix(knot, n, t, modulo=False)
        matrix = matrix_cache[t]
    else:
        matrix = _build_linear_matrix(knot, n, t, modulo=False)

    total_count = _snf_solution_count(
        matrix,
        n,
        n_arcs,
    )

    if n_arcs == 0:
        return total_count
    return total_count // n

def compute_quandle_colorings(quandle: Dict, knot: Dict, solver: Callable = enum_solver, stop: Callable = None, **kwargs) -> List[Dict]:
    _validate_quandle(quandle)
    _validate_knot(knot)
    colorings = solver(quandle, knot, stop=stop, **kwargs)
    
    # Skip validation for count-only solvers
    if isinstance(colorings, int):
        return colorings
        
    _validate_colorings(colorings, quandle, knot)
    return colorings

# endregion
