import numpy as np
from typing import List, Dict, Callable, Optional

# region Validation Helpers

def _validate_operation_table(op_table: List[List[int]]) -> None:
    n = len(op_table)
    if n == 0:
        raise ValueError("Invalid operation table: empty.")
    
    for i, row in enumerate(op_table):
        if len(row) != n:
            raise ValueError(f"Invalid operation table: row {i} has length {len(row)}, expected {n}.")
        for val in row:
            if not isinstance(val, int) or val < 0 or val >= n:
                raise ValueError(f"Invalid operation table: element {val} out of range.")

def _validate_group_size(group_size: int) -> None:
    if not isinstance(group_size, int) or group_size <= 0:
        raise ValueError(f"Invalid group size: {group_size}.")

def _build_cocycle_constraints(op_table: List[List[int]], group_size: int) -> List[tuple]:
    n = len(op_table)
    constraints = []
    
    for x in range(n):
        for y in range(n):
            for z in range(n):
                # Compute quandle operations
                x_op_y = op_table[x][y] # x ▷ y
                x_op_z = op_table[x][z] # x ▷ z
                y_op_z = op_table[y][z] # y ▷ z
                
                # Build constraint terms
                terms = {}
                
                # +phi(x, y)
                key = (x, y)
                terms[key] = terms.get(key, 0) + 1
                
                # +phi(x ▷ y, z)
                key = (x_op_y, z)
                terms[key] = terms.get(key, 0) + 1
                
                # -phi(x, z)
                key = (x, z)
                terms[key] = terms.get(key, 0) - 1
                
                # -phi(x ▷ z, y ▷ z)
                key = (x_op_z, y_op_z)
                terms[key] = terms.get(key, 0) - 1
                
                # Normalize coefficients mod group_size and drop zeros
                normalized_terms = []
                for key, coef in terms.items():
                    coef = coef % group_size
                    if coef != 0:
                        normalized_terms.append((coef, key))
                
                # Skip trivial constraints
                if normalized_terms:
                    constraints.append(tuple(normalized_terms))

    # phi(x, x) = 0
    for x in range(n):
        constraints.append(((1, (x, x)),))
    
    # Remove duplicate constraints
    unique_constraints = list(set(constraints))
    
    return unique_constraints

def _pair_to_index(i: int, j: int, n: int) -> int:
    """
    Convert pair (i, j) to a linear index for an n x n matrix.
    """
    return i * n + j

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
    
    # Back substitution to find basis vectors
    basis = []
    
    for free_var in free_vars:
        sol = [0] * n_cols
        sol[free_var] = 1
        for r, c in pivots:
            coef = m[r][free_var]
            sol[c] = (-coef * sol[free_var]) % p
        basis.append(sol)
        
    return basis

def _compute_coboundary_basis(op_table: List[List[int]], p: int) -> List[List[int]]:
    n = len(op_table)
    total_pairs = n * n
    basis = []
    
    # Basis for C^1 uses delta functions e_k(x)
    for k in range(n):
        # Compute image d_1(e_k)
        vec = [0] * total_pairs
        is_zero = True
        
        for x in range(n):
            for y in range(n):
                val = 0
                if x == k: val += 1
                if op_table[x][y] == k: val -= 1
                
                val = val % p
                if val != 0:
                    vec[_pair_to_index(x, y, n)] = val
                    is_zero = False
                    
        if not is_zero:
            basis.append(vec)
            
    return basis

def _compute_quotient_basis(Z2_basis: List[List[int]], B2_basis: List[List[int]], p: int) -> List[List[int]]:
    if not B2_basis:
        return Z2_basis
        
    if not Z2_basis:
        return []

    n_cols = len(Z2_basis[0])

    workspace = [row[:] for row in B2_basis]
    n_rows = len(workspace)
    
    # Triangulate B2
    for r in range(n_rows):
        # Find pivot for this row
        pivot_col = -1
        for c in range(n_cols):
             if workspace[r][c] != 0:
                 pivot_col = c
                 break
        if pivot_col == -1: continue
        
        # Normalize row
        pivot_val = workspace[r][pivot_col]
        inv = pow(pivot_val, p - 2, p)
        workspace[r] = [(x * inv) % p for x in workspace[r]]

        pass

    pivot_rows = [] # List of (row_vector, pivot_col_index)
    
    def reduce_vector(vec):
        v = vec[:]
        for p_row, p_col in pivot_rows:
            if v[p_col] != 0:
                factor = v[p_col]
                v = [(v[k] - factor * p_row[k]) % p for k in range(n_cols)]
        return v
    
    def add_to_basis(vec):
        # Find pivot column
        p_col = -1
        for c in range(n_cols):
            if vec[c] != 0:
                p_col = c
                break
        if p_col == -1:
            return False
        
        # Normalize
        inv = pow(vec[p_col], p - 2, p)
        vec = [(x * inv) % p for x in vec]

        pivot_rows.append((vec, p_col))
        return True

    # Process B2 basis
    for vec in B2_basis:
        pass

    current_basis = [] # List of (pivot_col, vector)
    
    # Build initial basis from B2
    for vec in B2_basis:
        v = vec[:]
        # Reduce against current basis
        for p_col, p_vec in current_basis:
            if v[p_col] != 0:
                factor = v[p_col]
                v = [(v[k] - factor * p_vec[k]) % p for k in range(n_cols)]
        
        # Try to find a new pivot
        pivot_col = -1
        for c in range(n_cols):
            if v[c] != 0:
                pivot_col = c
                break
        
        if pivot_col != -1:
            # Normalize
            inv = pow(v[pivot_col], p - 2, p)
            v = [(x * inv) % p for x in v]
            current_basis.append((pivot_col, v))
            current_basis.sort(key=lambda x: x[0])
            
    H2_basis = []
    
    # Reduce Z2 against current basis
    for vec in Z2_basis:
        v = vec[:]
        # Reduce against current basis
        for p_col, p_vec in current_basis:
            if v[p_col] != 0:
                factor = v[p_col]
                v = [(v[k] - factor * p_vec[k]) % p for k in range(n_cols)]
                
        # If surviving, add a new cohomology class
        pivot_col = -1
        for c in range(n_cols):
            if v[c] != 0:
                pivot_col = c
                break
                
        if pivot_col != -1:
            # Normalize
            inv = pow(v[pivot_col], p - 2, p)
            v = [(x * inv) % p for x in v]
            
            # Add reduced vector to H2_basis
            H2_basis.append(v)
            
            # Add to current basis to filter dependent vectors
            current_basis.append((pivot_col, v))
            current_basis.sort(key=lambda x: x[0])
            
    return H2_basis

# endregion

# region Cocycle Solvers

def enum_cocycle_solver(op_table: List[List[int]], group_size: int, stop: Optional[Callable] = None, **kwargs) -> List[List[List[int]]]:
    n = len(op_table)
    total_pairs = n * n
    
    # Build constraints
    constraints = _build_cocycle_constraints(op_table, group_size)
    
    valid_cocycles = []
    
    # Enumerate all possible assignments
    total_combinations = group_size ** total_pairs
    
    for combo_idx in range(total_combinations):
        if stop and combo_idx % 1000 == 0:
            stop()
        
        # Decode combination index to phi values
        phi_flat = []
        temp = combo_idx
        for _ in range(total_pairs):
            phi_flat.append(temp % group_size)
            temp //= group_size
        
        # Check constraints
        valid = True
        for constraint in constraints:
            total = 0
            for coef, (i, j) in constraint:
                idx = _pair_to_index(i, j, n)
                total += coef * phi_flat[idx]
            if total % group_size != 0:
                valid = False
                break
        
        if valid:
            # Convert flat array to matrix
            phi_matrix = []
            for i in range(n):
                row = []
                for j in range(n):
                    row.append(phi_flat[_pair_to_index(i, j, n)])
                phi_matrix.append(row)
            valid_cocycles.append(phi_matrix)
    
    return valid_cocycles

def linear_cocycle_solver(op_table: List[List[int]], group_size: int, stop: Optional[Callable] = None, just_reps: bool = True, **kwargs) -> List[List[List[int]]]:
    # 1. Check if group_size is prime
    if not _is_prime(group_size):
        return enum_cocycle_solver(op_table, group_size, stop, **kwargs)

    n = len(op_table)
    total_pairs = n * n
    
    # 2. Build linear system and compute Z^2 basis
    raw_constraints = _build_cocycle_constraints(op_table, group_size)
    Z2_basis = []
    if not raw_constraints:
        for i in range(total_pairs):
            vec = [0] * total_pairs
            vec[i] = 1
            Z2_basis.append(vec)
    else:
        matrix = []
        for constraint in raw_constraints:
            row = [0] * total_pairs
            for coef, (i, j) in constraint:
                idx = _pair_to_index(i, j, n)
                row[idx] = (row[idx] + coef) % group_size
            matrix.append(row)
        Z2_basis = solve_linear_system(matrix, group_size)
    
    basis = []
    if just_reps:
        # 3. Compute B^2 basis
        B2_basis = _compute_coboundary_basis(op_table, group_size)
        
        # 4. Compute H^2 = Z^2 / B^2
        H2_basis = _compute_quotient_basis(Z2_basis, B2_basis, group_size)
        basis = H2_basis
    else:
        # Use full Z^2 basis
        basis = Z2_basis

    # 5. Enumerate linear combinations of basis vectors
    if not basis:
        # Only trivial solution
        return [[[0]*n for _ in range(n)]]
        
    # Enumerate solution space
    basis_len = len(basis)
    valid_cocycles = []
    
    import itertools
    coeffs_iter = itertools.product(range(group_size), repeat=basis_len)
    
    for coeffs in coeffs_iter:
        if stop and len(valid_cocycles) % 1000 == 0:
            stop()
            
        # Linear combination of basis vectors
        flat_sol = [0] * total_pairs
        for i, c in enumerate(coeffs):
            if c == 0: continue
            vec = basis[i]
            for k in range(total_pairs):
                flat_sol[k] = (flat_sol[k] + c * vec[k]) % group_size
        
        phi_matrix = []
        for i in range(n):
            phi_matrix.append(flat_sol[i*n : (i+1)*n])
        valid_cocycles.append(phi_matrix)
        
    return valid_cocycles

def compute_cocycle(op_table: List[List[int]], group_size: int, solver: Callable = linear_cocycle_solver, stop: Optional[Callable] = None, **kwargs) -> List[List[List[int]]]:
    """
    Compute all 2-cocycles phi: Q x Q -> A for given Q and A.
    """
    _validate_operation_table(op_table)
    _validate_group_size(group_size)
    
    cocycles = solver(op_table, group_size, stop=stop, **kwargs)
    
    return cocycles

# endregion

# region Cocycle Invariants

def compute_cocycle_invariant(knot: Dict, quandle: Dict, cocycle: List[List[int]], group_size: int, colorings: Optional[List[Dict]] = None, stop: Optional[Callable] = None) -> Dict:
    """
    Compute the cocycle invariant for a knot and 2-cocycle.
    """
    from solver import compute_quandle_colorings, dfs_solver
    
    # Load colorings if missing
    if colorings is None:
        colorings = compute_quandle_colorings(quandle, knot, solver=dfs_solver, stop=stop)
    
    if isinstance(colorings, int):
        raise ValueError("Invalid colorings: expected a list, got a count.")
    
    if len(colorings) == 0:
        return {
            'weights': {},
            'polynomial': '0',
            'is_trivial': True
        }
    
    elements = quandle['elements']
    elem_to_idx = {e: i for i, e in enumerate(elements)}
    
    crossings = knot['crossings']
    arcs = knot['arcs']
    arc_to_idx = {arc: i for i, arc in enumerate(arcs)}
    
    # (under_in_arc_idx, over_arc_idx, sign)
    crossing_tuples = []
    for crossing in crossings:
        u_in_idx = arc_to_idx[crossing['under_in']]
        over_idx = arc_to_idx[crossing['over']]
        sign = 1 if crossing['type'] == 'positive' else -1
        crossing_tuples.append((u_in_idx, over_idx, sign))
    
    num_crossings = len(crossing_tuples)
    
    # colorings_arr[i][j] = color index of arc j in coloring i
    colorings_arr = []
    for coloring in colorings:
        arr = [elem_to_idx[coloring[arc]] for arc in arcs]
        colorings_arr.append(arr)
    
    weight_counts = {}
    raw_weights = []
    
    # Vectorized weight computation
    if len(colorings_arr) > 0:
        C_arr = np.array(colorings_arr, dtype=np.int32)
        Phi = np.array(cocycle, dtype=np.int32)
        
        U_in_indices = np.array([x[0] for x in crossing_tuples], dtype=np.int32)
        Over_indices = np.array([x[1] for x in crossing_tuples], dtype=np.int32)
        Signs = np.array([x[2] for x in crossing_tuples], dtype=np.int32)
        
        # 1. Get colors at under and over arcs
        Colors_U = C_arr[:, U_in_indices]
        Colors_O = C_arr[:, Over_indices]
        
        # 2. Look up Phi values
        Phi_vals = Phi[Colors_U, Colors_O]
        
        # 3. Multiply by signs
        Weighted_Phi = Phi_vals * Signs
        
        # 4. Sum over crossings
        Total_Weights = np.sum(Weighted_Phi, axis=1)
        
        # 5. Modulo
        Raw_Weights_Vec = Total_Weights % group_size
        
        raw_weights = Raw_Weights_Vec.tolist()
        for w in raw_weights:
            weight_counts[w] = weight_counts.get(w, 0) + 1
    
    # Build polynomial string
    polynomial_terms = []
    for weight in sorted(weight_counts.keys()):
        count = weight_counts[weight]
        if weight == 0:
            polynomial_terms.append(str(count))
        elif weight == 1:
            if count == 1:
                polynomial_terms.append('t')
            else:
                polynomial_terms.append(f'{count}t')
        else:
            if count == 1:
                polynomial_terms.append(f't^{weight}')
            else:
                polynomial_terms.append(f'{count}t^{weight}')
    
    polynomial = ' + '.join(polynomial_terms) if polynomial_terms else '0'
    
    # Check if trivial
    is_trivial = len(weight_counts) <= 1
    
    return {
        'weights': weight_counts,
        'raw_weights': raw_weights,
        'polynomial': polynomial,
        'is_trivial': is_trivial,
        'total_colorings': len(colorings)
    }

def compute_all_cocycle_invariant(knot: Dict, quandle: Dict, group_size: int, cocycles: Optional[List[List[List[int]]]] = None, colorings: Optional[List[Dict]] = None, stop: Optional[Callable] = None) -> List[Dict]:
    """
    Compute cocycle invariants for a given knot.
    """
    elements = quandle['elements']
    elem_to_idx = {e: i for i, e in enumerate(elements)}
    
    # Build operation table in integer indices
    op_table = [[elem_to_idx[val] for val in row] for row in quandle['operation_table']]
    
    # Load cocycles if missing
    if cocycles is None:
        cocycles = compute_cocycle(op_table, group_size, solver=linear_cocycle_solver, stop=stop, just_representatives=True)
    
    # Load colorings if missing
    if colorings is None:
        from solver import compute_quandle_colorings, dfs_solver
        colorings = compute_quandle_colorings(quandle, knot, solver=dfs_solver, stop=stop)
    
    if isinstance(colorings, int):
        raise ValueError("Invalid colorings: expected a list, got a count.")
    
    if len(colorings) == 0:
        # No colorings, return trivial results
        results = []
        for idx in range(len(cocycles)):
            results.append({
                'weights': {},
                'polynomial': '0',
                'is_trivial': True,
                'cocycle_index': idx
            })
        return results
    
    crossings = knot['crossings']
    arcs = knot['arcs']
    arc_to_idx = {arc: i for i, arc in enumerate(arcs)}
    
    # (under_in_arc_idx, over_arc_idx, sign)
    crossing_tuples = []
    for crossing in crossings:
        u_in_idx = arc_to_idx[crossing['under_in']]
        over_idx = arc_to_idx[crossing['over']]
        sign = 1 if crossing['type'] == 'positive' else -1
        crossing_tuples.append((u_in_idx, over_idx, sign))

    # colorings_arr[i][j] = color index of arc j in coloring i
    colorings_arr = []
    for coloring in colorings:
        arr = [elem_to_idx[coloring[arc]] for arc in arcs]
        colorings_arr.append(arr)
    
    num_colorings = len(colorings_arr)
    
    results = []
    for idx, cocycle in enumerate(cocycles):
        if stop:
            stop()
        
        weight_counts = {}
        raw_weights = []
        
        if num_colorings > 0:
             C_arr = np.array(colorings_arr, dtype=np.int32)
             Phi = np.array(cocycle, dtype=np.int32)
             
             U_in_indices = np.array([x[0] for x in crossing_tuples], dtype=np.int32)
             Over_indices = np.array([x[1] for x in crossing_tuples], dtype=np.int32)
             Signs = np.array([x[2] for x in crossing_tuples], dtype=np.int32)
             
             Colors_U = C_arr[:, U_in_indices]
             Colors_O = C_arr[:, Over_indices]
             
             Phi_vals = Phi[Colors_U, Colors_O]
             Weighted = Phi_vals * Signs
             Total = np.sum(Weighted, axis=1)
             Raw_Vec = Total % group_size
             
             raw_weights = Raw_Vec.tolist()
             for w in raw_weights:
                 weight_counts[w] = weight_counts.get(w, 0) + 1
        
        polynomial_terms = []
        for weight in sorted(weight_counts.keys()):
            count = weight_counts[weight]
            if weight == 0:
                polynomial_terms.append(str(count))
            elif weight == 1:
                if count == 1:
                    polynomial_terms.append('t')
                else:
                    polynomial_terms.append(f'{count}t')
            else:
                if count == 1:
                    polynomial_terms.append(f't^{weight}')
                else:
                    polynomial_terms.append(f'{count}t^{weight}')
        
        polynomial = ' + '.join(polynomial_terms) if polynomial_terms else '0'
        is_trivial = len(weight_counts) <= 1
        
        results.append({
            'weights': weight_counts,
            'raw_weights': raw_weights,
            'polynomial': polynomial,
            'is_trivial': is_trivial,
            'total_colorings': num_colorings,
            'cocycle_index': idx
        })
    
    return results

# endregion
