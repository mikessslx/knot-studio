from geometry import Point, find_intersections
from graph import build_graph_edges, determine_crossing_states, traverse_arcs, construct_geometry

def recognize_knot(strokes_data, chooser=None):
    """
    Convert raw stroke data into a knot dictionary.
    """
    # 1. Parse strokes into Point lists
    strokes = []
    for s in strokes_data:
        points = [Point(p['x'], p['y']) for p in s]
        if len(points) > 1:
            strokes.append(points)

    if not strokes:
        return {"arcs": [], "crossings": []}

    # 2. Find intersections
    intersections, intersection_count = find_intersections(strokes)

    # 3. Build graph edges
    graph_edges = build_graph_edges(strokes, intersections)

    # 4. Determine crossing states
    crossing_states = determine_crossing_states(intersections, intersection_count, strokes, chooser)

    # 5. Traverse arcs
    final_crossings = traverse_arcs(graph_edges, crossing_states, intersection_count)

    # 6. Construct geometry
    result = construct_geometry(graph_edges, strokes, intersections, final_crossings)
    
    return result


def detect_intersections(strokes_data):
    """
    Lightweight intersection detection for front-end preview.
    """
    # Parse strokes into Point lists
    strokes = []
    for s in strokes_data:
        points = [Point(p['x'], p['y']) for p in s]
        if len(points) > 1:
            strokes.append(points)

    if not strokes:
        return []

    intersections, _ = find_intersections(strokes)

    # Group pairs into preview-friendly objects
    intersections_by_id = {}
    for inter in intersections:
        iid = inter['id']
        if iid not in intersections_by_id:
            intersections_by_id[iid] = []
        intersections_by_id[iid].append(inter)

    preview = []
    for iid, inters in intersections_by_id.items():
        if len(inters) < 2:
            continue
        i1 = inters[0]
        i2 = inters[1]
        preview.append({
            'id': iid,
            'x': i1['pt'].x,
            'y': i1['pt'].y,
            'A': {
                's_idx': i1['s_idx'],
                'p_idx': i1['p_idx'],
                't': i1['t']
            },
            'B': {
                's_idx': i2['s_idx'],
                'p_idx': i2['p_idx'],
                't': i2['t']
            }
        })

    return preview
