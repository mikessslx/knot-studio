"""
Knot identification engine.

Computes the coloring signature of a knot diagram and matches it against
the precomputed database of prime and composite knot signatures.

All quandles used are valid (satisfy quandle axioms), ensuring coloring
counts are true knot invariants independent of diagram representation.
"""

import math

try:
    from .signature_db import (
        QUANDLES, QUANDLE_SIZES, QUANDLE_NAMES,
        PRIME_SIGNATURES, COMPOSITE_SIGNATURES,
        N_SNF_QUANDLES, ZN_PARAMS,
    )
    from .solver import compute_quandle_colorings, dfs_solver
except ImportError:
    from signature_db import (
        QUANDLES, QUANDLE_SIZES, QUANDLE_NAMES,
        PRIME_SIGNATURES, COMPOSITE_SIGNATURES,
        N_SNF_QUANDLES, ZN_PARAMS,
    )
    from solver import compute_quandle_colorings, dfs_solver


def _snf_count(matrix, n):
    """Count solutions to Ax=0 mod n via Smith Normal Form over Z."""
    if not matrix:
        return n
    A = [row[:] for row in matrix]
    nrows, ncols = len(A), len(A[0])
    for pivot in range(min(nrows, ncols)):
        for _ in range(500):
            min_val, min_pos = None, None
            for r in range(pivot, nrows):
                for c in range(pivot, ncols):
                    if A[r][c] != 0 and (min_val is None or abs(A[r][c]) < abs(min_val)):
                        min_val = A[r][c]
                        min_pos = (r, c)
            if min_pos is None:
                break
            r, c = min_pos
            if r != pivot:
                A[pivot], A[r] = A[r], A[pivot]
            if c != pivot:
                for row in A:
                    row[pivot], row[c] = row[c], row[pivot]
            if A[pivot][pivot] < 0:
                A[pivot] = [-x for x in A[pivot]]
            d = A[pivot][pivot]
            changed = False
            for r in range(nrows):
                if r != pivot and A[r][pivot] != 0:
                    q = A[r][pivot] // d
                    for k in range(ncols):
                        A[r][k] -= q * A[pivot][k]
                    if A[r][pivot] != 0:
                        changed = True
            for c in range(ncols):
                if c != pivot and A[pivot][c] != 0:
                    q = A[pivot][c] // d
                    for r in range(nrows):
                        A[r][c] -= q * A[r][pivot]
                    if A[pivot][c] != 0:
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


def _simplify_r1(knot):
    """
    Remove nugatory crossings (Reidemeister I moves).

    A crossing where over == under_in or over == under_out is nugatory.
    Returns a simplified copy of the knot.
    """
    arcs = list(knot["arcs"])
    crossings = [cr.copy() for cr in knot["crossings"]]
    changed = True
    while changed:
        changed = False
        for cr in crossings[:]:
            over = cr["over"]
            u_in = cr["under_in"]
            u_out = cr["under_out"]
            merge_from = merge_to = None
            if over == u_in:
                merge_from, merge_to = u_out, over
            elif over == u_out:
                merge_from, merge_to = u_in, over
            else:
                continue
            crossings.remove(cr)
            if merge_from in arcs:
                arcs.remove(merge_from)
            for other in crossings:
                if other["over"] == merge_from:
                    other["over"] = merge_to
                if other["under_in"] == merge_from:
                    other["under_in"] = merge_to
                if other["under_out"] == merge_from:
                    other["under_out"] = merge_to
            changed = True
            break
    return {"arcs": arcs, "crossings": crossings}


def compute_signature(knot, stop=None):
    """
    Compute the coloring count signature for a knot.

    Uses SNF (fast) for Z_n Alexander quandles and DFS for Z_n[i]/F_q quandles.
    """
    arcs = knot["arcs"]
    crossings = knot["crossings"]
    arc_to_idx = {arc: i for i, arc in enumerate(arcs)}
    n_arcs = len(arcs)
    n_total = len(QUANDLE_SIZES)
    signature = []

    for i in range(n_total):
        if stop:
            stop()
        if i < N_SNF_QUANDLES:
            n, t = ZN_PARAMS[i]
            if not crossings:
                signature.append(n)
                continue
            one_minus_t = 1 - t
            matrix = []
            for cr in crossings:
                row = [0] * n_arcs
                u_in = arc_to_idx[cr["under_in"]]
                u_out = arc_to_idx[cr["under_out"]]
                over = arc_to_idx[cr["over"]]
                if cr["type"] == "positive":
                    row[u_in] += t
                    row[over] += one_minus_t
                    row[u_out] -= 1
                else:
                    row[u_out] += t
                    row[over] += one_minus_t
                    row[u_in] -= 1
                matrix.append(row)
            signature.append(_snf_count(matrix, n))
        else:
            if not crossings:
                signature.append(QUANDLE_SIZES[i])
                continue
            fixed_color_count = compute_quandle_colorings(
                QUANDLES[i], knot, solver=dfs_solver, stop=stop, turbo=True
            )
            signature.append(fixed_color_count * QUANDLE_SIZES[i])
    return tuple(signature)


def is_unknot_signature(signature):
    """The unknot has Col_X(unknot) = |X| for all quandles X."""
    return all(signature[i] == QUANDLE_SIZES[i] for i in range(len(QUANDLE_SIZES)))


def identify_knot(knot, stop=None):
    """
    Identify a knot by computing its coloring signature and matching
    against the database.

    Returns a dict with:
      - result: human-readable identification string
      - type: "unknot" | "prime" | "composite" | "ambiguous" | "unknown"
      - signature: the computed signature
      - details: additional info (factors, confidence, candidates)
    """
    simplified = _simplify_r1(knot)
    had_nugatory = len(simplified["crossings"]) < len(knot.get("crossings", []))
    signature = compute_signature(simplified, stop=stop)

    if is_unknot_signature(signature):
        result = {
            "result": "Unknot (0_1)",
            "type": "unknot",
            "signature": list(signature),
            "details": {"confidence": "exact"},
        }
        if had_nugatory:
            result["details"]["nugatory_removed"] = (
                len(knot["crossings"]) - len(simplified["crossings"])
            )
        return result

    prime_matches = [
        name for name, sig in PRIME_SIGNATURES.items() if sig == signature
    ]
    composite_matches = [
        name for name, sig in COMPOSITE_SIGNATURES.items() if sig == signature
    ]

    if prime_matches and composite_matches:
        candidates = prime_matches + composite_matches
        return {
            "result": " or ".join(candidates),
            "type": "ambiguous",
            "signature": list(signature),
            "details": {
                "confidence": "ambiguous",
                "candidates": candidates,
                "prime_candidates": prime_matches,
                "composite_candidates": composite_matches,
            },
        }

    if len(prime_matches) == 1:
        return {
            "result": prime_matches[0],
            "type": "prime",
            "signature": list(signature),
            "details": {"confidence": "exact"},
        }
    if len(prime_matches) > 1:
        return {
            "result": " or ".join(prime_matches),
            "type": "prime",
            "signature": list(signature),
            "details": {
                "confidence": "ambiguous",
                "candidates": prime_matches,
            },
        }

    if len(composite_matches) == 1:
        factors = composite_matches[0].split(" # ")
        return {
            "result": composite_matches[0],
            "type": "composite",
            "signature": list(signature),
            "details": {"confidence": "exact", "factors": factors},
        }
    if len(composite_matches) > 1:
        return {
            "result": composite_matches[0],
            "type": "composite",
            "signature": list(signature),
            "details": {
                "confidence": "ambiguous",
                "candidates": composite_matches,
                "factors": composite_matches[0].split(" # "),
            },
        }

    factorizations = _try_factorize(signature)
    if factorizations:
        best = factorizations[0]
        return {
            "result": " # ".join(best),
            "type": "composite",
            "signature": list(signature),
            "details": {
                "confidence": "exact" if len(factorizations) == 1 else "ambiguous",
                "factors": best,
                "candidates": [" # ".join(f) for f in factorizations],
            },
        }

    return {
        "result": "Unknown",
        "type": "unknown",
        "signature": list(signature),
        "details": {
            "confidence": "none",
            "message": "Currently only knots with at most 9 crossings are supported.",
        },
    }


def _try_factorize(signature):
    """Try to express signature as a product of known prime knot signatures."""
    results = []
    sorted_primes = sorted(
        PRIME_SIGNATURES.keys(),
        key=lambda x: (int(x.split("_")[0]), int(x.split("_")[1])),
    )

    def divide_signature(current_signature, prime_signature):
        quotient = []
        for j in range(len(QUANDLE_SIZES)):
            if prime_signature[j] == 0:
                return None
            q = current_signature[j] * QUANDLE_SIZES[j]
            if q % prime_signature[j] != 0:
                return None
            quotient.append(q // prime_signature[j])
        return tuple(quotient)

    def search(current_signature, start_index, factors, crossing_sum):
        for index in range(start_index, len(sorted_primes)):
            knot_name = sorted_primes[index]
            next_crossing_sum = crossing_sum + int(knot_name.split("_")[0])
            if next_crossing_sum > 9:
                break

            quotient = divide_signature(current_signature, PRIME_SIGNATURES[knot_name])
            if quotient is None:
                continue

            next_factors = factors + [knot_name]
            if quotient in PRIME_SIGNATURES.values():
                for candidate in sorted_primes[index:]:
                    if PRIME_SIGNATURES[candidate] != quotient:
                        continue
                    if next_crossing_sum + int(candidate.split("_")[0]) <= 9:
                        results.append(next_factors + [candidate])

            search(quotient, index, next_factors, next_crossing_sum)

    search(signature, 0, [], 0)

    return results
