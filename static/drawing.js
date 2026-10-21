// Shared label color for crossings
export const CROSSING_LABEL_COLOR = '#e74c3c';

// Label style configuration
const LABEL_FONT = 'bold 12px sans-serif';
const LABEL_PADDING = 4;
const LABEL_MIN_RADIUS = 6;
const LABEL_SHADOW_BLUR = 4;
export const SELECTED_BG = 'rgba(46,204,113,0.9)';
// Offset to avoid arc label overlap
export const OFFSET_X = 6;
export const OFFSET_Y = -6;

export function drawRawStrokes(ctx, strokes) {
    ctx.strokeStyle = '#000';
    ctx.lineWidth = 3;
    strokes.forEach(stroke => {
        if (stroke.length === 0) return;
        ctx.beginPath();
        ctx.moveTo(stroke[0].x, stroke[0].y);
        for (let i = 1; i < stroke.length; i++) {
            ctx.lineTo(stroke[i].x, stroke[i].y);
        }
        ctx.stroke();
    });
}

export function drawRecognizedKnot(ctx, recognizedKnot, currentColoring) {
    if (!recognizedKnot || !recognizedKnot.geometry) return;

    const arcs = recognizedKnot.geometry;
    const crossings = recognizedKnot.crossings;

    // 1. Draw arcs
    for (const [arcId, points] of Object.entries(arcs)) {
        ctx.beginPath();
        if (points.length > 0) {
            ctx.moveTo(points[0].x, points[0].y);
            for (let i = 1; i < points.length; i++) {
                if (points[i].move) {
                    ctx.moveTo(points[i].x, points[i].y);
                } else {
                    ctx.lineTo(points[i].x, points[i].y);
                }
            }
        }

        // Select arc color
        if (currentColoring) {
            const val = currentColoring[arcId];
            ctx.strokeStyle = getColorForElement(val);
            ctx.lineWidth = 5;
        } else {
            ctx.strokeStyle = '#000';
            ctx.lineWidth = 3;
        }
        ctx.stroke();

        // Draw arc id label at midpoint
        const labelPoints = points.filter(point => !point.move);
        if (labelPoints.length > 0) {
            const mid = labelPoints[Math.floor(labelPoints.length / 2)];
            // Offset arc label
            const arcLabelX = mid.x + OFFSET_X;
            const arcLabelY = mid.y + OFFSET_Y;
            renderLabels(ctx, [{ x: arcLabelX, y: arcLabelY, text: String(arcId), textColor: '#000' }]);
        }
    }

    // 2. Draw crossings with over/under effect
    crossings.forEach(c => {
        const overArcId = c.over;
        const pt = { x: c.x, y: c.y };

        // Redraw over strand
        const pts = arcs[overArcId];
        if (pts) {
            const color = currentColoring ? getColorForElement(currentColoring[overArcId]) : '#000';
            drawOverStrand(ctx, pts, pt, color);
        }

        // Draw crossing label with frosted background
        const finalLabelX = pt.x + OFFSET_X;
        const finalLabelY = pt.y + OFFSET_Y;
        renderLabels(ctx, [{ x: finalLabelX, y: finalLabelY, text: String(c.id), textColor: CROSSING_LABEL_COLOR, bgColor: SELECTED_BG }]);
    });
}

export function drawOverStrand(ctx, pts, centerPt, color, priorityIdx = -1) {
    // 1. Clear underpass gap
    ctx.save();
    ctx.beginPath();
    ctx.arc(centerPt.x, centerPt.y, 8, 0, 2 * Math.PI);
    ctx.fillStyle = '#fff';
    ctx.fill();
    ctx.restore();

    // 2. Find closest point index
    let closestIdx = -1;

    if (priorityIdx !== -1 && priorityIdx !== null && typeof priorityIdx !== 'undefined') {
        // Use provided index when available
        closestIdx = Math.round(priorityIdx);
        // Clamp to valid range
        if (closestIdx < 0) closestIdx = 0;
        if (closestIdx >= pts.length) closestIdx = pts.length - 1;
    } else {
        // Fallback to nearest point
        let minD = Infinity;
        for (let i = 0; i < pts.length; i++) {
            const d = Math.hypot(pts[i].x - centerPt.x, pts[i].y - centerPt.y);
            if (d < minD) {
                minD = d;
                closestIdx = i;
            }
        }
    }

    if (closestIdx !== -1) {
        // Draw short segment around the crossing
        ctx.beginPath();
        const start = Math.max(0, closestIdx - 2);
        const end = Math.min(pts.length - 1, closestIdx + 2);

        ctx.moveTo(pts[start].x, pts[start].y);
        for (let i = start + 1; i <= end; i++) {
            ctx.lineTo(pts[i].x, pts[i].y);
        }

        ctx.strokeStyle = color;
        ctx.lineWidth = 5;
        ctx.stroke();
    }
}

export function getColorForElement(element) {
    // Map element index to a color
    const colors = [
        '#e74c3c',
        '#3498db',
        '#2ecc71',
        '#f1c40f',
        '#9b59b6',
        '#e67e22',
    ];
    return colors[element % colors.length];
}

// Draw frosted label at (x, y)
export function drawFrostedLabel(ctx, x, y, text, opts = {}) {
    const font = opts.font || LABEL_FONT;
    const padding = (typeof opts.padding === 'number') ? opts.padding : LABEL_PADDING;
    const minRadius = (typeof opts.minRadius === 'number') ? opts.minRadius : LABEL_MIN_RADIUS;
    const bgColor = opts.bgColor || 'rgba(255,255,255,0.85)';
    const shadowColor = opts.shadowColor || 'rgba(0,0,0,0.25)';
    const textColor = opts.textColor || CROSSING_LABEL_COLOR === undefined ? '#000' : '#000';

    ctx.save();
    ctx.font = font;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    const metrics = ctx.measureText(text);
    const textWidth = metrics.width;
    const radius = Math.max(minRadius, textWidth / 2 + padding);

    // Frosted circle background
    ctx.beginPath();
    ctx.arc(x, y, radius, 0, Math.PI * 2);
    ctx.fillStyle = bgColor;
    ctx.shadowColor = shadowColor;
    ctx.shadowBlur = (typeof opts.shadowBlur === 'number') ? opts.shadowBlur : LABEL_SHADOW_BLUR;
    ctx.fill();

    // Thin stroke for contrast
    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(0,0,0,0.08)';
    ctx.stroke();

    // Draw text
    ctx.fillStyle = textColor;
    ctx.fillText(text, x, y);

    // Restore defaults
    ctx.shadowBlur = 0;
    ctx.textAlign = 'start';
    ctx.textBaseline = 'alphabetic';
    ctx.restore();
}

// Render a list of labels
export function renderLabels(ctx, entries) {
    if (!entries || !entries.length) return;
    entries.forEach(e => {
        const opts = {};
        if (e.textColor) opts.textColor = e.textColor;
        if (e.bgColor) opts.bgColor = e.bgColor;
        drawFrostedLabel(ctx, e.x, e.y, e.text, opts);

        if (e.highlight) {
            ctx.beginPath();
            ctx.arc(e.x, e.y, 6, 0, Math.PI * 2);
            ctx.strokeStyle = e.highlightColor || 'rgba(0,0,0,0.2)';
            ctx.lineWidth = 2;
            ctx.stroke();
        }
    });
}
