// Dashboard Telemetry and Controls Manager (Direct Instant Control)

// Local State variables
let isSimulating = false;
let simulationInterval = null;

// Cumulative simulation logs
let simRuntime = 0.0;
let simEnergy = 0.0;

document.addEventListener("DOMContentLoaded", () => {
    // Determine initial simulation state
    const localSimState = localStorage.getItem("simTelemetryEnabled") || "false";
    isSimulating = localSimState === "true";
    updateSimulationStateUI();

    initSocketListeners();
    initKeyboardShortcuts();
});

/* Bind SocketIO telemetries */
function initSocketListeners() {
    if (!window.socket) {
        setTimeout(initSocketListeners, 100);
        return;
    }

    const socket = window.socket;

    // Handle initial state sync
    socket.on('status_update', (data) => {
        console.log("Sync status received:", data);
        updatePumpControlsUI(data.target_status);
        if (data.latest_telemetry && data.latest_telemetry.last_updated) {
            updateDashboardWidgets(data.latest_telemetry);
        }
    });

    // Handle incoming telemetry broadcasts
    socket.on('telemetry', (data) => {
        updateDashboardWidgets(data);
    });

    // Handle direct commands update
    socket.on('pump_command', (data) => {
        updatePumpControlsUI(data.target_status);
    });
}

/* Update dashboard statistics cards & widgets */
function updateDashboardWidgets(data) {
    // 1. ESP32 online tag in header & matrix
    const tag = document.getElementById("esp32-status-tag");
    const tagLive = document.getElementById("live-esp32");
    if (tag) {
        if (data.esp32_online) {
            tag.className = "flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-950/30 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors";
            tag.innerHTML = `
                <span class="relative flex h-2 w-2">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span>ESP32 ONLINE</span>
            `;
        } else {
            tag.className = "flex items-center space-x-1.5 px-3 py-1.5 bg-red-950/30 border border-red-500/20 text-red-400 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors";
            tag.innerHTML = `
                <span class="relative flex h-2 w-2">
                  <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                  <span class="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                </span>
                <span>ESP32 OFFLINE</span>
            `;
        }
    }
    if (tagLive) {
        tagLive.textContent = data.esp32_online ? "ONLINE" : "OFFLINE";
        tagLive.className = data.esp32_online ? "text-xl font-bold font-mono mt-1 text-emerald-400" : "text-xl font-bold font-mono mt-1 text-red-500";
    }

    // 2. Animate Main Stat Card values (Current, Voltage, Power, Duration, Energy)
    animateNumericValue("val-current", data.current, 2);
    animateNumericValue("val-voltage", data.voltage, 1);
    animateNumericValue("val-power", data.power, 1);
    animateNumericValue("val-runtime", data.runtime, 2);
    animateNumericValue("val-energy", data.energy, 4);

    // Update gauge bars inside cards
    updateProgressBarWidth("bar-current", data.current, 4.0); // max 4.0A
    updateProgressBarWidth("bar-voltage", data.voltage, 24.0); // max 24.0V
    updateProgressBarWidth("bar-power", data.power, 80.0); // max 80.0W

    // 3. Update Detailed Matrix Section
    const liveCurr = document.getElementById("live-current");
    const liveVolt = document.getElementById("live-voltage");
    const livePow = document.getElementById("live-power");
    const liveStatus = document.getElementById("live-status");
    const liveTime = document.getElementById("txt-last-update-time");

    if (liveCurr) liveCurr.textContent = data.current.toFixed(2);
    if (liveVolt) liveVolt.textContent = data.voltage.toFixed(1);
    if (livePow) livePow.textContent = data.power.toFixed(1);
    if (liveTime && data.last_updated) liveTime.textContent = `Last update: ${data.last_updated}`;
    
    const isRunning = (data.current >= 1.0 || data.pump_status === 1) ? 1 : 0;
    
    if (liveStatus) {
        liveStatus.textContent = isRunning === 1 ? "ACTIVE RUN" : "STANDBY";
        liveStatus.className = isRunning === 1 ? "text-xl font-bold font-mono mt-1 text-emerald-400 animate-pulse" : "text-xl font-bold font-mono mt-1 text-theme-muted";
    }

    // Sync card status badge and relay state
    updatePumpControlsUI(isRunning);

    // 4. Push data points to charts
    if (window.appendChartData) {
        window.appendChartData(data.voltage, data.current, data.power);
    }
}

/* GSAP Number tick animator */
function animateNumericValue(elementId, endValue, decimals = 2) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const startVal = parseFloat(el.textContent) || 0;
    if (Math.abs(startVal - endValue) < 0.001) return;
    
    const obj = { val: startVal };
    if (window.gsap) {
        gsap.to(obj, {
            val: endValue,
            duration: 0.6,
            ease: "power2.out",
            onUpdate: () => {
                el.textContent = obj.val.toFixed(decimals);
            }
        });
    } else {
        el.textContent = endValue.toFixed(decimals);
    }
}

function updateProgressBarWidth(elementId, val, maxVal) {
    const el = document.getElementById(elementId);
    if (!el) return;
    const pct = Math.min(100.0, (val / maxVal) * 100.0);
    el.style.width = `${pct}%`;
}

/* Update Pump Controls UI & Active States */
function updatePumpControlsUI(targetStatus) {
    const cmdVal = document.getElementById("target-cmd-val");
    const cardStatus = document.getElementById("card-status");
    const statusTxt = document.getElementById("status-text-val");
    const statusSub = document.getElementById("status-sub");
    const statusDot = document.getElementById("status-badge-dot");
    const statusRipple = document.getElementById("status-ripple");
    const btnOn = document.getElementById("btn-pump-on");
    const btnOff = document.getElementById("btn-pump-off");
    
    if (targetStatus === 1) {
        if (cmdVal) {
            cmdVal.textContent = "PUMP RUNNING (ON)";
            cmdVal.className = "font-bold text-emerald-400 font-mono";
        }
        if (cardStatus) cardStatus.className = "glass-card p-4 relative overflow-hidden border-emerald-500/35 glow-green";
        if (statusTxt) {
            statusTxt.textContent = "PUMP ON";
            statusTxt.className = "text-2xl font-black font-mono tracking-wide text-emerald-400";
        }
        if (statusSub) statusSub.textContent = "Relay Active (Closed)";
        if (statusDot) statusDot.className = "w-2.5 h-2.5 rounded-full bg-emerald-500 glow-green animate-pulse";
        if (statusRipple) statusRipple.style.opacity = "1";
        
        // Highlight active button
        if (btnOn) btnOn.className = "h-20 bg-emerald-600 border-2 border-emerald-400 text-white font-bold rounded-2xl flex flex-col items-center justify-center space-y-1.5 transition-all duration-300 btn-ripple shadow-lg shadow-emerald-900/40 glow-green";
        if (btnOff) btnOff.className = "h-20 sub-card border border-white/5 hover:border-red-500/40 text-theme-secondary hover:text-red-400 font-bold rounded-2xl flex flex-col items-center justify-center space-y-1.5 transition-all duration-300 btn-ripple opacity-80 hover:opacity-100";
    } else {
        if (cmdVal) {
            cmdVal.textContent = "PUMP STOPPED (OFF)";
            cmdVal.className = "font-bold text-red-400 font-mono";
        }
        if (cardStatus) cardStatus.className = "glass-card p-4 relative overflow-hidden";
        if (statusTxt) {
            statusTxt.textContent = "PUMP OFF";
            statusTxt.className = "text-2xl font-black font-mono tracking-wide text-red-500";
        }
        if (statusSub) statusSub.textContent = "Relay Standby (Open)";
        if (statusDot) statusDot.className = "w-2.5 h-2.5 rounded-full bg-red-500 glow-red";
        if (statusRipple) statusRipple.style.opacity = "0";
        
        // Highlight active button
        if (btnOn) btnOn.className = "h-20 bg-emerald-950/30 border border-emerald-500/30 hover:border-emerald-400 text-emerald-400 font-bold rounded-2xl flex flex-col items-center justify-center space-y-1.5 transition-all duration-300 btn-ripple opacity-80 hover:opacity-100";
        if (btnOff) btnOff.className = "h-20 bg-red-600 border-2 border-red-400 text-white font-bold rounded-2xl flex flex-col items-center justify-center space-y-1.5 transition-all duration-300 btn-ripple shadow-lg shadow-red-900/40 glow-red";
    }
}

/* Instant Direct Control command request (NO restrictions, NO blocking modals) */
function requestPumpState(state) {
    sendPumpStateCommand(state);
    const actionText = state === 1 ? "START (ON)" : "STOP (OFF)";
    showToast(state === 1 ? "success" : "info", `Relay command sent: ${actionText}`);
}
window.requestPumpState = requestPumpState;

function sendPumpStateCommand(state) {
    if (window.socket && window.socket.connected) {
        window.socket.emit('pump_control', { target_status: state });
    } else {
        // Fallback REST call in case websocket is connecting
        fetch('/api/esp32/data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pump_status: state })
        }).catch(err => console.log(err));
    }
    updatePumpControlsUI(state);
}

/* Emergency Stop Command */
function triggerEmergencyStop() {
    console.warn("Emergency Stop triggered!");
    sendPumpStateCommand(0);
    showToast("error", "EMERGENCY SHUTDOWN: Relay cut signal dispatched.");
}
window.triggerEmergencyStop = triggerEmergencyStop;

/* Chart tabs switching logic */
function switchChartTab(tab) {
    const btnTele = document.getElementById("btn-tab-telemetry");
    const btnUsage = document.getElementById("btn-tab-usage");
    const contentTele = document.getElementById("chart-tab-telemetry-content");
    const contentUsage = document.getElementById("chart-tab-usage-content");
    
    if (!btnTele || !btnUsage) return;
    
    if (tab === 'telemetry') {
        btnTele.className = "px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-[var(--accent-cyan)]/20 border border-[var(--accent-cyan)]/30 shadow-sm transition-all duration-300";
        btnUsage.className = "px-4 py-1.5 rounded-lg text-xs font-semibold text-theme-secondary hover:text-theme-primary transition-all duration-300";
        
        contentTele.classList.remove("hidden");
        contentUsage.classList.add("hidden");
    } else {
        btnUsage.className = "px-4 py-1.5 rounded-lg text-xs font-semibold text-white bg-[var(--accent-cyan)]/20 border border-[var(--accent-cyan)]/30 shadow-sm transition-all duration-300";
        btnTele.className = "px-4 py-1.5 rounded-lg text-xs font-semibold text-theme-secondary hover:text-theme-primary transition-all duration-300";
        
        contentUsage.classList.remove("hidden");
        contentTele.classList.add("hidden");
        
        if (window.renderUsageGraphs) {
            window.renderUsageGraphs();
        }
    }
}
window.switchChartTab = switchChartTab;

/* Web Telemetry Simulators loop */
function toggleSimulationState() {
    isSimulating = !isSimulating;
    localStorage.setItem("simTelemetryEnabled", isSimulating ? "true" : "false");
    updateSimulationStateUI();
}
window.toggleSimulationState = toggleSimulationState;

function updateSimulationStateUI() {
    const btn = document.getElementById("btn-hero-sim");
    const label = document.getElementById("txt-hero-sim");
    
    if (isSimulating) {
        if (btn) {
            btn.className = "px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl text-xs font-medium flex items-center space-x-1.5 transition-all duration-300 btn-ripple shadow-md glow-purple";
            if (label) label.textContent = "Simulation Running";
        }
        startTelemetrySimulationLoop();
    } else {
        if (btn) {
            btn.className = "px-4 py-2 bg-purple-950/20 border border-purple-500/30 hover:border-purple-400 text-purple-400 rounded-xl text-xs font-medium flex items-center space-x-1.5 transition-all duration-300 btn-ripple shadow-sm shadow-purple-900/10";
            if (label) label.textContent = "Simulate Telemetry";
        }
        stopTelemetrySimulationLoop();
    }
}

function startTelemetrySimulationLoop() {
    if (simulationInterval) clearInterval(simulationInterval);
    
    showToast("info", "Telemetry Simulation started.");
    
    simulationInterval = setInterval(() => {
        const isPumpRunning = document.getElementById("status-text-val") ? document.getElementById("status-text-val").textContent.includes("ON") : false;
        
        const hour = new Date().getHours();
        let baseVolt = 0.1;
        if (6 <= hour && hour <= 18) {
            const dist = Math.abs(hour - 12.5);
            baseVolt = Math.max(8.0, 18.0 - (dist * 1.5));
        }
        
        const voltage = baseVolt + Math.sin(Date.now() / 10000) * 0.2 + (Math.random() - 0.5) * 0.05;
        let current = 0.0;
        
        if (isPumpRunning && voltage > 10.0) {
            current = 2.15 + Math.cos(Date.now() / 15000) * 0.15 + (Math.random() - 0.5) * 0.02;
            simRuntime += 1.0 / 3600.0;
        }
        
        const power = voltage * current;
        simEnergy += (power * (1.0 / 3600.0)) / 1000.0;
        
        const data = {
            voltage: Math.max(0.0, voltage),
            current: current,
            power: power,
            pump_status: isPumpRunning ? 1 : 0,
            runtime: simRuntime,
            energy: simEnergy
        };
        
        if (window.socket && window.socket.connected) {
            window.socket.emit('simulated_telemetry', data);
        }
    }, 1000);
}

function stopTelemetrySimulationLoop() {
    if (simulationInterval) {
        clearInterval(simulationInterval);
        simulationInterval = null;
        showToast("warning", "Simulation stopped. Waiting for physical ESP32 data.");
    }
}

/* FAB drawer menu */
function toggleFABMenu() {
    const menu = document.getElementById("fab-menu");
    const icon = document.getElementById("fab-icon");
    if (!menu || !icon) return;
    
    if (menu.classList.contains("hidden")) {
        menu.classList.remove("hidden");
        icon.className = "fa-solid fa-xmark";
        if (window.gsap) {
            gsap.from("#fab-menu button, #fab-menu a", {
                y: 15,
                opacity: 0,
                duration: 0.3,
                stagger: 0.05,
                ease: "back.out(1.5)"
            });
        }
    } else {
        menu.classList.add("hidden");
        icon.className = "fa-solid fa-layer-group";
    }
}

/* Keyboard shortcuts */
function initKeyboardShortcuts() {
    document.addEventListener("keydown", (e) => {
        if (e.code === "Space" && e.target.tagName !== "INPUT" && e.target.tagName !== "SELECT") {
            e.preventDefault();
            triggerEmergencyStop();
        }
        
        if (e.altKey && e.code === "KeyO") {
            e.preventDefault();
            requestPumpState(1);
        }
        
        if (e.altKey && e.code === "KeyF") {
            e.preventDefault();
            requestPumpState(0);
        }

        if (e.altKey && e.code === "KeyS") {
            e.preventDefault();
            toggleSimulationState();
        }
    });
}

function openShortcutsModal() {
    const modal = document.getElementById("shortcuts-modal");
    if (modal) {
        modal.classList.remove("hidden");
        if (window.gsap) gsap.from(modal.firstElementChild, { scale: 0.9, opacity: 0, duration: 0.3 });
    }
}

function closeShortcutsModal() {
    const modal = document.getElementById("shortcuts-modal");
    if (modal) modal.classList.add("hidden");
}

function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch(err => {
            showToast("error", `Error entering fullscreen: ${err.message}`);
        });
        showToast("success", "Entered fullscreen presentation mode.");
    } else {
        document.exitFullscreen();
        showToast("info", "Fullscreen mode terminated.");
    }
}
