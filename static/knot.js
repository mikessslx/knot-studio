export const KNOTS = {
    "0_1": {
        name: "Unknot (0_1)",
        generator: (t) => {
            // Circle
            return {
                x: Math.cos(t),
                y: Math.sin(t)
            };
        },
        range: [0, 2 * Math.PI],
        scale: 150
    },
    "3_1": {
        name: "Trefoil (3_1)",
        generator: (t) => {
            // Torus knot T(3,2)
            const R = 2;
            const r = 1;
            return {
                x: (R + r * Math.cos(3 * t)) * Math.cos(2 * t),
                y: (R + r * Math.cos(3 * t)) * Math.sin(2 * t)
            };
        },
        range: [0, 2 * Math.PI],
        scale: 80
    },
    "4_1": {
        name: "Figure-8 (4_1)",
        generator: (t) => {
            // Figure-8 parametric curve
            return {
                x: 2 * Math.cos(3 * t) + Math.cos(t),
                y: 2 * Math.sin(3 * t) + Math.sin(t)
            };
        },
        range: [0, 2 * Math.PI],
        scale: 60
    },
    "5_1": {
        name: "Cinquefoil (5_1)",
        generator: (t) => {
            // Torus knot T(5,2)
            const R = 2.5;
            const r = 1;
            return {
                x: (R + r * Math.cos(5 * t)) * Math.cos(2 * t),
                y: (R + r * Math.cos(5 * t)) * Math.sin(2 * t)
            };
        },
        range: [0, 2 * Math.PI],
        scale: 70
    },
};

export function generateKnotPoints(key, centerX, centerY) {
    const preset = KNOTS[key];
    if (!preset) return [];

    const points = [];
    const steps = 200;
    const [start, end] = preset.range;
    const step = (end - start) / steps;

    for (let t = start; t <= end; t += step) {
        const p = preset.generator(t);
        points.push({
            x: p.x * preset.scale + centerX,
            y: p.y * preset.scale + centerY
        });
    }

    // Close curve
    const startP = preset.generator(start);
    points.push({
        x: startP.x * preset.scale + centerX,
        y: startP.y * preset.scale + centerY
    });

    return points;
}
