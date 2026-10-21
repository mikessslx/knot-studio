import random
from geometry import estimate_tangent

def build_graph_edges(strokes, intersections):
    """
    Split strokes into graph edges based on intersections.
    """
    split_points_by_stroke = {i: [] for i in range(len(strokes))}
    
    for inter in intersections:
        split_points_by_stroke[inter['s_idx']].append(inter)

    # Sort split points by position along each stroke
    for s_idx in split_points_by_stroke:
        split_points_by_stroke[s_idx].sort(key=lambda x: x['p_idx'] + x['t'])

    graph_edges = []  # Edge records for each stroke segment
    
    for s_idx, stroke in enumerate(strokes):
        splits = split_points_by_stroke[s_idx]
        
        prev_node = f"START_{s_idx}"
        
        for i, split in enumerate(splits):
            curr_node = f"I_{split['id']}"
            
            graph_edges.append({
                'u': prev_node,
                'v': curr_node,
                's_idx': s_idx,
                'type': 'segment',
                'start_p_idx': 0 if i == 0 else splits[i-1]['p_idx'],
                'end_p_idx': split['p_idx'],
                'start_t': 0 if i == 0 else splits[i-1]['t'],
                'end_t': split['t']
            })
            
            prev_node = curr_node
            
        end_node = f"END_{s_idx}"
        graph_edges.append({
            'u': prev_node,
            'v': end_node,
            's_idx': s_idx,
            'type': 'segment',
            'start_p_idx': splits[-1]['p_idx'] if splits else 0,
            'end_p_idx': len(stroke),
            'start_t': splits[-1]['t'] if splits else 0,
            'end_t': 0
        })
        
    return graph_edges

def determine_crossing_states(intersections, intersection_count, strokes, chooser=None):
    """
    Determine over and under state for each intersection.
    """
    crossing_states = {}  # id -> over strand and sign
    
    # Group intersections by id
    intersections_by_id = {}
    for inter in intersections:
        iid = inter['id']
        if iid not in intersections_by_id:
            intersections_by_id[iid] = []
        intersections_by_id[iid].append(inter)
        
    for iid, inters in intersections_by_id.items():
        if len(inters) < 2: continue
        
        i1 = inters[0]
        i2 = inters[1]

        # Choose under and over strands
        if callable(chooser):
            chosen = chooser(i1, i2, iid)
            if (isinstance(chosen, (list, tuple)) and len(chosen) == 2
                    and (chosen[0] in (i1, i2)) and (chosen[1] in (i1, i2))):
                under, over = chosen[0], chosen[1]
            else:
                if random.choice([True, False]):
                    under = i1
                    over = i2
                else:
                    under = i2
                    over = i1
        else:
            if random.choice([True, False]):
                under = i1
                over = i2
            else:
                under = i2
                over = i1
        
        t_over = estimate_tangent(strokes, over['s_idx'], over['p_idx'], over['t'])
        t_under = estimate_tangent(strokes, under['s_idx'], under['p_idx'], under['t'])

        # Use 2D cross product to set the sign
        z = t_over[0] * t_under[1] - t_over[1] * t_under[0]
        ctype = 'positive' if z > 0 else 'negative'

        crossing_states[iid] = {
            'over_s_idx': over['s_idx'],
            'over_p_idx': over['p_idx'],
            'type': ctype
        }
        
    return crossing_states

def traverse_arcs(graph_edges, crossing_states, intersection_count):
    """
    Traverse the graph to identify arcs.
    """
    # 1. Assign temporary ids to segments
    for i, edge in enumerate(graph_edges):
        edge['temp_id'] = i
        
    # 2. Union-find for arc merging
    parent = list(range(len(graph_edges)))
    def find(i):
        if parent[i] == i: return i
        parent[i] = find(parent[i])
        return parent[i]
    def union(i, j):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    # Group edges by node
    edges_at_node = {}
    for edge in graph_edges:
        u = edge['u']
        v = edge['v']
        if u not in edges_at_node: edges_at_node[u] = []
        if v not in edges_at_node: edges_at_node[v] = []
        edges_at_node[u].append(edge)
        edges_at_node[v].append(edge)

    for s_idx in range(max((e['s_idx'] for e in graph_edges), default=-1) + 1):
        start_node = f"START_{s_idx}"
        end_node = f"END_{s_idx}"
        start_edges = [e for e in graph_edges if e['u'] == start_node]
        end_edges = [e for e in graph_edges if e['v'] == end_node]
        if start_edges and end_edges:
            union(start_edges[0]['temp_id'], end_edges[0]['temp_id'])

    for node, edges in edges_at_node.items():
        if node.startswith("START") or node.startswith("END"):
            pass
        elif node.startswith("I_"):
            iid = int(node.split("_")[1])
            if iid not in crossing_states: continue
            state = crossing_states[iid]
            
            ins = [e for e in edges if e['v'] == node]
            outs = [e for e in edges if e['u'] == node]
            
            pairs = []
            for i_edge in ins:
                candidates = [o for o in outs if o['s_idx'] == i_edge['s_idx']]
                if candidates:
                    best_o = None
                    min_dist = float('inf')
                    for o in candidates:
                        dist = abs(i_edge['end_p_idx'] - o['start_p_idx'])
                        if dist < min_dist:
                            min_dist = dist
                            best_o = o
                    
                    if best_o:
                        pairs.append((i_edge, best_o))
            
            # Merge if this node is on the over strand
            for in_e, out_e in pairs:
                is_over = False
                if in_e['s_idx'] == state['over_s_idx']:
                    if abs(in_e['end_p_idx'] - state['over_p_idx']) < 2:
                        is_over = True
                    
                if is_over:
                    union(in_e['temp_id'], out_e['temp_id'])
                    
    # 3. Assign arc ids
    root_map = {}
    next_arc_id = 0
    
    for i in range(len(graph_edges)):
        r = find(i)
        if r not in root_map:
            root_map[r] = next_arc_id
            next_arc_id += 1
        graph_edges[i]['arc_id'] = root_map[r]
        
    # 4. Build crossings output
    final_crossings = []
    for iid in range(intersection_count):
        if iid not in crossing_states: continue
        state = crossing_states[iid]
        node = f"I_{iid}"
        
        ins = [e for e in graph_edges if e['v'] == node]
        outs = [e for e in graph_edges if e['u'] == node]
        
        over_arc_id = -1
        under_in_id = -1
        under_out_id = -1
        
        for in_e in ins:
            candidates = [o for o in outs if o['s_idx'] == in_e['s_idx']]
            if not candidates: continue
            
            out_e = None
            min_dist = float('inf')
            for o in candidates:
                dist = abs(in_e['end_p_idx'] - o['start_p_idx'])
                if dist < min_dist:
                    min_dist = dist
                    out_e = o
            
            if not out_e: continue

            is_over = False
            if in_e['s_idx'] == state['over_s_idx']:
                if abs(in_e['end_p_idx'] - state['over_p_idx']) < 2:
                    is_over = True
            
            if is_over:
                over_arc_id = in_e['arc_id']
            else:
                under_in_id = in_e['arc_id']
                under_out_id = out_e['arc_id']
                
        final_crossings.append({
            "type": state.get('type', 'positive'),
            "over": over_arc_id,
            "under_in": under_in_id,
            "under_out": under_out_id,
            "id": iid
        })
        
    return final_crossings

def _same_point(p1, p2, eps=1e-6):
    return abs(p1.x - p2.x) <= eps and abs(p1.y - p2.y) <= eps

def _same_dict_point(p1, p2, eps=1e-6):
    return abs(p1['x'] - p2['x']) <= eps and abs(p1['y'] - p2['y']) <= eps

def _edges_connect(edge, candidate, node_map):
    if edge['v'] == candidate['u']:
        return True

    p1 = node_map.get(edge['v'])
    p2 = node_map.get(candidate['u'])
    return p1 is not None and p2 is not None and _same_point(p1, p2)

def _order_edges_into_runs(edges, node_map):
    remaining = list(edges)
    runs = []

    while remaining:
        start = None
        for edge in remaining:
            has_predecessor = any(
                other is not edge and _edges_connect(other, edge, node_map)
                for other in remaining
            )
            if not has_predecessor:
                start = edge
                break

        if start is None:
            start = remaining[0]

        run = [start]
        remaining.remove(start)
        current = start

        while remaining:
            candidates = [
                edge for edge in remaining
                if _edges_connect(current, edge, node_map)
            ]
            if not candidates:
                break

            next_edge = min(
                candidates,
                key=lambda edge: 0 if current['v'] == edge['u'] else 1
            )
            run.append(next_edge)
            remaining.remove(next_edge)
            current = next_edge

        runs.append(run)

    return runs

def construct_geometry(graph_edges, strokes, intersections, final_crossings):
    """
    Construct geometry for each arc.
    """
    arc_paths = {}
    
    # Group edges by arc id
    edges_by_arc = {}
    for edge in graph_edges:
        aid = edge['arc_id']
        if aid not in edges_by_arc: edges_by_arc[aid] = []
        edges_by_arc[aid].append(edge)
        
    # Build node map
    node_map = {}
    for s_i, s in enumerate(strokes):
        node_map[f"START_{s_i}"] = s[0]
        node_map[f"END_{s_i}"] = s[-1]
        
    for inter in intersections:
        node_map[f"I_{inter['id']}"] = inter['pt']
        
    for aid, edges in edges_by_arc.items():
        arc_points = []

        for run in _order_edges_into_runs(edges, node_map):
            for edge in run:
                u, v = edge['u'], edge['v']
                p1 = node_map[u]
                p2 = node_map[v]

                segment_pts = [{'x': p1.x, 'y': p1.y}]

                stroke_pts = strokes[edge['s_idx']]
                idx1 = edge['start_p_idx']
                idx2 = edge['end_p_idx']

                start_k = int(idx1) + 1
                end_k = int(idx2) + 1

                for k in range(start_k, end_k):
                    if k < len(stroke_pts):
                        p = stroke_pts[k]
                        segment_pts.append({'x': p.x, 'y': p.y})

                segment_pts.append({'x': p2.x, 'y': p2.y})

                if arc_points and _same_dict_point(arc_points[-1], segment_pts[0]):
                    arc_points.extend(segment_pts[1:])
                elif arc_points:
                    segment_pts[0]['move'] = True
                    arc_points.extend(segment_pts)
                else:
                    arc_points.extend(segment_pts)
                
        arc_paths[aid] = arc_points

    # Attach crossing coordinates
    for c in final_crossings:
        pt = node_map[f"I_{c['id']}"]
        c['x'] = pt.x
        c['y'] = pt.y

    return {
        "arcs": list(set(e['arc_id'] for e in graph_edges)),
        "crossings": final_crossings,
        "geometry": arc_paths
    }
