import { drawRawStrokes, drawRecognizedKnot, renderLabels, drawOverStrand, CROSSING_LABEL_COLOR, SELECTED_BG, OFFSET_X, OFFSET_Y } from './drawing.js';
import { generateKnotPoints } from './knot.js';
import { QuandleGenerator } from './quandle.js';

document.addEventListener('DOMContentLoaded', () => {
    const isDemoMode = Boolean(window.KNOT_DEMO_MODE);
    const demoDisabledMessage = 'This computation is disabled in the public demo because it can be CPU intensive. Run the project locally or use the private research version to enable it.';
    const identifyUnsupportedMessage = 'Currently only knots with at most 9 crossings are supported.';
    const demoModal = document.getElementById('demoModal');
    const demoModalClose = document.getElementById('demoModalClose');
    const demoModalOk = document.getElementById('demoModalOk');
    const demoRepoLink = document.getElementById('demoRepoLink');
    const canvas = document.getElementById('drawingBoard');
    const ctx = canvas.getContext('2d');
    const mirrorCanvas = document.getElementById('mirrorCanvas');
    const mirrorContainer = document.querySelector('.mirror-container');
    const mirrorCtx = mirrorCanvas.getContext('2d');
    const clearBtn = document.getElementById('clearBtn');
    const undoBtn = document.getElementById('undoBtn');
    const recognizeBtn = document.getElementById('recognizeBtn');
    const calculateBtn = document.getElementById('calculateBtn');
    const stopBtn = document.getElementById('stopBtn');
    let abortController = null;
    let lastColorings = null;
    let lastCocycles = null;
    const knotSelect = document.getElementById('knotSelect');
    const saveBtn = document.getElementById('saveBtn');
    const loadBtn = document.getElementById('loadBtn');
    const fileInput = document.getElementById('fileInput');

    function showDemoDisabled() {
        if (!demoModal) {
            alert(demoDisabledMessage);
            return;
        }

        if (demoRepoLink && window.KNOT_REPO_URL) {
            demoRepoLink.href = window.KNOT_REPO_URL;
        }

        demoModal.classList.remove('hidden');
        document.body.classList.add('modal-open');
        demoModalOk?.focus();
    }

    function hideDemoModal() {
        if (!demoModal) return;
        demoModal.classList.add('hidden');
        document.body.classList.remove('modal-open');
    }

    demoModalClose?.addEventListener('click', hideDemoModal);
    demoModalOk?.addEventListener('click', hideDemoModal);
    demoModal?.addEventListener('click', (event) => {
        if (event.target === demoModal) hideDemoModal();
    });
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && demoModal && !demoModal.classList.contains('hidden')) {
            hideDemoModal();
        }
    });

    function setupDemoMode() {
        if (!isDemoMode) return;

        document.body.classList.add('demo-mode');

        const lockButton = (id) => {
            const button = document.getElementById(id);
            if (!button) return;
            button.classList.add('demo-locked-control');
            button.setAttribute('aria-disabled', 'true');
            button.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                showDemoDisabled();
            }, true);
        };

        lockButton('calculateBtn');
        lockButton('computeCocyclesBtn');
        lockButton('computeInvariantBtn');

        const turboModeCheckbox = document.getElementById('turboModeCheckbox');
        if (turboModeCheckbox) {
            const turboLabel = turboModeCheckbox.closest('label');
            turboModeCheckbox.disabled = true;
            turboLabel?.classList.add('demo-locked-control');
            turboLabel?.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopImmediatePropagation();
                showDemoDisabled();
            }, true);
        }

        document.querySelectorAll('[data-demo-lock]').forEach(section => {
            section.classList.add('demo-locked-section');
        });
    }

    function resultMessage(className, message) {
        const div = document.createElement('div');
        div.className = className;
        div.textContent = message;
        return div;
    }

    function isSingleComponentKnot(knot) {
        if (!knot || !Array.isArray(knot.arcs) || !Array.isArray(knot.crossings)) {
            return false;
        }
        if (knot.arcs.length === 0) {
            return false;
        }
        if (knot.crossings.length === 0) {
            return knot.arcs.length === 1;
        }

        const arcIds = new Set(knot.arcs);
        const adjacency = new Map(knot.arcs.map(arc => [arc, new Set()]));
        for (const crossing of knot.crossings) {
            const underIn = crossing.under_in;
            const underOut = crossing.under_out;
            if (!arcIds.has(underIn) || !arcIds.has(underOut)) {
                return false;
            }
            adjacency.get(underIn).add(underOut);
            adjacency.get(underOut).add(underIn);
        }

        const seen = new Set();
        let components = 0;
        for (const arc of knot.arcs) {
            if (seen.has(arc)) continue;
            components += 1;
            const stack = [arc];
            seen.add(arc);
            while (stack.length > 0) {
                const current = stack.pop();
                for (const neighbor of adjacency.get(current)) {
                    if (!seen.has(neighbor)) {
                        seen.add(neighbor);
                        stack.push(neighbor);
                    }
                }
            }
        }
        return components === 1;
    }

    function canIdentifyKnot(knot) {
        return (
            knot
            && Array.isArray(knot.crossings)
            && knot.crossings.length <= 9
            && isSingleComponentKnot(knot)
        );
    }

    function renderIdentifyResult(resultDiv, data) {
        const details = data.details || {};
        resultDiv.replaceChildren();

        if (data.type === 'unknot') {
            resultDiv.appendChild(resultMessage('success', 'This is the Unknot (0_1)'));
            if (details.nugatory_removed) {
                resultDiv.appendChild(resultMessage(
                    'warning',
                    `Note: ${details.nugatory_removed} nugatory crossing(s) were removed. If this knot should not be the unknot, please adjust the crossing choices (over/under assignments).`
                ));
            }
        } else if (data.type === 'prime') {
            if (details.confidence === 'exact') {
                resultDiv.appendChild(resultMessage('success', `This knot is ${data.result}`));
            } else {
                const candidates = Array.isArray(details.candidates) ? details.candidates.join(' or ') : data.result;
                resultDiv.appendChild(resultMessage(
                    'warning',
                    `This knot is either ${candidates} (indistinguishable by coloring invariants)`
                ));
            }
        } else if (data.type === 'composite') {
            const factors = Array.isArray(details.factors) ? details.factors.join(' # ') : data.result;
            resultDiv.appendChild(resultMessage('success', `This is a composite knot: ${factors}`));
        } else if (data.type === 'ambiguous') {
            const candidates = Array.isArray(details.candidates) ? details.candidates.join(' or ') : data.result;
            resultDiv.appendChild(resultMessage(
                'warning',
                `This knot is either ${candidates} (indistinguishable by coloring invariants)`
            ));
        } else {
            resultDiv.appendChild(resultMessage(
                'warning',
                identifyUnsupportedMessage
            ));
        }

        if (Array.isArray(data.signature)) {
            const signatureInfo = document.createElement('div');
            signatureInfo.className = 'signature-info';
            const small = document.createElement('small');
            small.textContent = `Signature: [${data.signature.join(', ')}]`;
            signatureInfo.appendChild(small);
            resultDiv.appendChild(signatureInfo);
        }
    }

    // Quandle controls
    const quandleTypeSelect = document.getElementById('quandleType');
    const paramInputs = {
        n: document.getElementById('param-n'),
        q: document.getElementById('param-q'),
        alpha: document.getElementById('param-alpha'),
        size: document.getElementById('param-size'),
        sn_n: document.getElementById('param-sn-n'),
        f8_t: document.getElementById('param-f8-t'),
        zni_n: document.getElementById('param-zni-n'),
        zni_real: document.getElementById('param-zni-real'),
        zni_imag: document.getElementById('param-zni-imag')
    };
    const paramDivs = {
        dihedral: document.getElementById('params-dihedral'),
        alexander: document.getElementById('params-alexander'),
        alexander_f4: document.getElementById('params-alexander-f4'),
        alexander_f8: document.getElementById('params-alexander-f8'),
        alexander_zn_i: document.getElementById('params-alexander-zn_i'),
        trivial: document.getElementById('params-trivial'),
        conjugation: document.getElementById('params-conjugation'),
        custom: null
    };
    const quandleInput = document.getElementById('quandleInput');

    function updateQuandleJSON() {
        lastColorings = null;
        lastCocycles = null;

        const type = quandleTypeSelect.value;
        let quandle = null;

        try {
            if (type === 'dihedral') {
                const n = parseInt(paramInputs.n.value) || 3;
                quandle = QuandleGenerator.createDihedral(n);
            } else if (type === 'alexander') {
                const q = parseInt(paramInputs.q.value) || 3;
                const alpha = parseInt(paramInputs.alpha.value) || 2;
                quandle = QuandleGenerator.createAlexander(q, alpha);
            } else if (type === 'alexander_f4') {
                const t = 2; // Fixed to alpha
                quandle = QuandleGenerator.createAlexanderF4(t);
            } else if (type === 'alexander_f8') {
                const t = parseInt(paramInputs.f8_t.value) || 2;
                quandle = QuandleGenerator.createAlexanderF8(t);
            } else if (type === 'alexander_zn_i') {
                const n = parseInt(paramInputs.zni_n.value) || 3;
                const tr = parseInt(paramInputs.zni_real.value) || 0;
                const ti = parseInt(paramInputs.zni_imag.value) || 1;
                quandle = QuandleGenerator.createAlexanderZn_i(n, tr, ti);
            } else if (type === 'conjugation') {
                const n = parseInt(paramInputs.sn_n.value) || 3;
                quandle = QuandleGenerator.createConjugation(n);
            } else if (type === 'trivial') {
                const size = parseInt(paramInputs.size.value) || 3;
                quandle = QuandleGenerator.createTrivial(size);
            } else if (type === 'custom') {
                return;
            }

            if (quandle) {
                // Use labels when provided
                const useLabels = !!quandle.elementLabels;
                const elements = useLabels ? quandle.elementLabels : quandle.elements;

                let opTableToSerialize = quandle.operation_table;

                // Map operation table indices to labels
                if (useLabels) {
                    opTableToSerialize = quandle.operation_table.map(row =>
                        row.map(idx => elements[idx])
                    );
                }

                // Compact JSON formatting
                const elementsStr = JSON.stringify(elements);
                const opTableStr = "[\n" + opTableToSerialize.map(row => "        " + JSON.stringify(row)).join(",\n") + "\n    ]";

                quandleInput.value = `{\n    "elements": ${elementsStr},\n    "operation_table": ${opTableStr}\n}`;
            }
        } catch (e) {
            console.error("Error: Failed to generate quandle.", e);
        }
    }

    if (quandleTypeSelect) {
        quandleTypeSelect.addEventListener('change', () => {
            const type = quandleTypeSelect.value;
            for (const [key, div] of Object.entries(paramDivs)) {
                if (div) {
                    if (key === type) div.classList.remove('hidden');
                    else div.classList.add('hidden');
                }
            }
            updateQuandleJSON();
        });

        Object.values(paramInputs).forEach(input => {
            if (input) input.addEventListener('input', updateQuandleJSON);
            if (input && input.tagName === 'SELECT') input.addEventListener('change', updateQuandleJSON);
        });

        // Update alpha options from q
        if (paramInputs.q && paramInputs.alpha) {
            const updateAlphaOptions = () => {
                const q = parseInt(paramInputs.q.value) || 3;
                const alphaSelect = paramInputs.alpha;
                const currentAlpha = parseInt(alphaSelect.value);

                alphaSelect.innerHTML = '';
                const gcd = (a, b) => b === 0 ? Math.abs(a) : gcd(b, a % b);

                // Operation is alpha*x + (1-alpha)y (right translations require gcd(alpha, q) = 1)
                for (let i = 2; i < q; i++) {
                    if (gcd(i, q) === 1) {
                        const opt = document.createElement('option');
                        opt.value = i;
                        opt.textContent = i;
                        if (i === currentAlpha) opt.selected = true;
                        alphaSelect.appendChild(opt);
                    }
                }
                // Select first when none chosen
                if (alphaSelect.selectedIndex === -1 && alphaSelect.options.length > 0) {
                    alphaSelect.selectedIndex = 0;
                }
                updateQuandleJSON();
            };

            paramInputs.q.addEventListener('change', updateAlphaOptions);
            updateAlphaOptions();
        }

        // Update Zn[i] options from n
        if (paramInputs.zni_n && paramInputs.zni_real && paramInputs.zni_imag) {
            const validateAndFix = (n) => {
                const tr = parseInt(paramInputs.zni_real.value) || 0;
                const ti = parseInt(paramInputs.zni_imag.value) || 0;

                // Disallow 0 and 1
                if ((tr === 0 && ti === 0) || (tr === 1 && ti === 0)) {
                    paramInputs.zni_imag.value = (n > 1) ? 1 : 0;
                }
            };

            const populate = (selectElem, limit) => {
                const currentVal = parseInt(selectElem.value);
                selectElem.innerHTML = '';
                for (let i = 0; i < limit; i++) {
                    const opt = document.createElement('option');
                    opt.value = i;
                    opt.textContent = i;
                    if (i === currentVal) opt.selected = true;
                    selectElem.appendChild(opt);
                }
                if (selectElem.selectedIndex === -1) selectElem.selectedIndex = 0;
            };

            const updateZnIOptions = () => {
                const n = parseInt(paramInputs.zni_n.value) || 3;

                populate(paramInputs.zni_real, n);
                populate(paramInputs.zni_imag, Math.floor(n / 2) + 1);

                validateAndFix(n);
                updateQuandleJSON();
            };

            const onParamChange = () => {
                const n = parseInt(paramInputs.zni_n.value) || 3;
                validateAndFix(n);
                updateQuandleJSON();
            };

            paramInputs.zni_n.addEventListener('change', updateZnIOptions);
            paramInputs.zni_real.addEventListener('change', onParamChange);
            paramInputs.zni_imag.addEventListener('change', onParamChange);

            updateZnIOptions();
        }

        updateQuandleJSON();
    }

    setupDemoMode();

    // Canvas setup
    canvas.width = 800;
    canvas.height = 600;
    mirrorCanvas.width = 800;
    mirrorCanvas.height = 600;

    // State
    let isDrawing = false;
    let currentStroke = [];
    let strokes = []; // Array of strokes
    let recognizedKnot = null;
    let currentColoring = null;
    let savedCrossingChoices = {}; // Store user choices for crossings

    // Drawing settings
    ctx.lineWidth = 3;
    ctx.lineCap = 'round';
    ctx.lineJoin = 'round';
    ctx.strokeStyle = '#000';

    // Event Listeners
    canvas.addEventListener('pointerdown', startDrawing);
    canvas.addEventListener('pointermove', draw);
    canvas.addEventListener('pointerup', stopDrawing);
    canvas.addEventListener('pointercancel', stopDrawing);
    canvas.addEventListener('pointerleave', stopDrawing);

    // Input mode switching
    const drawingModeContainer = document.getElementById('drawingModeContainer');
    const PDCodeModeContainer = document.getElementById('PDCodeModeContainer');
    const modeRadios = document.getElementsByName('inputMode');
    let currentMode = 'drawing';

    if (modeRadios.length > 0) {
        modeRadios.forEach(radio => {
            radio.addEventListener('change', (e) => {
                // Reset state on mode switch
                clearCanvas();
                document.getElementById('PDCodeInput').value = '';

                currentMode = e.target.value;
                if (currentMode === 'drawing') {
                    drawingModeContainer.classList.remove('hidden');
                    PDCodeModeContainer.classList.add('hidden');
                    document.getElementById('identifySection').classList.add('hidden');
                } else {
                    drawingModeContainer.classList.add('hidden');
                    PDCodeModeContainer.classList.remove('hidden');
                    document.getElementById('identifySection').classList.remove('hidden');
                }
            });
        });
    }

    clearBtn.addEventListener('click', clearCanvas);
    undoBtn.addEventListener('click', undoLastStroke);
    recognizeBtn.addEventListener('click', recognizeKnot);
    knotSelect.addEventListener('change', loadPreset);
    saveBtn.addEventListener('click', saveKnot);
    loadBtn.addEventListener('click', () => fileInput.click());
    fileInput.addEventListener('change', handleFileLoad);

    document.getElementById('identifyBtn').addEventListener('click', identifyKnot);

    async function identifyKnot() {
        const resultDiv = document.getElementById('identifyResult');
        let knot = recognizedKnot;
        if (!knot && currentMode === 'json') {
            try {
                const pdCode = document.getElementById('PDCodeInput').value;
                knot = JSON.parse(pdCode);
                if (!knot.arcs || !knot.crossings) throw new Error("Missing 'arcs' or 'crossings'.");
            } catch (e) {
                // ignore parse error
            }
        }
        if (!knot) {
            resultDiv.replaceChildren(resultMessage(
                'error',
                'No knot recognized yet. Please draw and recognize a knot first.'
            ));
            return;
        }
        if (!canIdentifyKnot(knot)) {
            resultDiv.replaceChildren(resultMessage('warning', identifyUnsupportedMessage));
            return;
        }

        resultDiv.replaceChildren(resultMessage('info', 'Computing invariants and identifying knot...'));

        try {
            const response = await fetch('/api/identify', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ knot: knot })
            });
            const data = await response.json();
            if (data.status === 'success') {
                renderIdentifyResult(resultDiv, data);
            } else {
                resultDiv.replaceChildren(resultMessage('error', `Error: ${data.message || response.statusText}`));
            }
        } catch (error) {
            resultDiv.replaceChildren(resultMessage('error', `Error: ${error.message}`));
        }
    }

    function loadPreset(e) {
        const key = e.target.value;
        if (!key) return;

        const points = generateKnotPoints(key, canvas.width / 2, canvas.height / 2);
        if (points.length > 0) {
            clearCanvas();
            strokes = [points];
            redrawCanvas();
            document.getElementById('recognitionStatus').innerText = `Loaded preset: ${key}. Click 'Recognize Knot' to analyze.`;
        }
        // Reset select
        e.target.value = "";
    }

    function startDrawing(e) {
        e.preventDefault();
        isDrawing = true;
        if (canvas.setPointerCapture && e.pointerId !== undefined) {
            canvas.setPointerCapture(e.pointerId);
        }
        const point = getMousePos(e);
        currentStroke = [point];
        ctx.beginPath();
        ctx.moveTo(point.x, point.y);
    }

    function draw(e) {
        if (!isDrawing) return;
        e.preventDefault();
        const point = getMousePos(e);

        // Sample throttle
        if (currentStroke.length > 0) {
            const lastPoint = currentStroke[currentStroke.length - 1];
            const dist = Math.hypot(point.x - lastPoint.x, point.y - lastPoint.y);
            if (dist < 5) return; // Threshold of 5 pixels
        }

        currentStroke.push(point);
        ctx.lineTo(point.x, point.y);
        ctx.stroke();
    }

    function stopDrawing(e) {
        if (!isDrawing) return;
        if (
            e &&
            canvas.releasePointerCapture &&
            canvas.hasPointerCapture &&
            e.pointerId !== undefined &&
            canvas.hasPointerCapture(e.pointerId)
        ) {
            canvas.releasePointerCapture(e.pointerId);
        }
        isDrawing = false;
        if (currentStroke.length > 1) {
            const start = currentStroke[0];
            currentStroke.push({ x: start.x, y: start.y });

            strokes.push(currentStroke);
            redrawCanvas();
        }
        currentStroke = [];
    }

    function getMousePos(e) {
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    }

    function clearCanvas() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        strokes = [];
        recognizedKnot = null;
        currentColoring = null;
        savedCrossingChoices = {};
        document.getElementById('recognitionStatus').innerHTML = '';
        document.getElementById('coloringResults').innerHTML = '';
        document.getElementById('crossingChoices').innerHTML = '';
        if (mirrorContainer) mirrorContainer.classList.add('hidden');
    }

    function undoLastStroke() {
        strokes.pop();
        recognizedKnot = null;
        currentColoring = null;
        savedCrossingChoices = {};
        redrawCanvas();
    }

    function redrawCanvas() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        if (recognizedKnot && recognizedKnot.geometry) {
            drawRecognizedKnot(ctx, recognizedKnot, currentColoring);
        } else {
            drawRawStrokes(ctx, strokes);
        }
        // Mirror canvas preview
        mirrorCtx.clearRect(0, 0, mirrorCanvas.width, mirrorCanvas.height);
        mirrorCtx.drawImage(canvas, 0, 0);
    }

    function autoCenterAndScale() {
        if (strokes.length === 0) return;

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        strokes.forEach(stroke => {
            stroke.forEach(p => {
                if (p.x < minX) minX = p.x;
                if (p.y < minY) minY = p.y;
                if (p.x > maxX) maxX = p.x;
                if (p.y > maxY) maxY = p.y;
            });
        });

        const w = maxX - minX;
        const h = maxY - minY;

        // Skip tiny drawings
        if (w < 5 && h < 5) return;

        const padding = 60;
        const availW = canvas.width - 2 * padding;
        const availH = canvas.height - 2 * padding;

        const scale = Math.min(availW / w, availH / h);

        const offsetX = (canvas.width - w * scale) / 2;
        const offsetY = (canvas.height - h * scale) / 2;

        strokes.forEach(stroke => {
            stroke.forEach(p => {
                p.x = (p.x - minX) * scale + offsetX;
                p.y = (p.y - minY) * scale + offsetY;
            });
        });

        redrawCanvas();
    }

    async function recognizeKnot() {
        // Auto-center and scale to fit canvas
        autoCenterAndScale();

        // Ensure preview panel is visible
        if (mirrorContainer) mirrorContainer.classList.remove('hidden');
        // Two-step recognition with preview choices
        document.getElementById('recognitionStatus').innerText = 'Detecting intersections...';
        try {
            const resp = await fetch('/api/recognize_preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strokes: strokes })
            });
            const previewData = await resp.json();
            if (previewData.status !== 'success') {
                document.getElementById('recognitionStatus').innerText = 'Preview error: ' + previewData.message;
                return;
            }

            const preview = previewData.preview || [];
            if (!preview.length) {
                // No crossings, finalize directly
                await finalizeRecognize({});
                return;
            }

            // Build crossing choice UI
            const container = document.getElementById('crossingChoices');
            container.innerHTML = '<h3>Choose Over Strand for Each Crossing</h3>';
            const list = document.createElement('div');
            list.className = 'crossing-list';

            currentPreview = preview;
            previewChoices = {};

            const setPreviewChoice = (item, choice, row) => {
                previewChoices[item.id] = choice;
                row.querySelectorAll('.choice-toggle-btn').forEach(btn => {
                    const isSelected = btn.dataset.choice === choice;
                    btn.classList.toggle('active', isSelected);
                    btn.setAttribute('aria-pressed', String(isSelected));
                });
                renderPreviewChoices(currentPreview, previewChoices);
            };

            preview.forEach(item => {
                const row = document.createElement('div');
                row.className = 'crossing-row';

                // Use saved choice or default to 'A'
                const initialChoice = savedCrossingChoices[item.id] || 'A';
                previewChoices[item.id] = initialChoice;

                row.innerHTML = `
                    <div class="crossing-label">Crossing ${item.id} at (${Math.round(item.x)}, ${Math.round(item.y)})</div>
                    <div class="choice-toggle" role="group" aria-label="Choose over strand for crossing ${item.id}">
                        <button type="button" class="choice-toggle-btn${initialChoice === 'A' ? ' active' : ''}" data-choice="A" aria-pressed="${initialChoice === 'A'}">A</button>
                        <button type="button" class="choice-toggle-btn${initialChoice === 'B' ? ' active' : ''}" data-choice="B" aria-pressed="${initialChoice === 'B'}">B</button>
                    </div>
                `;

                row.querySelectorAll('.choice-toggle-btn').forEach(btn => {
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        setPreviewChoice(item, btn.dataset.choice, row);
                    });
                });

                row.addEventListener('click', () => {
                    const nextChoice = previewChoices[item.id] === 'A' ? 'B' : 'A';
                    setPreviewChoice(item, nextChoice, row);
                });

                list.appendChild(row);
            });

            const applyBtn = document.createElement('button');
            applyBtn.textContent = 'Apply Choices';
            applyBtn.className = 'primary';
            applyBtn.addEventListener('click', async () => {
                await finalizeRecognize(previewChoices);
            });

            container.appendChild(list);
            container.appendChild(applyBtn);

            renderPreviewChoices(currentPreview, previewChoices);

        } catch (err) {
            console.error("Error: Preview failed.", err);
            document.getElementById('recognitionStatus').innerText = 'Preview error: ' + err.message;
        }
    }

    async function finalizeRecognize(choicesMap) {
        document.getElementById('recognitionStatus').innerText = 'Finalizing recognition...';
        try {
            const response = await fetch('/api/recognize', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ strokes: strokes, crossing_choices: choicesMap })
            });
            const data = await response.json();
            if (data.status === 'success') {
                recognizedKnot = data.knot;
                currentColoring = null;
                savedCrossingChoices = choicesMap;
                lastColorings = null;
                lastCocycles = null;

                document.getElementById('crossingChoices').innerHTML = '';
                currentPreview = null;
                previewChoices = {};
                redrawCanvas();
                document.getElementById('recognitionStatus').innerHTML = `
                    <div class="success">
                        Recognized Knot: ${recognizedKnot.arcs.length} arcs, ${recognizedKnot.crossings.length} crossings.
                        <pre>${JSON.stringify({ arcs: recognizedKnot.arcs, crossings: recognizedKnot.crossings.map(c => ({ ...c, x: Math.round(c.x), y: Math.round(c.y) })) }, null, 2)}</pre>
                    </div>
                `;
                document.getElementById('identifySection').classList.remove('hidden');
            } else {
                document.getElementById('recognitionStatus').innerText = 'Error: ' + data.message;
            }
        } catch (error) {
            console.error("Error: Failed to recognize knot.", error);
            document.getElementById('recognitionStatus').innerText = 'Error: ' + error.message;
        }
    }

    // Preview state
    let currentPreview = null;
    let previewChoices = {};

    function renderPreviewChoices(preview, choices) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        drawRawStrokes(ctx, strokes);

        if (!preview || !preview.length) return;

        const allLabels = [];

        // 1. Draw over/under effect
        preview.forEach(item => {
            const choice = choices[item.id] || 'A';
            const overStrandInfo = (choice === 'B') ? item.B : item.A;
            const pt = { x: item.x, y: item.y };

            if (overStrandInfo && strokes[overStrandInfo.s_idx]) {
                const s = strokes[overStrandInfo.s_idx];
                drawOverStrand(ctx, s, pt, '#000', overStrandInfo.p_idx);
            }
        });

        // 2. Draw crossing labels
        preview.forEach(item => {
            const pt = { x: item.x, y: item.y };
            const crossingBg = choices[item.id] ? SELECTED_BG : 'rgba(255,255,255,0.85)';
            allLabels.push({
                x: pt.x + OFFSET_X,
                y: pt.y + OFFSET_Y,
                text: String(item.id),
                textColor: CROSSING_LABEL_COLOR,
                bgColor: crossingBg
            });
        });

        renderLabels(ctx, allLabels);
    }

    // Turbo mode
    const turboModeCheckbox = document.getElementById('turboModeCheckbox');
    const normalPDInput = document.getElementById('normalPDInput');
    const turboModeInput = document.getElementById('turboModeInput');
    const knotFilesList = document.getElementById('knotFilesList');
    const toggleAllKnots = document.getElementById('toggleAllKnots');
    const toggleAllQuandles = document.getElementById('toggleAllQuandles');

    let availableKnotFiles = [];
    let solverBeforeTurbo = null;

    // Quandles
    const availableQuandles = [
        ...(() => {
            const list = [];
            const gcd = (a, b) => b === 0 ? Math.abs(a) : gcd(b, a % b);

            const isPrimePower = (n) => {
                if (n <= 1) return false;
                let temp = n;
                let div = 2;
                while (div * div <= temp) {
                    if (temp % div === 0) break;
                    div++;
                }
                if (temp % div !== 0) return true; // It's prime
                while (temp > 1 && temp % div === 0) temp /= div;
                return temp === 1;
            };

            for (let n = 3; n < 100; n++) {
                list.push({
                    type: 'Dihedral',
                    n: n,
                    label: `Dihedral (n=${n})`,
                    value: `Dihedral_${n}`
                });

                for (let alpha = 2; alpha < n - 1; alpha++) {
                    if (gcd(alpha, n) === 1) {
                        list.push({
                            type: 'Alexander',
                            q: n, // Use n as q
                            alpha: alpha,
                            label: `Alexander (q=${n}, α=${alpha})`,
                            value: `Alexander_${n}_${alpha}`
                        });
                    }
                }
            }
            return list;
        })(),

        { type: 'Alexander_F4', t: 2, label: 'Alexander (F₄, t=α)', value: 'Alexander_F4_alpha' },

        { type: 'Alexander_F8', t: 2, label: 'Alexander (F₈, t=α)', value: 'Alexander_F8_2' },
        { type: 'Alexander_F8', t: 3, label: 'Alexander (F₈, t=α+1)', value: 'Alexander_F8_3' },

        ...(() => {
            const list = [];
            const configs = {
                3: ["i", "1+i", "2", "2+i"],
                5: ["2i", "1+i", "2", "2+2i", "4"],
                7: ["i", "2i", "1+i", "2", "3"]
            };
            for (const [nStr, ts] of Object.entries(configs)) {
                const n = parseInt(nStr);
                ts.forEach(tStr => {
                    list.push({
                        type: 'Alexander_Zn_i',
                        n: n,
                        t_str: tStr,
                        label: `Alexander (Z_${n}[i], t=${tStr})`,
                        value: `Alexander_Zn_i_${n}_${tStr}`
                    });
                });
            }
            return list;
        })(),

        { type: 'Conjugation', n: 3, label: 'Conjugation (S₃)', value: 'Conjugation_3' },
        { type: 'Conjugation', n: 4, label: 'Conjugation (S₄)', value: 'Conjugation_4' },
    ];

    let connectedQuandlesLoaded = false;
    let connectedQuandles = [];

    async function loadConnectedQuandles() {
        if (connectedQuandlesLoaded) return;
        try {
            const response = await fetch('/static/quandle.json');
            if (response.ok) {
                const data = await response.json();
                connectedQuandles = data.map(q => ({
                    type: 'Connected',
                    value: q.id,
                    label: q.label || `Connected (Size ${q.size}, #${q.index})`,
                    data: q.data,
                    name: q.label
                }));
                connectedQuandlesLoaded = true;
                connectedQuandles.forEach(cq => {
                    cq.data.name = cq.label;
                });
                renderQuandleTypesList();
            } else {
                console.error("Error: Failed to load connected quandles.", response.status);
            }
        } catch (e) {
            console.error("Error: Failed to load connected quandles.", e);
        }
    }

    // Knots
    async function loadKnotFiles() {
        try {
            const response = await fetch('/api/list_data_files');
            const data = await response.json();
            if (data.status === 'success') {
                availableKnotFiles = data.files;
                renderKnotFilesList();
            }
        } catch (e) {
            console.error("Error: Failed to load knot files.", e);
        }
    }

    function updateKnotCount() {
        const cbs = document.querySelectorAll('.knot-file-cb');
        const checked = document.querySelectorAll('.knot-file-cb:checked');
        if (toggleAllKnots && toggleAllKnots.nextSibling) {
            toggleAllKnots.nextSibling.textContent = ` Select All (${checked.length}/${cbs.length})`;
        }
    }

    function updateQuandleCount() {
        const cbs = document.querySelectorAll('.quandle-type-cb');
        const checked = document.querySelectorAll('.quandle-type-cb:checked');
        if (toggleAllQuandles && toggleAllQuandles.nextSibling) {
            toggleAllQuandles.nextSibling.textContent = ` Select All (${checked.length}/${cbs.length})`;
        }
    }

    function renderKnotFilesList() {
        knotFilesList.innerHTML = '';
        availableKnotFiles.forEach(file => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.innerHTML = `<input type="checkbox" class="knot-file-cb" value="${file}"> ${file}`;
            const cb = label.querySelector('input');
            cb.addEventListener('change', updateKnotCount);
            knotFilesList.appendChild(label);
        });
        updateKnotCount();
    }

    function renderQuandleTypesList() {
        const list = document.getElementById('quandleTypesList');
        if (!list) return;
        list.innerHTML = '';

        availableQuandles.forEach(q => {
            const label = document.createElement('label');
            label.style.display = 'block';
            label.innerHTML = `<input type="checkbox" class="quandle-type-cb" value="${q.value}"> ${q.label}`;
            const cb = label.querySelector('input');
            cb.addEventListener('change', updateQuandleCount);
            list.appendChild(label);
        });

        if (connectedQuandles.length > 0) {
            const divider = document.createElement('div');
            divider.style.borderTop = '1px solid #555';
            divider.style.margin = '10px 0';
            divider.style.paddingTop = '5px';
            divider.innerHTML = '<strong style="font-size:0.9em; color:#aaa;">Connected Quandles</strong>';
            list.appendChild(divider);

            connectedQuandles.forEach(q => {
                const label = document.createElement('label');
                label.style.display = 'block';
                label.innerHTML = `<input type="checkbox" class="quandle-type-cb" value="${q.value}" data-connected="true"> ${q.label}`;
                const cb = label.querySelector('input');
                cb.addEventListener('change', updateQuandleCount);
                list.appendChild(label);
            });
        }
        updateQuandleCount();
    }

    if (turboModeCheckbox) {
        turboModeCheckbox.addEventListener('change', (e) => {
            const solverSelect = document.getElementById('solverMethod');
            const snfOption = solverSelect.querySelector('option[value="snf"]');
            const enumOption = solverSelect.querySelector('option[value="enum"]');
            const allOption = solverSelect.querySelector('option[value="all"]');

            if (e.target.checked) {
                solverBeforeTurbo = solverSelect.value;
                normalPDInput.classList.add('hidden');
                turboModeInput.classList.remove('hidden');
                if (availableKnotFiles.length === 0) {
                    loadKnotFiles();
                }
                if (availableKnotFiles.length === 0) {
                    loadKnotFiles();
                }
                loadConnectedQuandles().then(() => {
                    if (document.getElementById('quandleTypesList').children.length <= availableQuandles.length) {
                        renderQuandleTypesList();
                    }
                });

                if (document.getElementById('quandleTypesList').children.length === 0) {
                    renderQuandleTypesList();
                }
                if (snfOption) snfOption.disabled = false;
                solverSelect.value = 'snf';
                if (enumOption) enumOption.disabled = true;
                if (allOption) allOption.disabled = true;
            } else {
                normalPDInput.classList.remove('hidden');
                turboModeInput.classList.add('hidden');
                if (snfOption) snfOption.disabled = true;
                if (enumOption) enumOption.disabled = false;
                if (allOption) allOption.disabled = false;
                if (solverBeforeTurbo && solverBeforeTurbo !== 'snf') {
                    solverSelect.value = solverBeforeTurbo;
                } else {
                    solverSelect.value = 'enum';
                }
                solverBeforeTurbo = null;
            }
        });
    }

    if (toggleAllKnots) {
        toggleAllKnots.addEventListener('change', (e) => {
            document.querySelectorAll('.knot-file-cb').forEach(cb => cb.checked = e.target.checked);
            updateKnotCount();
        });
    }

    if (toggleAllQuandles) {
        toggleAllQuandles.addEventListener('change', (e) => {
            document.querySelectorAll('.quandle-type-cb').forEach(cb => cb.checked = e.target.checked);
            updateQuandleCount();
        });
    }

    if (calculateBtn) {
        calculateBtn.addEventListener('click', calculateColorings);
    }

    if (stopBtn) {
        stopBtn.addEventListener('click', () => {
            if (abortController) {
                abortController.abort();
                abortController = null;
                // Signal server to stop calculation
                fetch('/api/stop', { method: 'POST' })
                    .catch(err => console.error("Error: Failed to send stop signal.", err));
            }
        });
    }

    async function calculateColorings() {
        // Check if turbo mode is enabled
        if (currentMode === 'json' && turboModeCheckbox && turboModeCheckbox.checked) {
            await runTurboCalculation();
            return;
        }

        let knotToUse = recognizedKnot;

        if (currentMode === 'json') {
            const pdCode = document.getElementById('PDCodeInput').value;
            try {
                knotToUse = JSON.parse(pdCode);
                if (!knotToUse.arcs || !knotToUse.crossings) {
                    throw new Error("Missing 'arcs' or 'crossings'.");
                }
            } catch (e) {
                alert("Invalid knot JSON: " + e.message);
                return;
            }
        } else {
            if (!recognizedKnot) {
                alert("Please recognize a knot first.");
                return;
            }
        }

        const quandleStr = document.getElementById('quandleInput').value;
        let quandle;
        try {
            quandle = JSON.parse(quandleStr);
        } catch (e) {
            alert("Invalid quandle JSON.");
            return;
        }

        const method = document.getElementById('solverMethod').value;

        const resultsDiv = document.getElementById('coloringResults');
        resultsDiv.innerHTML = '<h3>Calculating...</h3>';

        calculateBtn.disabled = true;
        calculateBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');

        abortController = new AbortController();

        try {
            const response = await fetch('/api/calculate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    knot: knotToUse,
                    quandle: quandle,
                    method: method
                }),
                signal: abortController.signal
            });
            const data = await response.json();

            if (data.status === 'success') {
                const colorings = data.colorings;
                if (colorings.length > 1000000) {
                    lastColorings = null;
                } else {
                    lastColorings = colorings; // Cache results
                }

                let timingHtml = "";
                if (data.method === 'all' && data.results) {
                    const enumCount = data.results.enum.count;
                    const dfsCount = data.results.dfs.count;
                    const algCount = data.results.algebra ? data.results.algebra.count : -1;
                    const propCount = data.results.propagation ? data.results.propagation.count : -1;
                    const linCount = data.results.linear ? data.results.linear.count : -1;

                    let countStatus = "Counts match";
                    if (enumCount !== dfsCount || (algCount !== -1 && algCount !== enumCount) || (propCount !== -1 && propCount !== enumCount) || (linCount !== -1 && linCount !== enumCount)) {
                        countStatus = `Counts differ (Enum:${enumCount}, DFS:${dfsCount}, Alg:${algCount}, Prop:${propCount}, Linear:${linCount})`;
                    }

                    timingHtml = `<p style="font-size: 0.9em; color: #7f8c8d;">Time: Enum ${data.results.enum.time.toFixed(4)}s, DFS ${data.results.dfs.time.toFixed(4)}s`;
                    if (data.results.algebra) {
                        timingHtml += `, Alg ${data.results.algebra.time.toFixed(4)}s`;
                    }
                    if (data.results.propagation) {
                        timingHtml += `, Prop ${data.results.propagation.time.toFixed(4)}s`;
                    }
                    if (data.results.linear) {
                        timingHtml += `, Linear ${data.results.linear.time.toFixed(4)}s`;
                    }
                    timingHtml += `. ${countStatus}!</p>`;
                } else if (data.time !== undefined) {
                    timingHtml = `<p style="font-size: 0.9em; color: #7f8c8d;">Time: ${data.time.toFixed(4)}s</p>`;
                }

                if (currentMode === 'json') {
                    let html = `<h3>Found ${colorings.length} Colorings</h3>`;
                    html += timingHtml
                    if (colorings.length > 0) {
                        const sortedColorings = colorings.map(c => {
                            const sortedC = {};
                            Object.keys(c).sort((a, b) => parseInt(a) - parseInt(b)).forEach(k => {
                                sortedC[k] = c[k];
                            });
                            return sortedC;
                        });

                        let formatted = "colorings = [\n";
                        sortedColorings.forEach((c, idx) => {
                            formatted += "    " + JSON.stringify(c);
                            if (idx < sortedColorings.length - 1) {
                                formatted += ",";
                            }
                            formatted += "\n";
                        });
                        formatted += "]";

                        html += `<div style="max-height: 500px; overflow-y: auto; background: #2c3e50; padding: 10px; border-radius: 4px;">`;
                        html += `<pre style="margin: 0; font-family: monospace; white-space: pre-wrap; color: #e0e0e0;">${formatted}</pre>`;
                        html += `</div>`;
                    }
                    document.getElementById('coloringResults').innerHTML = html;
                } else {
                    let html = `<h3>Found ${colorings.length} Colorings</h3>`;
                    html += timingHtml;
                    html += `<div class="coloring-list">`;
                    colorings.forEach((c, idx) => {
                        html += `<button class="coloring-btn" data-idx="${idx}">Coloring ${idx + 1}</button>`;
                    });
                    html += `</div>`;

                    const resultsDiv = document.getElementById('coloringResults');
                    resultsDiv.innerHTML = html;

                    const buttons = resultsDiv.querySelectorAll('.coloring-btn');
                    buttons.forEach(btn => {
                        btn.addEventListener('click', () => {
                            const idx = parseInt(btn.dataset.idx);
                            currentColoring = colorings[idx];
                            redrawCanvas();
                        });
                    });

                    if (colorings.length > 0) {
                        currentColoring = colorings[0];
                        redrawCanvas();
                    }
                }

            } else {
                document.getElementById('coloringResults').innerText = "Error: " + data.message;
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                document.getElementById('coloringResults').innerHTML = '<h3 style="color: orange;">Calculation Stopped</h3>';
            } else {
                console.error("Error: Calculation failed.", error);
                document.getElementById('coloringResults').innerText = "Error: " + error.message;
            }
        } finally {
            calculateBtn.disabled = false;
            calculateBtn.classList.remove('hidden');
            stopBtn.classList.add('hidden');
            abortController = null;
        }
    }

    function saveKnot() {
        if (strokes.length === 0) {
            alert("No drawing to save.");
            return;
        }
        // Prefer preview choices when available
        const choicesToSave = (Object.keys(previewChoices).length > 0) ? previewChoices : savedCrossingChoices;

        const data = {
            strokes: strokes,
            recognizedKnot: recognizedKnot,
            crossingChoices: choicesToSave
        };
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'knot_data.json';
        a.click();
        URL.revokeObjectURL(url);
    }

    function handleFileLoad(e) {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = function (event) {
            try {
                const data = JSON.parse(event.target.result);
                if (data.strokes) {
                    clearCanvas();
                    strokes = data.strokes;
                    recognizedKnot = data.recognizedKnot || null;
                    savedCrossingChoices = data.crossingChoices || {};
                    lastColorings = null;
                    lastCocycles = null;

                    redrawCanvas();

                    if (recognizedKnot) {
                        document.getElementById('recognitionStatus').innerHTML = `
                            <div class="success">
                                Loaded Knot: ${recognizedKnot.arcs.length} arcs, ${recognizedKnot.crossings.length} crossings.
                            </div>
                        `;
                    } else {
                        document.getElementById('recognitionStatus').innerText = "Loaded drawing. Click 'Recognize Knot' to analyze.";
                    }
                } else {
                    alert("Invalid knot file format.");
                }
            } catch (err) {
                console.error("Error: Failed to load file.", err);
                alert("Error: Failed to load file: " + err.message);
            }
        };
        reader.readAsText(file);
        e.target.value = '';
    }

    async function runTurboCalculation() {
        const selectedKnotFiles = Array.from(document.querySelectorAll('.knot-file-cb:checked')).map(cb => cb.value);

        if (selectedKnotFiles.length === 0) {
            alert("Please select at least one knot file.");
            return;
        }

        const selectedQuandleTypes = Array.from(document.querySelectorAll('.quandle-type-cb:checked')).map(cb => cb.value);

        if (selectedQuandleTypes.length === 0) {
            alert("Please select at least one quandle type.");
            return;
        }

        const quandles = [];
        selectedQuandleTypes.forEach(type => {
            const [quandleType, ...params] = type.split('_');
            let quandle = null;

            if (quandleType === 'Dihedral') {
                const n = parseInt(params[0]);
                quandle = QuandleGenerator.createDihedral(n);
                quandle.name = `Dihedral(${n})`;
            } else if (quandleType === 'connected') {
                const fullValue = type;
                const found = connectedQuandles.find(cq => cq.value === fullValue);
                if (found) {
                    quandle = found.data;
                    if (!quandle.name) quandle.name = found.label;
                }
            } else if (quandleType === 'Alexander') {
                if (params[0] === 'F4') {
                    quandle = QuandleGenerator.createAlexanderF4(2);
                    quandle.name = `Alexander(F4, t=α)`;
                } else if (params[0] === 'F8') {
                    const t = parseInt(params[1]);
                    quandle = QuandleGenerator.createAlexanderF8(t);
                    const label = (t === 2) ? "α" : "α+1";
                    quandle.name = `Alexander(F8, t=${label})`;
                } else if (params[0] === 'Zn') {
                    const n = parseInt(params[2]);
                    const tStr = params[3];

                    let tr = 0, ti = 0;
                    let s = tStr.replace(/\s+/g, '');
                    if (!s.includes('i')) {
                        tr = parseInt(s);
                    } else {
                        if (s === 'i') { ti = 1; }
                        else if (s === '-i') { ti = -1; }
                        else {
                            const parts = s.split('+');
                            if (parts.length === 2) {
                                tr = parseInt(parts[0]);
                                let imagPart = parts[1].replace('i', '');
                                ti = imagPart === '' ? 1 : parseInt(imagPart);
                            } else {
                                let part = parts[0].replace('i', '');
                                ti = part === '' ? 1 : parseInt(part);
                            }
                        }
                    }

                    quandle = QuandleGenerator.createAlexanderZn_i(n, tr, ti);
                    quandle.name = `Alexander(Z${n}[i], t=${tStr})`;
                } else {
                    const q = parseInt(params[0]);
                    const alpha = parseInt(params[1]);
                    quandle = QuandleGenerator.createAlexander(q, alpha);
                    quandle.name = `Alexander(Z${q}, t=${alpha})`;
                }
            } else if (quandleType === 'Conjugation') {
                const n = parseInt(params[0]);
                quandle = QuandleGenerator.createConjugation(n);
                quandle.name = `Conjugation(S${n})`;
            } else if (quandleType === 'Trivial') {
                const size = parseInt(params[0]);
                quandle = QuandleGenerator.createTrivial(size);
                quandle.name = `Trivial(${size})`;
            }

            if (quandle) {
                quandles.push(quandle);
            }
        });

        const method = document.getElementById('solverMethod').value;
        const headers = quandles.map(q => q.name);

        calculateBtn.disabled = true;
        calculateBtn.classList.add('hidden');
        stopBtn.classList.remove('hidden');

        const resultsDiv = document.getElementById('coloringResults');
        resultsDiv.innerHTML = '';
        const tbody = initBatchTable(resultsDiv, headers);

        abortController = new AbortController();

        const fullResults = {};

        try {
            for (const knotFile of selectedKnotFiles) {
                if (abortController.signal.aborted) break;

                const response = await fetch('/api/turbo_calculate', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        knot_files: [knotFile], // Send one by one
                        quandles: quandles,
                        method: method,
                        turbo: true
                    }),
                    signal: abortController.signal
                });

                const responseText = await response.text();
                let data = null;
                try {
                    data = responseText ? JSON.parse(responseText) : null;
                } catch (_error) {
                    data = null;
                }

                if (!response.ok) {
                    throw new Error(data?.message || responseText || `Request failed with status ${response.status}`);
                }

                if (!data) {
                    throw new Error(`Invalid response from server for ${knotFile}.`);
                }

                if (data.status === 'success') {
                    Object.assign(fullResults, data.results);
                    appendBatchRow(tbody, knotFile, data.results[knotFile], headers);
                    updateDownloadButtons(fullResults, headers, selectedKnotFiles, quandles, method);

                    resultsDiv.scrollTop = resultsDiv.scrollHeight;
                } else {
                    throw new Error(data?.message || `Failed to calculate ${knotFile}.`);
                }
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                const msg = document.createElement('div');
                msg.innerHTML = '<h3 style="color: orange;">Stopped!</h3>';
                resultsDiv.prepend(msg);
            } else {
                console.error("Error:", error);
                resultsDiv.innerText = "Error: " + error.message;
            }
        } finally {
            calculateBtn.disabled = false;
            calculateBtn.classList.remove('hidden');
            stopBtn.classList.add('hidden');
            abortController = null;
        }
    }

    function initBatchTable(container, headers) {
        let html = '<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">';
        html += '<h3 style="margin: 0;">Turbo Results</h3>';
        html += '<div>';
        html += '<button id="downloadIpynbBtn" class="primary" style="padding: 5px 15px; font-size: 0.9rem; margin-right: 10px; display: none;">Download IPYNB</button>';
        html += '<button id="downloadGapBtn" class="primary" style="padding: 5px 15px; font-size: 0.9rem; margin-right: 10px; display: none;">Download GAP</button>';
        html += '<button id="downloadCsvBtn" class="primary" style="padding: 5px 15px; font-size: 0.9rem; display: none;">Download CSV</button>';
        html += '</div>';
        html += '</div>';

        // Results table container
        html += '<div style="overflow-x: auto; max-height: 600px; border: 1px solid #444; border-radius: 4px; background: #2c3e50;">';
        html += '<table id="batchResultsTable" style="border-collapse: collapse; width: 100%; color: #e0e0e0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, \'Roboto Mono\', monospace; font-size: 0.8rem;">';

        // Header
        html += '<thead style="position: sticky; top: 0; z-index: 1; background: #34495e;"><tr>';
        html += '<th style="border: 1px solid #444; padding: 10px; text-align: left;">Knot</th>';
        headers.forEach(h => {
            html += `<th style="border: 1px solid #444; padding: 10px;">${h}</th>`;
        });
        html += '</tr></thead>';
        html += '<tbody></tbody></table></div>';

        container.innerHTML = html;
        return container.querySelector('tbody');
    }

    function appendBatchRow(tbody, knot, rowData, headers) {
        const tr = document.createElement('tr');
        let totalTime = 0;
        headers.forEach(h => {
            const res = rowData[h];
            if (res) totalTime += res.time;
        });

        let html = `<td style="border: 1px solid #444; padding: 8px; font-weight: bold;">${knot}<br><span style="font-size: 0.75em; color: orange;">${totalTime.toFixed(3)}s</span></td>`;

        headers.forEach(h => {
            const res = rowData[h];
            if (res) {
                html += `<td style="border: 1px solid #444; padding: 8px; text-align: center;" title="Time: ${res.time.toFixed(4)}s">
                    ${res.count}<br>
                    <span style="font-size: 0.75em; color: #95a5a6;">${res.time.toFixed(3)}s</span>
                </td>`;
            } else {
                html += `<td style="border: 1px solid #444; padding: 8px; text-align: center; color: #888;">-</td>`;
            }
        });

        tr.innerHTML = html;
        tbody.appendChild(tr);
    }

    function updateDownloadButtons(results, headers, selectedKnotFiles, quandles, method) {
        const csvBtn = document.getElementById('downloadCsvBtn');
        if (csvBtn) {
            csvBtn.style.display = 'inline-block';
            const newCsvBtn = csvBtn.cloneNode(true);
            csvBtn.parentNode.replaceChild(newCsvBtn, csvBtn);
            newCsvBtn.addEventListener('click', () => downloadResultsAsCSV(results, headers));
        }

        const ipynbBtn = document.getElementById('downloadIpynbBtn');
        if (ipynbBtn) {
            ipynbBtn.style.display = 'inline-block';
            const newIpynbBtn = ipynbBtn.cloneNode(true);
            ipynbBtn.parentNode.replaceChild(newIpynbBtn, ipynbBtn);
            newIpynbBtn.addEventListener('click', () => downloadResultsAsIPYNB(selectedKnotFiles, quandles, method));
        }

        const gapBtn = document.getElementById('downloadGapBtn');
        if (gapBtn) {
            gapBtn.style.display = 'inline-block';
            const newGapBtn = gapBtn.cloneNode(true);
            gapBtn.parentNode.replaceChild(newGapBtn, gapBtn);
            newGapBtn.addEventListener('click', () => downloadResultsAsGAP(selectedKnotFiles, quandles));
        }
    }

    function downloadResultsAsGAP(selectedKnotFiles, quandles) {
        const payload = {
            knot_files: selectedKnotFiles,
            quandles: quandles,
            turbo: true
        };

        fetch('/api/generate_gap', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
            .then(response => response.json())
            .then(data => {
                if (data.script) {
                    const blob = new Blob([data.script], { type: 'text/plain' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'turbo_calculation.g';
                    document.body.appendChild(a);
                    a.click();
                    window.URL.revokeObjectURL(url);
                    a.remove();
                } else {
                    console.error("Error: Failed to generate GAP script (no script returned).");
                }
            })
            .catch(err => console.error("Error: Failed to generate GAP script.", err));
    }

    function downloadResultsAsCSV(results, headers) {
        const knotFiles = Object.keys(results).sort();

        const escapeCsv = (field) => {
            const stringField = String(field);
            if (stringField.includes(",")) {
                return `"${stringField}"`;
            }
            return stringField;
        };

        // CSV header
        let csvContent = "";
        csvContent += "Knot," + headers.map(escapeCsv).join(",") + "\n";

        // CSV rows
        knotFiles.forEach(knot => {
            let row = [escapeCsv(knot)];
            headers.forEach(h => {
                const res = results[knot][h];
                row.push(res ? res.count : "");
            });
            csvContent += row.join(",") + "\n";
        });

        // Trigger download
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.setAttribute("href", url);
        link.setAttribute("download", "turbo_results.csv");
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }

    function downloadResultsAsIPYNB(selectedKnotFiles, quandles, method) {
        const payload = {
            knot_files: selectedKnotFiles,
            quandles: quandles,
            method: method,
            turbo: true
        };

        fetch('/api/generate_ipynb', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        })
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'turbo_calculation.ipynb';
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                a.remove();
            })
            .catch(err => console.error("Error: Failed to generate IPYNB.", err));
    }

    // Cocycle
    const computeCocyclesBtn = document.getElementById('computeCocyclesBtn');
    const stopCocyclesBtn = document.getElementById('stopCocyclesBtn');
    const cocycleGroupSize = document.getElementById('cocycleGroupSize');
    const cocycleSolverMethod = document.getElementById('cocycleSolverMethod');
    const cocycleJustReps = document.getElementById('cocycleJustReps');
    const cocycleResults = document.getElementById('cocycleResults');

    if (cocycleSolverMethod && cocycleJustReps) {
        const updateJustRepsState = () => {
            if (cocycleSolverMethod.value === 'enum') {
                cocycleJustReps.checked = false;
                cocycleJustReps.disabled = true;
                cocycleJustReps.parentElement.style.opacity = '0.5';
                cocycleJustReps.parentElement.title = "Not available for Enumeration solver";
            } else {
                cocycleJustReps.disabled = false;
                cocycleJustReps.parentElement.style.opacity = '1';
                cocycleJustReps.parentElement.title = "";
            }
        };

        cocycleSolverMethod.addEventListener('change', updateJustRepsState);
        updateJustRepsState();
    }
    let cocycleAbortController = null;

    if (computeCocyclesBtn) {
        computeCocyclesBtn.addEventListener('click', computeCocycles);
    }

    if (stopCocyclesBtn) {
        stopCocyclesBtn.addEventListener('click', () => {
            if (cocycleAbortController) {
                cocycleAbortController.abort();
                cocycleAbortController = null;
                fetch('/api/stop', { method: 'POST' })
                    .catch(err => console.error("Error: Failed to send stop signal.", err));
            }
        });
    }

    async function computeCocycles() {
        const quandleStr = document.getElementById('quandleInput').value;
        let quandle;
        try {
            quandle = JSON.parse(quandleStr);
        } catch (e) {
            alert("Invalid quandle JSON.");
            return;
        }

        if (!quandle.elements || !quandle.operation_table) {
            alert("Quandle must include 'elements' and 'operation_table'.");
            return;
        }

        const elements = quandle.elements;
        const elemToIdx = {};
        elements.forEach((e, i) => elemToIdx[e] = i);

        const opTable = quandle.operation_table.map(row =>
            row.map(val => elemToIdx[val])
        );

        const groupSize = parseInt(cocycleGroupSize.value);
        const method = cocycleSolverMethod.value;
        const justReps = document.getElementById('cocycleJustReps').checked;

        computeCocyclesBtn.disabled = true;
        computeCocyclesBtn.classList.add('hidden');
        stopCocyclesBtn.classList.remove('hidden');
        cocycleResults.innerHTML = '<h3>Computing cocycle...</h3>';

        cocycleAbortController = new AbortController();

        try {
            const response = await fetch('/api/cocycle', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    op_table: opTable,
                    group_size: groupSize,
                    method: method,
                    just_reps: justReps
                }),
                signal: cocycleAbortController.signal
            });

            const data = await response.json();

            if (data.status === 'success') {
                if (data.cocycles.length > 1000000) {
                    lastCocycles = null;
                } else {
                    lastCocycles = data.cocycles;
                }
                renderCocycleResults(data, elements, groupSize);
            } else {
                cocycleResults.innerHTML = `<h3 style="color: #e74c3c;">Error: ${data.message}</h3>`;
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                cocycleResults.innerHTML = '<h3 style="color: orange;">Stopped!</h3>';
            } else {
                console.error("Error: Failed to compute cocycle.", error);
                cocycleResults.innerHTML = `<h3 style="color: #e74c3c;">Error: ${error.message}</h3>`;
            }
        } finally {
            computeCocyclesBtn.disabled = false;
            computeCocyclesBtn.classList.remove('hidden');
            stopCocyclesBtn.classList.add('hidden');
            cocycleAbortController = null;
        }
    }

    function renderCocycleResults(data, elements, groupSize) {
        const n = elements.length;
        let html = `<h3>Found ${data.count} 2-Cocycles (Z<sub>${groupSize}</sub>)</h3>`;
        html += `<p style="font-size: 0.9em; color: #7f8c8d;">Time: ${data.time.toFixed(4)}s | Method: ${data.method}</p>`;

        if (data.count === 0) {
            html += '<h3>No non-trivial cocycles found.</h3>';
            cocycleResults.innerHTML = html;
            return;
        }

        if (data.count > 1000) {
            html += `<h3>Found ${data.count} cocycles. Details are hidden.</h3>`;
            html += `<div style="margin-top: 20px;">
                        <button id="downloadCocyclesBtn" class="primary">Download JSON</button>
                     </div>`;
            cocycleResults.innerHTML = html;

            document.getElementById('downloadCocyclesBtn').addEventListener('click', () => {
                const formattedEntries = data.cocycles.map((matrix, idx) => {
                    const rows = matrix.map(row => `    [${row.join(', ')}]`).join(',\n');
                    return `  "cocycle_${idx + 1}": [\n${rows}\n  ]`;
                }).join(',\n');

                const jsonContent = `{\n${formattedEntries}\n}`;

                const blob = new Blob([jsonContent], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `cocycles_Z${groupSize}_${data.count}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            });
            return;
        }

        const formattedEntries = data.cocycles.map((matrix, idx) => {
            const rows = matrix.map(row => `    [${row.join(', ')}]`).join(',\n');
            return `  "cocycle_${idx + 1}": [\n${rows}\n  ]`;
        }).join(',\n');

        const outputText = `{\n${formattedEntries}\n}`;

        html += `<div class="success"><pre style="max-height: 300px;">${outputText}</pre></div>`;

        cocycleResults.innerHTML = html;
    }

    // Cocycle Invariant
    const computeInvariantBtn = document.getElementById('computeInvariantBtn');
    const stopInvariantBtn = document.getElementById('stopInvariantBtn');
    const invariantResults = document.getElementById('invariantResults');
    let invariantAbortController = null;

    if (computeInvariantBtn) {
        computeInvariantBtn.addEventListener('click', computeCocycleInvariant);
    }

    if (stopInvariantBtn) {
        stopInvariantBtn.addEventListener('click', () => {
            if (invariantAbortController) {
                invariantAbortController.abort();
                invariantAbortController = null;
                fetch('/api/stop', { method: 'POST' })
                    .catch(err => console.error("Error: Failed to send stop signal.", err));
            }
        });
    }

    async function computeCocycleInvariant() {
        // Get knot from recognized knot or PD code
        let knotToUse = recognizedKnot;

        if (currentMode === 'json') {
            const pdCode = document.getElementById('PDCodeInput').value;
            try {
                knotToUse = JSON.parse(pdCode);
                if (!knotToUse.arcs || !knotToUse.crossings) {
                    throw new Error("Invalid knot JSON.");
                }
            } catch (e) {
                alert("Please enter valid knot JSON or use Drawing Mode.");
                return;
            }
        } else {
            if (!recognizedKnot) {
                alert("Please recognize a knot first.");
                return;
            }
        }

        // Parse quandle
        const quandleStr = document.getElementById('quandleInput').value;
        let quandle;
        try {
            quandle = JSON.parse(quandleStr);
        } catch (e) {
            alert("Invalid quandle JSON.");
            return;
        }

        const groupSize = parseInt(cocycleGroupSize.value);

        computeInvariantBtn.disabled = true;
        computeInvariantBtn.classList.add('hidden');
        stopInvariantBtn.classList.remove('hidden');
        invariantResults.innerHTML = '<h3>Computing cocycle invariant...</h3>';

        invariantAbortController = new AbortController();

        try {
            const response = await fetch('/api/cocycle_invariant', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    knot: knotToUse,
                    quandle: quandle,
                    group_size: groupSize,
                    compute_all: true,
                    cocycles: lastCocycles,
                    colorings: lastColorings
                }),
                signal: invariantAbortController.signal
            });

            const data = await response.json();

            if (data.status === 'success') {
                renderInvariantResults(data, groupSize);
            } else {
                invariantResults.innerHTML = `<h3 style="color: #e74c3c;">Error: ${data.message}</h3>`;
            }
        } catch (error) {
            if (error.name === 'AbortError') {
                invariantResults.innerHTML = '<h3 style="color: orange;">Stopped!</h3>';
            } else {
                console.error("Error: Failed to compute invariant.", error);
                invariantResults.innerHTML = `<h3 style="color: #e74c3c;">Error: ${error.message}</h3>`;
            }
        } finally {
            computeInvariantBtn.disabled = false;
            computeInvariantBtn.classList.remove('hidden');
            stopInvariantBtn.classList.add('hidden');
            invariantAbortController = null;
        }
    }

    function renderInvariantResults(data, groupSize) {
        let html = `<h3>Found ${data.non_trivial_count} Non-trivial Invariants</h3>`;
        html += `<p style="color: #7f8c8d; font-size: 0.9em; margin-bottom: 15px;">
            Time: ${data.time.toFixed(4)}s | Total cocycles: ${data.total_cocycles}
        </p>`;

        if (data.results.length === 0) {
            html += '<p>No cocycles found.</p>';
            invariantResults.innerHTML = html;
            return;
        }

        // Group by polynomial
        const polyGroups = {};
        data.results.forEach((r, idx) => {
            const poly = r.polynomial;
            if (!polyGroups[poly]) {
                polyGroups[poly] = [];
            }
            polyGroups[poly].push(idx);
        });

        // Table container
        html += '<div style="overflow-x: auto; max-height: 300px; border: 1px solid #444; border-radius: 4px; background: #2c3e50;">';
        html += '<table style="border-collapse: collapse; width: 100%; color: #e0e0e0; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, \'Roboto Mono\', monospace; font-size: 0.8rem;">';
        html += '<thead style="position: sticky; top: 0; z-index: 1; background: #34495e;">';
        html += '<tr><th style="border: 1px solid #444; padding: 10px; text-align: left;">Polynomial</th>';
        html += '<th style="border: 1px solid #444; padding: 10px; text-align: left;">Cocycle</th>';
        html += '<th style="border: 1px solid #444; padding: 10px; text-align: center;">Type</th></tr>';
        html += '</thead><tbody>';

        const sortedPolys = Object.keys(polyGroups).sort((a, b) => {
            const aTrivial = !data.results[polyGroups[a][0]].is_trivial;
            const bTrivial = !data.results[polyGroups[b][0]].is_trivial;
            if (aTrivial !== bTrivial) return bTrivial - aTrivial;
            return a.localeCompare(b);
        });

        for (const poly of sortedPolys) {
            const indices = polyGroups[poly];
            const isTrivial = data.results[indices[0]].is_trivial;
            const rawWeights = data.results[indices[0]].raw_weights;
            // Use background highlight for non-trivial but keep borders
            const rowStyle = isTrivial ? '' : 'background: rgba(39, 174, 96, 0.15);';
            const typeLabel = isTrivial ?
                '<span style="color: #95a5a6;">Trivial</span>' :
                '<span style="color: #2ecc71;">Non-trivial</span>';

            html += `<tr style="${rowStyle}">`;
            html += `<td style="border: 1px solid #444; padding: 8px;">${poly} <span style="color: #95a5a6; font-size: 0.9em;">[${rawWeights.join(', ')}]</span></td>`;
            html += `<td style="border: 1px solid #444; padding: 8px;">${indices.length <= 10 ? indices.map(i => `cocycle_${i + 1}`).join(', ') : indices.slice(0, 5).map(i => `cocycle_${i + 1}`).join(', ') + `... (+${indices.length - 5})`}</td>`;
            html += `<td style="border: 1px solid #444; padding: 8px; text-align: center;">${typeLabel}</td>`;
            html += '</tr>';
        }

        html += '</tbody></table></div>';

        invariantResults.innerHTML = html;
    }
});
