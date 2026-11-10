/**
 * Main UI Controller for Gear Reduction Solver.
 * Conforms to Modern Web Guidance for tabs, native dialogs, and Web Worker interaction.
 */

(function () {
    "use strict";

    // Application State
    const DEFAULT_TEETH = Array.from({ length: 30 }, (_, i) => i + 11); // 11 to 40
    let enabledTeeth = new Set(DEFAULT_TEETH);
    let worker = null;
    let isWorkerReady = false;
    let requestCounter = 0;
    const pendingRequests = new Map();

    // Cache DOM Elements
    const elements = {
        engineStatus: document.getElementById("engine-status"),
        inventoryBadge: document.getElementById("inventory-badge"),
        modalActiveCount: document.getElementById("modal-active-count"),
        btnOpenInventory: document.getElementById("btn-open-inventory"),
        inventoryDialog: document.getElementById("inventory-dialog"),
        btnCloseInventoryX: document.getElementById("btn-close-inventory-x"),
        btnSaveInventory: document.getElementById("btn-save-inventory"),
        btnSelectAllTeeth: document.getElementById("btn-select-all-teeth"),
        btnDeselectAllTeeth: document.getElementById("btn-deselect-all-teeth"),
        btnResetTeeth: document.getElementById("btn-reset-teeth"),
        teethMatrix: document.getElementById("teeth-matrix"),

        // Tabs
        tabSpur: document.getElementById("tab-spur"),
        tabPlanetary: document.getElementById("tab-planetary"),
        panelSpur: document.getElementById("panel-spur"),
        panelPlanetary: document.getElementById("panel-planetary"),

        // Spur Controls
        formSpur: document.getElementById("form-spur"),
        spurRatio: document.getElementById("spur-ratio"),
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
    // 3. Gear Inventory Modal & Persistence
    // =========================================================================

    function loadInventoryFromStorage() {
        try {
            const saved = localStorage.getItem("gear_reduction_teeth");
            if (saved) {
                const arr = JSON.parse(saved);
                if (Array.isArray(arr) && arr.length > 0) {
                    enabledTeeth = new Set(arr.filter((n) => Number.isInteger(n) && n >= 11 && n <= 40));
                }
            }
        } catch (e) {
            console.warn("Could not load teeth inventory from storage:", e);
        }
        updateInventoryUI();
    }

    function saveInventoryToStorage() {
        try {
            localStorage.setItem("gear_reduction_teeth", JSON.stringify(Array.from(enabledTeeth).sort((a, b) => a - b)));
        } catch (e) {
            console.warn("Could not save teeth inventory to storage:", e);
        }
        updateInventoryUI();
    }

    function renderTeethGrid() {
        elements.teethMatrix.innerHTML = "";
        for (let t = 11; t <= 40; t++) {
            const btn = document.createElement("button");
            btn.type = "button";
            btn.className = `btn-tooth ${enabledTeeth.has(t) ? "active" : ""}`;
            btn.textContent = `${t}T`;
            btn.setAttribute("aria-pressed", enabledTeeth.has(t) ? "true" : "false");
            btn.addEventListener("click", () => {
                if (enabledTeeth.has(t)) {
                    if (enabledTeeth.size <= 1) {
                        alert("At least one gear size must remain active.");
                        return;
                    }
                    enabledTeeth.delete(t);
                    btn.classList.remove("active");
                    btn.setAttribute("aria-pressed", "false");
                } else {
                    enabledTeeth.add(t);
                    btn.classList.add("active");
                    btn.setAttribute("aria-pressed", "true");
                }
                updateInventoryUI();
                saveInventoryToStorage();
            });
            elements.teethMatrix.appendChild(btn);
        }
    }

    function updateInventoryUI() {
        const count = enabledTeeth.size;
        elements.inventoryBadge.textContent = `${count}/30`;
        elements.modalActiveCount.textContent = count;
    }

    elements.btnOpenInventory.addEventListener("click", () => {
        renderTeethGrid();
        elements.inventoryDialog.showModal();
    });

    elements.btnCloseInventoryX.addEventListener("click", () => elements.inventoryDialog.close());
    elements.btnSaveInventory.addEventListener("click", () => elements.inventoryDialog.close());

    elements.btnSelectAllTeeth.addEventListener("click", () => {
        enabledTeeth = new Set(DEFAULT_TEETH);
        renderTeethGrid();
        updateInventoryUI();
        saveInventoryToStorage();
    });

    elements.btnDeselectAllTeeth.addEventListener("click", () => {
        // Keep minimum one tooth active
        enabledTeeth = new Set([12]);
        renderTeethGrid();
        updateInventoryUI();
        saveInventoryToStorage();
    });

    elements.btnResetTeeth.addEventListener("click", () => {
        enabledTeeth = new Set(DEFAULT_TEETH);
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
                available_teeth: Array.from(enabledTeeth).sort((a, b) => a - b),
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
            elements.spurResultsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🔍</span>
                    <p>No exact solutions found for ratio <strong>${escapeHtml(targetRatioStr)}</strong>.<br>
                    Try enabling <strong>Allow Approximate Ratios</strong> or increasing <strong>Max Stages</strong>.</p>
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
                available_teeth: Array.from(enabledTeeth).sort((a, b) => a - b),
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
            elements.planetaryResultsContainer.innerHTML = `
                <div class="empty-state">
                    <span class="empty-icon">🪐</span>
                    <p>No planetary configurations found for ratio <strong>${escapeHtml(targetRatioStr)}</strong>.<br>
                    Try enabling <strong>Allow Approximate Ratios</strong>, changing the <strong>Stator</strong> selection, or increasing <strong>Max Ring Teeth</strong>.</p>
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
