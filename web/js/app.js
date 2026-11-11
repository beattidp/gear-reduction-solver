/**
 * Main UI Controller for Gear Reduction Solver.
 * Conforms to Modern Web Guidance for tabs, native dialogs, and Web Worker interaction.
 */

(function () {
    "use strict";

    // Application State
    const DEFAULT_KNOWN_TEETH = Array.from({ length: 32 }, (_, i) => i + 9); // 9 to 40
    let knownTeeth = new Set(DEFAULT_KNOWN_TEETH);
    let availableTeeth = new Set(DEFAULT_KNOWN_TEETH);
    let worker = null;
    let isWorkerReady = false;
    let requestCounter = 0;
    const pendingRequests = new Map();

    // Cache DOM Elements
    const elements = {
        engineStatus: document.getElementById("engine-status"),
        inventoryBadge: document.getElementById("inventory-badge"),
        modalActiveCount: document.getElementById("modal-active-count"),
        modalKnownCount: document.getElementById("modal-known-count"),
        btnOpenInventory: document.getElementById("btn-open-inventory"),
        inventoryDialog: document.getElementById("inventory-dialog"),
        btnCloseInventoryX: document.getElementById("btn-close-inventory-x"),
        btnSaveInventory: document.getElementById("btn-save-inventory"),
        btnSelectAllTeeth: document.getElementById("btn-select-all-teeth"),
        btnDeselectAllTeeth: document.getElementById("btn-deselect-all-teeth"),
        btnResetTeeth: document.getElementById("btn-reset-teeth"),
        btnExportConfig: document.getElementById("btn-export-config"),
        btnImportConfig: document.getElementById("btn-import-config"),
        fileImportConfig: document.getElementById("file-import-config"),
        formAddCustomGear: document.getElementById("form-add-custom-gear"),
        inputCustomTooth: document.getElementById("input-custom-tooth"),
        btnAddCustomTooth: document.getElementById("btn-add-custom-tooth"),
        customToothFeedback: document.getElementById("custom-tooth-feedback"),
        teethMatrix: document.getElementById("teeth-matrix"),

        // Tabs
        tabSpur: document.getElementById("tab-spur"),
        tabPlanetary: document.getElementById("tab-planetary"),
        panelSpur: document.getElementById("panel-spur"),
        panelPlanetary: document.getElementById("panel-planetary"),

        // Spur Controls
        formSpur: document.getElementById("form-spur"),
        spurRatio: document.getElementById("spur-ratio"),
        spurRatioInterpretation: document.getElementById("spur-ratio-interpretation"),
        spurWorm: document.getElementById("spur-worm"),
        spurApprox: document.getElementById("spur-approx"),
        spurMaxStages: document.getElementById("spur-max-stages"),
        spurMaxSolutions: document.getElementById("spur-max-solutions"),
        spurWormMultiplier: document.getElementById("spur-worm-multiplier"),
        btnSolveSpur: document.getElementById("btn-solve-spur"),
        spurResultsContainer: document.getElementById("spur-results-container"),
        spurActions: document.getElementById("spur-actions"),
        btnCopySpurJson: document.getElementById("btn-copy-spur-json"),

        // Planetary Controls
        formPlanetary: document.getElementById("form-planetary"),
        planetaryRatio: document.getElementById("planetary-ratio"),
        planetaryRatioInterpretation: document.getElementById("planetary-ratio-interpretation"),
        planetaryPlanetsCount: document.getElementById("planetary-planets-count"),
        planetaryMaxStages: document.getElementById("planetary-max-stages"),
        planetaryMaxSolutions: document.getElementById("planetary-max-solutions"),
        planetaryApprox: document.getElementById("planetary-approx"),
        planetaryStrictRing: document.getElementById("planetary-strict-ring"),
        planetaryRingMultiplier: document.getElementById("planetary-ring-multiplier"),
        planetaryMaxRing: document.getElementById("planetary-max-ring"),
        btnSolvePlanetary: document.getElementById("btn-solve-planetary"),
        planetaryResultsContainer: document.getElementById("planetary-results-container"),
        planetaryActions: document.getElementById("planetary-actions"),
        btnCopyPlanetaryJson: document.getElementById("btn-copy-planetary-json"),
    };

    let lastSpurSolutions = [];
    let lastPlanetarySolutions = [];

    // =========================================================================
    // 1. Web Worker & Pyodide Lifecycle
    // =========================================================================

    function initWorker() {
        try {
            updateStatus("loading", "Initializing WASM...");
            worker = new Worker("js/worker.js");

            worker.onmessage = function (event) {
                const { id, type, message, data, error } = event.data;

                if (type === "status") {
                    updateStatus("loading", message);
                } else if (type === "ready") {
                    isWorkerReady = true;
                    updateStatus("ready", "WASM Solver Ready");
                } else if (type === "result") {
                    if (pendingRequests.has(id)) {
                        const { resolve } = pendingRequests.get(id);
                        pendingRequests.delete(id);
                        resolve(data);
                    }
                } else if (type === "error") {
                    if (id && pendingRequests.has(id)) {
                        const { reject } = pendingRequests.get(id);
                        pendingRequests.delete(id);
                        reject(new Error(error));
                    } else {
                        updateStatus("error", error);
                    }
                }
            };

            worker.onerror = function (err) {
                updateStatus("error", "Worker failure: " + (err.message || "Failed to load"));
            };
        } catch (e) {
            updateStatus("error", "Web Worker unavailable: " + e.message);
        }
    }

    function updateStatus(state, message) {
        elements.engineStatus.className = `status-pill status-${state}`;
        const textSpan = elements.engineStatus.querySelector(".status-text");
        if (textSpan) textSpan.textContent = message;
    }

    function sendWorkerRequest(type, payload) {
        return new Promise((resolve, reject) => {
            if (!worker) {
                return reject(new Error("Web Worker is not running"));
            }
            const id = ++requestCounter;
            pendingRequests.set(id, { resolve, reject });
            worker.postMessage({ id, type, payload });
        });
    }

    // =========================================================================
    // 2. Tab Navigation (Modern Web Guidance)
    // =========================================================================

    function switchTab(targetTab) {
        const isSpur = targetTab === elements.tabSpur;

        elements.tabSpur.setAttribute("aria-selected", isSpur ? "true" : "false");
        elements.tabPlanetary.setAttribute("aria-selected", isSpur ? "false" : "true");

        if (isSpur) {
            elements.panelSpur.removeAttribute("hidden");
            elements.panelPlanetary.setAttribute("hidden", "");
            elements.tabSpur.focus();
        } else {
            elements.panelSpur.setAttribute("hidden", "");
            elements.panelPlanetary.removeAttribute("hidden");
            elements.tabPlanetary.focus();
        }
    }

    elements.tabSpur.addEventListener("click", () => switchTab(elements.tabSpur));
    elements.tabPlanetary.addEventListener("click", () => switchTab(elements.tabPlanetary));

    // Keyboard arrow navigation between tabs
    [elements.tabSpur, elements.tabPlanetary].forEach((tab) => {
        tab.addEventListener("keydown", (e) => {
            if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                const nextTab = tab === elements.tabSpur ? elements.tabPlanetary : elements.tabSpur;
                switchTab(nextTab);
            }
        });
    });

    // =========================================================================
    // 2b. Ratio Interpretation Helper & Live Feedback
    // =========================================================================

    function interpretRatioString(str) {
        if (!str) return null;
        const clean = str.trim();
        if (!clean) return null;
        try {
            let num, den;
            if (clean.includes(":") || clean.includes("/")) {
                const parts = clean.split(/[:/]/);
                if (parts.length !== 2) return null;
                num = parseFloat(parts[0].trim());
                den = parseFloat(parts[1].trim());
            } else {
                num = parseFloat(clean);
                den = 1.0;
            }
            if (isNaN(num) || isNaN(den) || num <= 0 || den <= 0) return null;
            let val = num / den;
            let inverted = false;
            if (val < 1.0) {
                val = 1.0 / val;
                inverted = true;
            }
            const ratioDisplay = Number.isInteger(val) ? `${val}:1` : `${val.toFixed(2)}:1`;
            const text = inverted
                ? `Interpreted as ${ratioDisplay} (${val.toFixed(2)}x speed reduction)`
                : `${ratioDisplay} speed reduction`;
            return { val, inverted, ratioDisplay, text };
        } catch {
            return null;
        }
    }

    function updateRatioHint(inputEl, hintEl) {
        if (!inputEl || !hintEl) return;
        const interp = interpretRatioString(inputEl.value);
        if (interp) {
            hintEl.textContent = interp.text;
            hintEl.style.color = interp.inverted ? "var(--warning)" : "var(--accent)";
        } else {
            hintEl.textContent = "";
        }
    }

    if (elements.spurRatio && elements.spurRatioInterpretation) {
        elements.spurRatio.addEventListener("input", () => {
            updateRatioHint(elements.spurRatio, elements.spurRatioInterpretation);
        });
    }
    if (elements.planetaryRatio && elements.planetaryRatioInterpretation) {
        elements.planetaryRatio.addEventListener("input", () => {
            updateRatioHint(elements.planetaryRatio, elements.planetaryRatioInterpretation);
        });
    }

    // =========================================================================
    // 3. Gear Inventory Modal, Known Catalog & Persistence
    // =========================================================================

    function loadInventoryFromStorage() {
        try {
            const savedV2 = localStorage.getItem("gear_reduction_config_v2");
            if (savedV2) {
                const parsed = JSON.parse(savedV2);
                if (Array.isArray(parsed.known_gear_teeth) && parsed.known_gear_teeth.length > 0) {
                    knownTeeth = new Set(parsed.known_gear_teeth.filter((n) => Number.isInteger(n) && n > 0));
                }
                if (Array.isArray(parsed.available_gear_teeth) && parsed.available_gear_teeth.length > 0) {
                    availableTeeth = new Set(parsed.available_gear_teeth.filter((n) => knownTeeth.has(n)));
                }
            } else {
                // Check legacy v1 key
                const savedV1 = localStorage.getItem("gear_reduction_teeth");
                if (savedV1) {
                    const arr = JSON.parse(savedV1);
                    if (Array.isArray(arr) && arr.length > 0) {
                        availableTeeth = new Set(arr.filter((n) => Number.isInteger(n) && n > 0));
                        knownTeeth = new Set([...DEFAULT_KNOWN_TEETH, ...availableTeeth]);
                    }
                }
            }
        } catch (e) {
            console.warn("Could not load teeth inventory from storage:", e);
        }
        if (knownTeeth.size === 0) knownTeeth = new Set(DEFAULT_KNOWN_TEETH);
        if (availableTeeth.size === 0) availableTeeth = new Set(knownTeeth);
        updateInventoryUI();
    }

    function saveInventoryToStorage() {
        try {
            const data = {
                known_gear_teeth: Array.from(knownTeeth).sort((a, b) => a - b),
                available_gear_teeth: Array.from(availableTeeth).sort((a, b) => a - b),
            };
            localStorage.setItem("gear_reduction_config_v2", JSON.stringify(data));
        } catch (e) {
            console.warn("Could not save teeth inventory to storage:", e);
        }
        updateInventoryUI();
    }

    function renderTeethGrid() {
        elements.teethMatrix.innerHTML = "";
        const sortedKnown = Array.from(knownTeeth).sort((a, b) => a - b);

        sortedKnown.forEach((t) => {
            const isCustom = !DEFAULT_KNOWN_TEETH.includes(t);
            const wrapper = document.createElement("div");
            wrapper.className = "btn-tooth-wrapper";

            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `btn-tooth ${availableTeeth.has(t) ? "active" : ""} ${isCustom ? "is-custom" : ""}`;
            btn.textContent = `${t}T`;
            btn.setAttribute("aria-pressed", availableTeeth.has(t) ? "true" : "false");
            btn.title = `${t} teeth (${availableTeeth.has(t) ? "Active" : "Inactive"}${isCustom ? ", Custom" : ""})`;

            btn.addEventListener("click", () => {
                if (availableTeeth.has(t)) {
                    if (availableTeeth.size <= 1) {
                        alert("At least one gear size must remain active.");
                        return;
                    }
                    availableTeeth.delete(t);
                    btn.classList.remove("active");
                    btn.setAttribute("aria-pressed", "false");
                } else {
                    availableTeeth.add(t);
                    btn.classList.add("active");
                    btn.setAttribute("aria-pressed", "true");
                }
                updateInventoryUI();
                saveInventoryToStorage();
            });

            wrapper.appendChild(btn);

            if (isCustom) {
                const btnRemove = document.createElement("button");
                btnRemove.type = "button";
                btnRemove.className = "btn-remove-custom-tooth";
                btnRemove.innerHTML = "&times;";
                btnRemove.title = `Remove custom gear ${t}T from catalog`;
                btnRemove.setAttribute("aria-label", `Remove ${t}T`);
                btnRemove.addEventListener("click", (e) => {
                    e.stopPropagation();
                    knownTeeth.delete(t);
                    availableTeeth.delete(t);
                    if (availableTeeth.size === 0 && knownTeeth.size > 0) {
                        availableTeeth.add(Array.from(knownTeeth)[0]);
                    }
                    renderTeethGrid();
                    updateInventoryUI();
                    saveInventoryToStorage();
                });
                wrapper.appendChild(btnRemove);
            }

            elements.teethMatrix.appendChild(wrapper);
        });
    }

    function updateInventoryUI() {
        const activeCount = availableTeeth.size;
        const knownCount = knownTeeth.size;
        elements.inventoryBadge.textContent = `${activeCount}/${knownCount}`;
        elements.modalActiveCount.textContent = activeCount;
        if (elements.modalKnownCount) {
            elements.modalKnownCount.textContent = knownCount;
        }
    }

    // Add Custom Gear Size Form Handler
    if (elements.formAddCustomGear) {
        elements.formAddCustomGear.addEventListener("submit", (e) => {
            e.preventDefault();
            const val = parseInt(elements.inputCustomTooth.value, 10);
            if (!val || val <= 0 || isNaN(val)) {
                showCustomFeedback("Please enter a positive integer.", "error");
                return;
            }
            if (val < 2 || val > 300) {
                showCustomFeedback("Gear teeth must be between 2 and 300.", "error");
                return;
            }
            if (knownTeeth.has(val)) {
                showCustomFeedback(`${val}T is already in known gears.`, "error");
                return;
            }
            knownTeeth.add(val);
            availableTeeth.add(val);
            elements.inputCustomTooth.value = "";
            showCustomFeedback(`Added ${val}T to catalog and enabled it.`, "success");
            renderTeethGrid();
            updateInventoryUI();
            saveInventoryToStorage();
        });
    }

    function showCustomFeedback(msg, type) {
        if (!elements.customToothFeedback) return;
        elements.customToothFeedback.textContent = msg;
        elements.customToothFeedback.className = `custom-tooth-feedback ${type}`;
        setTimeout(() => {
            if (elements.customToothFeedback.textContent === msg) {
                elements.customToothFeedback.textContent = "";
            }
        }, 4000);
    }

    // Export configuration to JSON
    if (elements.btnExportConfig) {
        elements.btnExportConfig.addEventListener("click", () => {
            const configData = {
                known_gear_teeth: Array.from(knownTeeth).sort((a, b) => a - b),
                available_gear_teeth: Array.from(availableTeeth).sort((a, b) => a - b),
                min_gear_teeth: Math.min(...Array.from(knownTeeth)),
                max_gear_teeth: Math.max(...Array.from(knownTeeth)),
                exported_at: new Date().toISOString(),
            };
            const jsonStr = JSON.stringify(configData, null, 2);
            const blob = new Blob([jsonStr], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = "gear_inventory_config.json";
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        });
    }

    // Import configuration from JSON
    if (elements.btnImportConfig && elements.fileImportConfig) {
        elements.btnImportConfig.addEventListener("click", () => {
            elements.fileImportConfig.value = "";
            elements.fileImportConfig.click();
        });

        elements.fileImportConfig.addEventListener("change", (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = function (ev) {
                try {
                    const data = JSON.parse(ev.target.result);
                    let importedKnown = null;
                    let importedAvailable = null;

                    if (Array.isArray(data.known_gear_teeth)) {
                        importedKnown = data.known_gear_teeth.filter((n) => Number.isInteger(n) && n > 0);
                    } else if (Array.isArray(data.default_enabled_teeth)) {
                        importedKnown = data.default_enabled_teeth.filter((n) => Number.isInteger(n) && n > 0);
                    }

                    if (Array.isArray(data.available_gear_teeth)) {
                        importedAvailable = data.available_gear_teeth.filter((n) => Number.isInteger(n) && n > 0);
                    } else if (Array.isArray(data.default_enabled_teeth)) {
                        importedAvailable = data.default_enabled_teeth.filter((n) => Number.isInteger(n) && n > 0);
                    }

                    if (!importedKnown || importedKnown.length === 0) {
                        alert("Invalid JSON format: missing known_gear_teeth or default_enabled_teeth array.");
                        return;
                    }

                    knownTeeth = new Set(importedKnown);
                    if (importedAvailable && importedAvailable.length > 0) {
                        availableTeeth = new Set(importedAvailable.filter((t) => knownTeeth.has(t)));
                    } else {
                        availableTeeth = new Set(knownTeeth);
                    }
                    if (availableTeeth.size === 0) {
                        availableTeeth = new Set(knownTeeth);
                    }

                    renderTeethGrid();
                    updateInventoryUI();
                    saveInventoryToStorage();
                    alert(`Successfully imported configuration (${knownTeeth.size} known gears, ${availableTeeth.size} available).`);
                } catch (err) {
                    alert("Failed to parse JSON configuration: " + err.message);
                }
            };
            reader.readAsText(file);
        });
    }

    elements.btnOpenInventory.addEventListener("click", () => {
        renderTeethGrid();
        elements.inventoryDialog.showModal();
    });

    elements.btnCloseInventoryX.addEventListener("click", () => elements.inventoryDialog.close());
    elements.btnSaveInventory.addEventListener("click", () => elements.inventoryDialog.close());

    elements.btnSelectAllTeeth.addEventListener("click", () => {
        availableTeeth = new Set(knownTeeth);
        renderTeethGrid();
        updateInventoryUI();
        saveInventoryToStorage();
    });

    elements.btnDeselectAllTeeth.addEventListener("click", () => {
        const first = Array.from(knownTeeth)[0] || 12;
        availableTeeth = new Set([first]);
        renderTeethGrid();
        updateInventoryUI();
        saveInventoryToStorage();
    });

    elements.btnResetTeeth.addEventListener("click", () => {
        knownTeeth = new Set(DEFAULT_KNOWN_TEETH);
        availableTeeth = new Set(DEFAULT_KNOWN_TEETH);
        renderTeethGrid();
        updateInventoryUI();
        saveInventoryToStorage();
    });

    // Ratio preset buttons helper
    document.querySelectorAll(".btn-preset").forEach((btn) => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target");
            const val = btn.getAttribute("data-val");
            const input = document.getElementById(targetId);
            if (input) {
                input.value = val;
                input.focus();
                if (targetId === "spur-ratio" && elements.spurRatioInterpretation) {
                    updateRatioHint(elements.spurRatio, elements.spurRatioInterpretation);
                } else if (targetId === "planetary-ratio" && elements.planetaryRatioInterpretation) {
                    updateRatioHint(elements.planetaryRatio, elements.planetaryRatioInterpretation);
                }
            }
        });
    });

    // =========================================================================
    // 4. Spur & Worm Train Solver Execution
    // =========================================================================

    elements.formSpur.addEventListener("submit", async (e) => {
        e.preventDefault();
        const ratioStr = elements.spurRatio.value.trim();
        if (!ratioStr) return;

        setLoading(elements.btnSolveSpur, elements.spurResultsContainer, true);

        try {
            const payload = {
                ratio: ratioStr,
                available_teeth: Array.from(availableTeeth).sort((a, b) => a - b),
                use_worm: elements.spurWorm.checked,
                allow_approximate: elements.spurApprox.checked,
                max_solutions: parseInt(elements.spurMaxSolutions.value, 10),
                max_stages: parseInt(elements.spurMaxStages.value, 10),
                worm_multiplier: parseFloat(elements.spurWormMultiplier.value) || 3.0,
            };

            const solutions = await sendWorkerRequest("solve_spur", payload);
            lastSpurSolutions = solutions;
            renderSpurResults(solutions, ratioStr);
        } catch (err) {
            renderError(elements.spurResultsContainer, err.message);
        } finally {
            setLoading(elements.btnSolveSpur, elements.spurResultsContainer, false);
        }
    });

    function renderSpurResults(solutions, targetRatioStr) {
        if (!solutions || solutions.length === 0) {
            elements.spurActions.hidden = true;
            const interp = interpretRatioString(targetRatioStr);
            const interpNote = interp && interp.inverted
                ? `<div style="font-size: 0.85rem; color: var(--accent); margin-top: 0.5rem;">Target ratio was evaluated as speed reduction <strong>${interp.ratioDisplay}</strong>.</div>`
                : "";
            elements.spurResultsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🔍</span>
                    <p>No exact solutions found for target ratio <strong>${escapeHtml(targetRatioStr)}</strong>.<br>
                    Try enabling <strong>Allow Approximate Ratios</strong>, increasing <strong>Max Stages</strong>, or adding custom gear sizes.</p>
                    ${interpNote}
                </div>
            `;
            return;
        }

        elements.spurActions.hidden = false;
        let html = `
            <div class="table-responsive">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Stages (Pinion &rarr; Gear)</th>
                            <th>Achieved Ratio</th>
                            <th>Deviation</th>
                            <th>Cost</th>
                            <th>Rel. Cost</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        solutions.forEach((sol, idx) => {
            const stagesHtml = sol.stages
                .map((s) => {
                    if (s.is_worm) {
                        return `<span class="stage-pill worm-stage">Worm(1T) &rarr; ${s.gear}T</span>`;
                    }
                    return `<span class="stage-pill">${s.pinion}T &rarr; ${s.gear}T</span>`;
                })
                .join(" ");

            const devText = sol.deviation_percentage ? sol.deviation_percentage : "0.00%";
            const devClass = sol.is_approximate ? "dev-tag dev-approx" : "dev-tag";
            const relCostClass = sol.relative_cost <= 1.0 ? "rel-cost-tag rel-cost-best" : "rel-cost-tag";

            html += `
                <tr>
                    <td class="sol-rank">#${idx + 1}</td>
                    <td><div class="stages-display">${stagesHtml}</div></td>
                    <td>
                        <span class="ratio-val">${sol.achieved_ratio_fraction}</span>
                        <div class="ratio-subtext">${sol.achieved_ratio.toFixed(4)}</div>
                    </td>
                    <td><span class="${devClass}">${devText}</span></td>
                    <td><span class="cost-tag">${sol.cost}</span></td>
                    <td><span class="${relCostClass}">${sol.relative_cost.toFixed(4)}</span></td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        elements.spurResultsContainer.innerHTML = html;
    }

    elements.btnCopySpurJson.addEventListener("click", () => {
        copyToClipboard(JSON.stringify(lastSpurSolutions, null, 2), elements.btnCopySpurJson);
    });

    // =========================================================================
    // 5. Planetary Gear Train Solver Execution
    // =========================================================================

    elements.formPlanetary.addEventListener("submit", async (e) => {
        e.preventDefault();
        const ratioStr = elements.planetaryRatio.value.trim();
        if (!ratioStr) return;

        setLoading(elements.btnSolvePlanetary, elements.planetaryResultsContainer, true);

        try {
            const statorRadio = document.querySelector('input[name="planetary-stator"]:checked');
            const statorVal = statorRadio ? statorRadio.value : "any";

            const payload = {
                ratio: ratioStr,
                available_teeth: Array.from(availableTeeth).sort((a, b) => a - b),
                stator: statorVal,
                planets_count: parseInt(elements.planetaryPlanetsCount.value, 10),
                allow_approximate: elements.planetaryApprox.checked,
                max_solutions: parseInt(elements.planetaryMaxSolutions.value, 10),
                max_stages: parseInt(elements.planetaryMaxStages.value, 10),
                ring_multiplier: parseFloat(elements.planetaryRingMultiplier.value) || 1.5,
                max_ring_teeth: parseInt(elements.planetaryMaxRing.value, 10) || 120,
                strict_ring_inventory: elements.planetaryStrictRing.checked,
            };

            const solutions = await sendWorkerRequest("solve_planetary", payload);
            lastPlanetarySolutions = solutions;
            renderPlanetaryResults(solutions, ratioStr);
        } catch (err) {
            renderError(elements.planetaryResultsContainer, err.message);
        } finally {
            setLoading(elements.btnSolvePlanetary, elements.planetaryResultsContainer, false);
        }
    });

    function renderPlanetaryResults(solutions, targetRatioStr) {
        if (!solutions || solutions.length === 0) {
            elements.planetaryActions.hidden = true;
            const interp = interpretRatioString(targetRatioStr);
            const interpNote = interp && interp.inverted
                ? `<div style="font-size: 0.85rem; color: var(--accent); margin-top: 0.5rem;">Target ratio was evaluated as speed reduction <strong>${interp.ratioDisplay}</strong>.</div>`
                : "";
            elements.planetaryResultsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🪐</span>
                    <p>No planetary configurations found for target ratio <strong>${escapeHtml(targetRatioStr)}</strong>.<br>
                    Try enabling <strong>Allow Approximate Ratios</strong>, changing the <strong>Stator</strong> selection, or increasing <strong>Max Ring Teeth</strong>.</p>
                    ${interpNote}
                </div>
            `;
            return;
        }

        elements.planetaryActions.hidden = false;
        let html = `
            <div class="table-responsive">
                <table class="results-table">
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Configuration [Stator: S / P / R]</th>
                            <th>Kinematics</th>
                            <th>Achieved Ratio</th>
                            <th>Deviation</th>
                            <th>Cost</th>
                            <th>Rel. Cost</th>
                        </tr>
                    </thead>
                    <tbody>
        `;

        solutions.forEach((sol, idx) => {
            const stagesHtml = sol.stages
                .map((s) => {
                    const statorName = s.stator.charAt(0).toUpperCase() + s.stator.slice(1);
                    const invClass = s.is_inverted ? "stage-pill inverted-stage" : "stage-pill";
                    const invLabel = s.is_inverted ? " [Rev]" : "";
                    return `<span class="${invClass}">${statorName} Fixed: S=${s.sun}T, P=${s.planet}Tx${s.planets_count}, R=${s.ring}T${invLabel}</span>`;
                })
                .join("<br>");

            const directionLabel = sol.is_inverted
                ? `<span class="badge" style="background:#ec4899;">Reverse</span>`
                : `<span class="badge" style="background:#10b981;">Forward</span>`;

            const devText = sol.deviation_percentage ? sol.deviation_percentage : "0.00%";
            const devClass = sol.is_approximate ? "dev-tag dev-approx" : "dev-tag";
            const relCostClass = sol.relative_cost <= 1.0 ? "rel-cost-tag rel-cost-best" : "rel-cost-tag";

            html += `
                <tr>
                    <td class="sol-rank">#${idx + 1}</td>
                    <td><div class="stages-display">${stagesHtml}</div></td>
                    <td>${directionLabel}</td>
                    <td>
                        <span class="ratio-val">${sol.achieved_ratio_fraction}</span>
                        <div class="ratio-subtext">${sol.achieved_ratio.toFixed(4)}</div>
                    </td>
                    <td><span class="${devClass}">${devText}</span></td>
                    <td><span class="cost-tag">${sol.cost}</span></td>
                    <td><span class="${relCostClass}">${sol.relative_cost.toFixed(4)}</span></td>
                </tr>
            `;
        });

        html += `
                    </tbody>
                </table>
            </div>
        `;

        elements.planetaryResultsContainer.innerHTML = html;
    }

    elements.btnCopyPlanetaryJson.addEventListener("click", () => {
        copyToClipboard(JSON.stringify(lastPlanetarySolutions, null, 2), elements.btnCopyPlanetaryJson);
    });

    // =========================================================================
    // 6. Utility Functions
    // =========================================================================

    function setLoading(button, container, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = "Calculating...";
        } else {
            button.disabled = false;
            if (button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
            }
        }
    }

    function renderError(container, message) {
        container.innerHTML = `
            <div class="empty-state" style="color: var(--danger);">
                <span class="empty-icon">⚠️</span>
                <p><strong>Calculation Error:</strong><br>${escapeHtml(message)}</p>
            </div>
        `;
    }

    function copyToClipboard(text, button) {
        navigator.clipboard.writeText(text).then(() => {
            const originalText = button.textContent;
            button.textContent = "Copied!";
            button.disabled = true;
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
            }, 1800);
        }).catch((err) => {
            alert("Failed to copy to clipboard: " + err);
        });
    }

    function escapeHtml(str) {
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Initialize on page load
    loadInventoryFromStorage();
    initWorker();

})();
