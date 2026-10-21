from flask import Flask, render_template, request, jsonify
from werkzeug.exceptions import RequestEntityTooLarge
import time
import sys
import os
import json
import math

# Add logic directory to import path
sys.path.append(os.path.join(os.path.dirname(__file__), 'logic'))

# Increase recursion limit for deep knot recursion
sys.setrecursionlimit(5000)

STOP_CALCULATION = False
DEMO_MODE = os.getenv('PUBLIC_DEMO_MODE', '1').lower() in ('1', 'true', 'yes', 'on')
DEMO_MESSAGE = (
    "This computation is disabled in the public demo because it can be CPU intensive. "
    "Run the project locally or use the private research version to enable it."
)
REPO_URL = os.getenv('PROJECT_REPO_URL', 'https://github.com')

def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default

MAX_REQUEST_BYTES = _env_int('MAX_REQUEST_BYTES', 512 * 1024)
MAX_STROKES = _env_int('MAX_STROKES', 8)
MAX_STROKE_POINTS = _env_int('MAX_STROKE_POINTS', 800)
MAX_TOTAL_STROKE_POINTS = _env_int('MAX_TOTAL_STROKE_POINTS', 1200)
MAX_RECOGNIZE_CROSSINGS = _env_int('MAX_RECOGNIZE_CROSSINGS', 80)
MAX_IDENTIFY_CROSSINGS = _env_int('MAX_IDENTIFY_CROSSINGS', 9)
MAX_IDENTIFY_ARCS = _env_int('MAX_IDENTIFY_ARCS', 64)
MAX_COORDINATE_ABS = _env_int('MAX_COORDINATE_ABS', 10000)
IDENTIFY_UNSUPPORTED_MESSAGE = (
    f"Currently only knots with at most {MAX_IDENTIFY_CROSSINGS} crossings are supported."
)

app = Flask(__name__)
if DEMO_MODE:
    app.config['MAX_CONTENT_LENGTH'] = MAX_REQUEST_BYTES

@app.route('/')
def index():
    return render_template('index.html', demo_mode=DEMO_MODE, repo_url=REPO_URL)

@app.errorhandler(RequestEntityTooLarge)
def request_too_large(_error):
    return jsonify({
        "status": "error",
        "message": f"Request body is too large. Maximum allowed size is {MAX_REQUEST_BYTES} bytes."
    }), 413

@app.before_request
def enforce_demo_request_size():
    if (
        DEMO_MODE
        and request.content_length is not None
        and request.content_length > MAX_REQUEST_BYTES
    ):
        raise RequestEntityTooLarge()

def demo_disabled_response():
    return jsonify({
        "status": "error",
        "message": DEMO_MESSAGE,
        "repo_url": REPO_URL,
        "demo_mode": True
    }), 403

class InputValidationError(ValueError):
    pass

def validation_error_response(error):
    return jsonify({"status": "error", "message": str(error)}), 400

def get_json_body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise InputValidationError("Expected a JSON object.")
    return data

def _is_number(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )

def validate_strokes(strokes):
    if not isinstance(strokes, list):
        raise InputValidationError("'strokes' must be a list.")
    if DEMO_MODE and len(strokes) > MAX_STROKES:
        raise InputValidationError(f"Too many strokes. Maximum is {MAX_STROKES}.")

    total_points = 0
    for stroke_index, stroke in enumerate(strokes):
        if not isinstance(stroke, list):
            raise InputValidationError(f"Stroke {stroke_index} must be a list of points.")
        if DEMO_MODE and len(stroke) > MAX_STROKE_POINTS:
            raise InputValidationError(
                f"Stroke {stroke_index} has too many points. Maximum per stroke is {MAX_STROKE_POINTS}."
            )

        total_points += len(stroke)
        if DEMO_MODE and total_points > MAX_TOTAL_STROKE_POINTS:
            raise InputValidationError(f"Too many total stroke points. Maximum is {MAX_TOTAL_STROKE_POINTS}.")

        for point_index, point in enumerate(stroke):
            if not isinstance(point, dict):
                raise InputValidationError(f"Point {point_index} in stroke {stroke_index} must be an object.")
            x = point.get('x')
            y = point.get('y')
            if not _is_number(x) or not _is_number(y):
                raise InputValidationError(f"Point {point_index} in stroke {stroke_index} must have numeric x/y.")
            if DEMO_MODE and (abs(x) > MAX_COORDINATE_ABS or abs(y) > MAX_COORDINATE_ABS):
                raise InputValidationError(
                    f"Point {point_index} in stroke {stroke_index} is outside the allowed coordinate range."
                )

def validate_crossing_choices(crossing_choices):
    if crossing_choices is None:
        return None
    if not isinstance(crossing_choices, dict):
        raise InputValidationError("'crossing_choices' must be an object.")
    if DEMO_MODE and len(crossing_choices) > MAX_RECOGNIZE_CROSSINGS:
        raise InputValidationError(
            f"Too many crossing choices. Maximum is {MAX_RECOGNIZE_CROSSINGS}."
        )
    for key, value in crossing_choices.items():
        if not isinstance(key, str):
            raise InputValidationError("Crossing choice keys must be strings.")
        if DEMO_MODE and len(key) > 20:
            raise InputValidationError("Crossing choice keys must be short strings.")
        if value not in ('A', 'B'):
            raise InputValidationError("Crossing choice values must be 'A' or 'B'.")
    return crossing_choices

def validate_recognized_crossings(knot):
    crossing_count = len(knot.get('crossings', []))
    if DEMO_MODE and crossing_count > MAX_RECOGNIZE_CROSSINGS:
        raise InputValidationError(
            f"Recognized diagram has too many crossings ({crossing_count}). Maximum is {MAX_RECOGNIZE_CROSSINGS}."
        )

def validate_preview_crossings(preview):
    crossing_count = len(preview)
    if DEMO_MODE and crossing_count > MAX_RECOGNIZE_CROSSINGS:
        raise InputValidationError(
            f"Diagram has too many crossings ({crossing_count}). Maximum is {MAX_RECOGNIZE_CROSSINGS}."
        )

def is_single_component_knot(knot):
    arcs = knot.get('arcs', [])
    crossings = knot.get('crossings', [])
    if not arcs:
        return False
    if not crossings:
        return len(arcs) == 1

    adjacency = {arc: set() for arc in arcs}
    for crossing in crossings:
        under_in = crossing['under_in']
        under_out = crossing['under_out']
        if under_in not in adjacency or under_out not in adjacency:
            return False
        adjacency[under_in].add(under_out)
        adjacency[under_out].add(under_in)

    seen = set()
    components = 0
    for arc in arcs:
        if arc in seen:
            continue
        components += 1
        stack = [arc]
        seen.add(arc)
        while stack:
            current = stack.pop()
            for neighbor in adjacency[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)

    return components == 1

def validate_identify_knot(knot):
    if not isinstance(knot, dict):
        raise InputValidationError("'knot' must be an object.")

    arcs = knot.get('arcs')
    crossings = knot.get('crossings')
    if not isinstance(arcs, list) or not isinstance(crossings, list):
        raise InputValidationError("'knot' must include list fields 'arcs' and 'crossings'.")
    if DEMO_MODE and len(arcs) > MAX_IDENTIFY_ARCS:
        raise InputValidationError(f"Knot has too many arcs. Maximum is {MAX_IDENTIFY_ARCS}.")
    if len(crossings) > MAX_IDENTIFY_CROSSINGS:
        raise InputValidationError(IDENTIFY_UNSUPPORTED_MESSAGE)

    arc_ids = set()
    for arc in arcs:
        if isinstance(arc, bool) or not isinstance(arc, (int, str)):
            raise InputValidationError("Knot arcs must be integers or strings.")
        arc_ids.add(arc)

    for index, crossing in enumerate(crossings):
        if not isinstance(crossing, dict):
            raise InputValidationError(f"Crossing {index} must be an object.")
        for field in ('over', 'under_in', 'under_out', 'type'):
            if field not in crossing:
                raise InputValidationError(f"Crossing {index} is missing '{field}'.")
        if crossing['type'] not in ('positive', 'negative'):
            raise InputValidationError(f"Crossing {index} has invalid type.")
        for field in ('over', 'under_in', 'under_out'):
            if crossing[field] not in arc_ids:
                raise InputValidationError(f"Crossing {index} references an unknown arc.")

    if not is_single_component_knot(knot):
        raise InputValidationError(IDENTIFY_UNSUPPORTED_MESSAGE)

@app.route('/api/stop', methods=['POST'])
def stop_calculation():
    global STOP_CALCULATION
    STOP_CALCULATION = True
    return jsonify({"status": "success", "message": "Stop signal received."})

def stop():
    if STOP_CALCULATION:
        raise Exception("Calculation stopped by user request.")

from logic.recognition import recognize_knot, detect_intersections

@app.route('/api/recognize', methods=['POST'])
def recognize():
    try:
        data = get_json_body()
        strokes = data.get('strokes', [])
        validate_strokes(strokes)
        # crossing_choices maps intersection id to "A" or "B" for over-strand selection
        crossing_choices = validate_crossing_choices(data.get('crossing_choices'))
    except InputValidationError as e:
        return validation_error_response(e)

    try:
        if crossing_choices:
            # Build chooser callback for recognize_knot
            def make_chooser(choices_map):
                def chooser(i1, i2, iid):
                    # choices_map stores ids as strings
                    v = choices_map.get(str(iid))
                    if v == 'A':
                        # "A" means i1 is over i2
                        return (i2, i1)
                    if v == 'B':
                        # "B" means i2 is over i1
                        return (i1, i2)
                    # None lets recognize_knot decide
                    return None
                return chooser

            chooser = make_chooser(crossing_choices)
            knot = recognize_knot(strokes, chooser=chooser)
        else:
            knot = recognize_knot(strokes)

        validate_recognized_crossings(knot)

        return jsonify({
            "status": "success",
            "knot": knot
        })
    except InputValidationError as e:
        return validation_error_response(e)
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/recognize_preview', methods=['POST'])
def recognize_preview():
    try:
        data = get_json_body()
        strokes = data.get('strokes', [])
        validate_strokes(strokes)
    except InputValidationError as e:
        return validation_error_response(e)

    try:
        preview = detect_intersections(strokes)
        validate_preview_crossings(preview)
        return jsonify({
            "status": "success",
            "preview": preview
        })
    except InputValidationError as e:
        return validation_error_response(e)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

from logic.solver import (
    compute_quandle_colorings,
    enum_solver,
    dfs_solver,
    algebraic_solver,
    propagation_solver,
    linear_solver,
    snf_solver,
)

@app.route('/api/calculate', methods=['POST'])
def calculate():
    if DEMO_MODE:
        return demo_disabled_response()

    data = request.json
    quandle = data.get('quandle')
    knot = data.get('knot')
    method = data.get('method', 'enum')
    
    global STOP_CALCULATION
    STOP_CALCULATION = False
    
    if method == 'all':
        # Run all solvers and collect timings
        start = time.time()
        res_enum = compute_quandle_colorings(quandle, knot, solver=enum_solver, stop=stop)
        time_enum = time.time() - start
        
        start = time.time()
        res_dfs = compute_quandle_colorings(quandle, knot, solver=dfs_solver, stop=stop)
        time_dfs = time.time() - start

        start = time.time()
        res_alg = compute_quandle_colorings(quandle, knot, solver=algebraic_solver, stop=stop)
        time_alg = time.time() - start

        start = time.time()
        res_prop = compute_quandle_colorings(quandle, knot, solver=propagation_solver, stop=stop)
        time_prop = time.time() - start

        start = time.time()
        res_linear = compute_quandle_colorings(quandle, knot, solver=linear_solver, stop=stop)
        time_linear = time.time() - start

        return jsonify({
            "status": "success",
            "method": "all",
            "results": {
                "enum": {"time": time_enum, "count": len(res_enum)},
                "dfs": {"time": time_dfs, "count": len(res_dfs)},
                "algebra": {"time": time_alg, "count": len(res_alg)},
                "propagation": {"time": time_prop, "count": len(res_prop)},
                "linear": {"time": time_linear, "count": len(res_linear)}
            },
            "colorings": res_dfs  # Use DFS colorings for display
        })
    
    if method == 'dfs':
        solver_func = dfs_solver
    elif method == 'algebra':
        solver_func = algebraic_solver
    elif method == 'propagation':
        solver_func = propagation_solver
    elif method == 'linear':
        solver_func = linear_solver
    else:
        solver_func = enum_solver
    
    try:
        start = time.time()
        colorings = compute_quandle_colorings(quandle, knot, solver=solver_func, stop=stop)
        duration = time.time() - start
        
        return jsonify({
            "status": "success",
            "method": method,
            "time": duration,
            "colorings": colorings
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/list_data_files', methods=['GET'])
def list_data_files():
    try:
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
        files.sort()
        return jsonify({
            "status": "success",
            "files": files
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/turbo_calculate', methods=['POST'])
def turbo_calculate():
    if DEMO_MODE:
        return demo_disabled_response()

    data = request.json
    knot_files = data.get('knot_files', [])
    quandles = data.get('quandles', [])
    method = data.get('method', 'dfs')
    
    global STOP_CALCULATION
    STOP_CALCULATION = False
    
    if method == 'dfs':
        solver_func = dfs_solver
    elif method == 'algebra':
        solver_func = algebraic_solver
    elif method == 'propagation':
        solver_func = propagation_solver
    elif method == 'linear':
        solver_func = linear_solver
    elif method == 'snf':
        solver_func = snf_solver
    else:
        solver_func = enum_solver
    is_turbo = data.get('turbo', False)
    
    try:
        results = {}
        data_dir = os.path.join(os.path.dirname(__file__), 'data')
        
        for knot_file in knot_files:
            file_path = os.path.join(data_dir, knot_file)
            if not os.path.exists(file_path):
                continue
                
            with open(file_path, 'r') as f:
                knot = json.load(f)
            
            results[knot_file] = {}
            matrix_cache = {} if solver_func is snf_solver and is_turbo else None
            
            for idx, quandle in enumerate(quandles):
                quandle_name = quandle.get('name', f'Quandle_{idx}')
                start = time.time()

                solver_kwargs = {}
                if matrix_cache is not None:
                    solver_kwargs['matrix_cache'] = matrix_cache

                colorings = compute_quandle_colorings(
                    quandle,
                    knot,
                    solver=solver_func,
                    turbo=is_turbo,
                    stop=stop,
                    **solver_kwargs,
                )
                duration = time.time() - start
                
                if isinstance(colorings, int):
                    count = colorings
                else:
                    count = len(colorings)

                if is_turbo:
                    count *= len(quandle['elements'])

                results[knot_file][quandle_name] = {
                    'count': count,
                    'time': duration
                }
        
        return jsonify({
            "status": "success",
            "results": results
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

from logic.turbo import turbo_ipynb, turbo_gap
from logic.cocycle import compute_cocycle, enum_cocycle_solver, linear_cocycle_solver
from logic.cocycle import compute_cocycle_invariant, compute_all_cocycle_invariant
from logic.identifier import identify_knot

@app.route('/api/identify', methods=['POST'])
def identify():
    try:
        data = get_json_body()
        knot = data.get('knot')
        if not knot:
            return jsonify({"status": "error", "message": "Missing required field: knot."}), 400
        validate_identify_knot(knot)
    except InputValidationError as e:
        return validation_error_response(e)

    global STOP_CALCULATION
    STOP_CALCULATION = False

    try:
        result = identify_knot(knot, stop=stop)
        return jsonify({"status": "success", **result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/cocycle', methods=['POST'])
def cocycle():
    if DEMO_MODE:
        return demo_disabled_response()

    data = request.json
    op_table = data.get('op_table')
    group_size = data.get('group_size', 2)
    method = data.get('method', 'linear')
    just_reps = data.get('just_reps', True)
    
    global STOP_CALCULATION
    STOP_CALCULATION = False
    
    if not op_table:
        return jsonify({
            "status": "error",
            "message": "Missing required field: op_table."
        }), 400
    
    # Select cocycle solver
    if method == 'enum':
        solver_func = enum_cocycle_solver
    else:
        solver_func = linear_cocycle_solver
    
    try:
        start = time.time()
        cocycles = compute_cocycle(op_table, group_size, solver=solver_func, stop=stop, just_reps=just_reps)
        duration = time.time() - start
        
        return jsonify({
            "status": "success",
            "method": method,
            "time": duration,
            "count": len(cocycles),
            "cocycles": cocycles
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/cocycle_invariant', methods=['POST'])
def cocycle_invariant():
    if DEMO_MODE:
        return demo_disabled_response()

    data = request.json
    knot = data.get('knot')
    quandle = data.get('quandle')
    cocycle = data.get('cocycle')
    group_size = data.get('group_size', 3)
    compute_all = data.get('compute_all', False)
    cocycles_input = data.get('cocycles')
    colorings_input = data.get('colorings')

    colorings = None
    if colorings_input:
        try:
            colorings = []
            for c in colorings_input:
                new_c = {}
                for k, v in c.items():
                    new_c[int(k)] = v
                colorings.append(new_c)
        except Exception:
            colorings = None

    global STOP_CALCULATION
    STOP_CALCULATION = False
    
    if not knot:
        return jsonify({"status": "error", "message": "Missing required field: knot."}), 400
    if not quandle:
        return jsonify({"status": "error", "message": "Missing required field: quandle."}), 400
    
    try:
        start = time.time()
        
        if compute_all:
            # Compute invariants for all cocycles
            results = compute_all_cocycle_invariant(
                knot, quandle, group_size, 
                cocycles=cocycles_input, 
                colorings=colorings,
                stop=stop
            )
            duration = time.time() - start
            
            # Filter non-trivial invariants
            non_trivial = [r for r in results if not r['is_trivial']]
            
            return jsonify({
                "status": "success",
                "time": duration,
                "total_cocycles": len(results),
                "non_trivial_count": len(non_trivial),
                "results": results,
                "non_trivial": non_trivial
            })
        else:
            # Compute for a single cocycle
            if not cocycle:
                n = len(quandle['elements'])
                cocycle = [[0] * n for _ in range(n)]
            
            result = compute_cocycle_invariant(
                knot, quandle, cocycle, group_size,
                colorings=colorings, stop=stop
            )
            duration = time.time() - start
            
            return jsonify({
                "status": "success",
                "time": duration,
                "polynomial": result['polynomial'],
                "weights": result['weights'],
                "is_trivial": result['is_trivial'],
                "total_colorings": result['total_colorings']
            })
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/generate_ipynb', methods=['POST'])
def generate_ipynb():
    data = request.json
    knot_files = data.get('knot_files', [])
    # Expect full quandle objects
    quandles = data.get('quandles', []) 
    method = data.get('method', 'dfs')
    turbo = data.get('turbo', True)

    notebook = turbo_ipynb(knot_files, quandles, method, turbo)
    return jsonify(notebook)

@app.route('/api/generate_gap', methods=['POST'])
def generate_gap():
    data = request.json
    knot_files = data.get('knot_files', [])
    quandles = data.get('quandles', []) 
    turbo = data.get('turbo', True)

    gap = turbo_gap(knot_files, quandles, turbo)
    return jsonify({"script": gap})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
