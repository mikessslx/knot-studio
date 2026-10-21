import math

class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def __repr__(self):
        return f"Point({self.x}, {self.y})"

    def dist(self, other):
        return math.sqrt((self.x - other.x)**2 + (self.y - other.y)**2)

def segment_intersection(p1, p2, p3, p4):
    """
    Return intersection point of segments p1p2 and p3p4 or None.
    """
    x1, y1 = p1.x, p1.y
    x2, y2 = p2.x, p2.y
    x3, y3 = p3.x, p3.y
    x4, y4 = p4.x, p4.y

    denom = (y4 - y3) * (x2 - x1) - (x4 - x3) * (y2 - y1)
    if denom == 0:
        return None  # Parallel segments

    ua = ((x4 - x3) * (y1 - y3) - (y4 - y3) * (x1 - x3)) / denom
    ub = ((x2 - x1) * (y1 - y3) - (y2 - y1) * (x1 - x3)) / denom

    if 0 <= ua <= 1 and 0 <= ub <= 1:
        x = x1 + ua * (x2 - x1)
        y = y1 + ua * (y2 - y1)
        return Point(x, y)
    return None

def estimate_tangent(strokes, s_idx, p_idx, t):
    """
    Estimate a unit tangent vector at a stroke point.
    """
    pts = strokes[s_idx]
    # Use adjacent points for a stable tangent
    i = int(p_idx)
    n = len(pts)
    if n < 2:
        return (0.0, 0.0)

    # Use neighboring indices for a finite difference
    prev_idx = max(0, i - 1)
    next_idx = min(n - 1, i + 1)

    p_prev = pts[prev_idx]
    p_next = pts[next_idx]

    tx = p_next.x - p_prev.x
    ty = p_next.y - p_prev.y
    norm = (tx * tx + ty * ty) ** 0.5
    if norm == 0:
        return (0.0, 0.0)
    return (tx / norm, ty / norm)

def get_path_distance(stroke, i, j):
    """
    Return cumulative distance along the stroke between indices i and j.
    """
    if i > j:
        i, j = j, i
    dist = 0
    for k in range(i, j):
        dist += stroke[k].dist(stroke[k+1])
    return dist

def find_intersections(strokes):
    """
    Return all self-intersections and inter-stroke intersections.
    """
    intersections = []
    
    # Build segment list
    segments = []
    for s_i, stroke in enumerate(strokes):
        for p_i in range(len(stroke) - 1):
            segments.append({
                's_idx': s_i,
                'p_idx': p_i,
                'p1': stroke[p_i],
                'p2': stroke[p_i+1]
            })

    intersection_count = 0
    
    # Collect raw intersection candidates
    candidates = []

    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            seg1 = segments[i]
            seg2 = segments[j]
            
            # 1. Self-intersection filters
            if seg1['s_idx'] == seg2['s_idx']:
                idx_diff = abs(seg1['p_idx'] - seg2['p_idx'])
                
                # Skip near-adjacent segments
                if idx_diff <= 5:
                    continue
                
                # Skip wrap-around neighbors on closed strokes
                stroke = strokes[seg1['s_idx']]
                stroke_len = len(stroke)
                if stroke[0].dist(stroke[-1]) < 20:
                    if idx_diff >= stroke_len - 5:
                        continue
                
                # Skip short loops that look like corners
                path_dist = get_path_distance(stroke, seg1['p_idx'], seg2['p_idx'])
                if path_dist < 30:
                    continue
                
                # Check the alternate loop length on closed strokes
                if stroke[0].dist(stroke[-1]) < 20:
                    total_len = get_path_distance(stroke, 0, stroke_len - 1)
                    if (total_len - path_dist) < 30:
                        continue

            pt = segment_intersection(seg1['p1'], seg1['p2'], seg2['p1'], seg2['p2'])
            if pt:
                # Skip intersections near stroke start on self crossings
                if seg1['s_idx'] == seg2['s_idx']:
                    start_pt = strokes[seg1['s_idx']][0]
                    if pt.dist(start_pt) < 20: 
                        continue

                # Compute segment parameters
                dx1 = seg1['p2'].x - seg1['p1'].x
                dy1 = seg1['p2'].y - seg1['p1'].y
                if abs(dx1) > abs(dy1):
                    t1 = (pt.x - seg1['p1'].x) / dx1
                else:
                    t1 = (pt.y - seg1['p1'].y) / dy1
                
                dx2 = seg2['p2'].x - seg2['p1'].x
                dy2 = seg2['p2'].y - seg2['p1'].y
                if abs(dx2) > abs(dy2):
                    t2 = (pt.x - seg2['p1'].x) / dx2
                else:
                    t2 = (pt.y - seg2['p1'].y) / dy2

                candidates.append({
                    'pt': pt,
                    'seg1': seg1,
                    'seg2': seg2,
                    't1': t1,
                    't2': t2
                })

    # 2. Debounce nearby intersections
    filtered_candidates = []
    
    used_indices = set()
    
    for k, cand in enumerate(candidates):
        if k in used_indices:
            continue
            
        # Start a new cluster
        cluster = [cand]
        used_indices.add(k)
        
        # Add nearby candidates from the same stroke pair
        for m in range(k + 1, len(candidates)):
            if m in used_indices:
                continue
            
            other = candidates[m]
            if cand['pt'].dist(other['pt']) < 15:
                s1_a = cand['seg1']['s_idx']
                s2_a = cand['seg2']['s_idx']
                s1_b = other['seg1']['s_idx']
                s2_b = other['seg2']['s_idx']
                
                if {s1_a, s2_a} == {s1_b, s2_b}:
                    cluster.append(other)
                    used_indices.add(m)
        
        # Collapse cluster to an average point
        avg_x = sum(c['pt'].x for c in cluster) / len(cluster)
        avg_y = sum(c['pt'].y for c in cluster) / len(cluster)
        avg_pt = Point(avg_x, avg_y)

        best_cand = cluster[0]
        
        intersections.append({
            'id': intersection_count,
            'pt': avg_pt,
            's_idx': best_cand['seg1']['s_idx'],
            'p_idx': best_cand['seg1']['p_idx'],
            't': best_cand['t1'],
            'other_s_idx': best_cand['seg2']['s_idx']
        })
        intersections.append({
            'id': intersection_count,
            'pt': avg_pt,
            's_idx': best_cand['seg2']['s_idx'],
            'p_idx': best_cand['seg2']['p_idx'],
            't': best_cand['t2'],
            'other_s_idx': best_cand['seg1']['s_idx']
        })
        intersection_count += 1

    return intersections, intersection_count
