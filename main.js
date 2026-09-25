/**
 * Smart Waste Sentinel - Frontend Live Engine
 * Handles real-time telemetry polling, toast notifications, and actuator controls.
 */

let lastAlertId = 0;

// Poll sensor data every 1500ms
function pollSensorData() {
    fetch('/api/sensor')
        .then(res => res.json())
        .then(data => {
            const lux = data.lux;
            const ledActive = data.led_active;

            // 1. Update Navbar Elements
            const navLux = document.getElementById('nav-lux-val');
            if (navLux) navLux.innerText = lux + " lx";

            const navLedDot = document.getElementById('nav-led-dot');
            const navLedText = document.getElementById('nav-led-text');
            if (navLedDot && navLedText) {
                if (ledActive) {
                    navLedDot.className = "w-2 h-2 rounded-full bg-emerald-400 shadow-lg shadow-emerald-400";
                    navLedText.innerText = "LED ACTIVE";
                    navLedText.className = "font-semibold text-emerald-400";
                } else {
                    navLedDot.className = "w-2 h-2 rounded-full bg-slate-500";
                    navLedText.innerText = "LED OFF";
                    navLedText.className = "font-medium text-slate-400";
                }
            }

            // 2. Update KPI Elements on index.html
            const kpiLux = document.getElementById('kpi-lux');
            if (kpiLux) kpiLux.innerHTML = lux + ' <span class="text-lg font-normal text-slate-400">Lux</span>';

            const kpiLuxBar = document.getElementById('kpi-lux-bar');
            if (kpiLuxBar) {
                // Max normalized to 150 lx for visual gauge
                const percent = Math.min(100, Math.max(5, (lux / 150) * 100));
                kpiLuxBar.style.width = percent + '%';
            }

            const kpiLuxMode = document.getElementById('kpi-lux-mode');
            if (kpiLuxMode) {
                if (lux < data.threshold_low) {
                    kpiLuxMode.innerText = "Night Mode (<" + data.threshold_low + " lx)";
                    kpiLuxMode.className = "font-bold text-amber-400";
                } else {
                    kpiLuxMode.innerText = "Daylight Sufficient";
                    kpiLuxMode.className = "font-medium text-emerald-400";
                }
            }

            const kpiLedStatus = document.getElementById('kpi-led-status');
            const kpiLedIconBg = document.getElementById('kpi-led-icon-bg');
            const kpiLedIcon = document.getElementById('kpi-led-icon');
            if (kpiLedStatus && kpiLedIconBg) {
                if (ledActive) {
                    kpiLedStatus.innerText = "ACTIVE";
                    kpiLedStatus.className = "text-3xl font-extrabold text-emerald-400 mt-1";
                    kpiLedIconBg.className = "w-12 h-12 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-300 text-xl shadow-lg shadow-emerald-500/20";
                    kpiLedIcon.className = "fa-solid fa-lightbulb text-emerald-300";
                } else {
                    kpiLedStatus.innerText = "OFF";
                    kpiLedStatus.className = "text-3xl font-extrabold text-slate-300 mt-1";
                    kpiLedIconBg.className = "w-12 h-12 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-500 text-xl";
                    kpiLedIcon.className = "fa-solid fa-lightbulb text-slate-500";
                }
            }
        })
        .catch(err => console.debug("Sensor poll error:", err));
}

// Poll alerts every 2500ms
function pollAlerts() {
    fetch('/api/alerts')
        .then(res => res.json())
        .then(alerts => {
            if (alerts && alerts.length > 0) {
                const latest = alerts[0];
                if (latest.id > lastAlertId) {
                    if (lastAlertId !== 0) {
                        showToastAlert(latest);
                        // Beep audio indicator using Web Audio API
                        playAlertSound();
                    }
                    lastAlertId = latest.id;
                }
            }
        })
        .catch(err => console.debug("Alerts poll error:", err));
}

// Show Toast Alert
function showToastAlert(alert) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = "pointer-events-auto bg-white border-2 border-rose-500 rounded-xl p-4 shadow-xl alert-glow text-slate-900 transition transform duration-300 translate-y-2";
    toast.innerHTML = `
        <div class="flex items-start space-x-3">
            <div class="text-rose-600 text-xl"><i class="fa-solid fa-triangle-exclamation"></i></div>
            <div class="flex-grow">
                <div class="flex items-center justify-between">
                    <h4 class="text-xs font-extrabold uppercase tracking-wider text-rose-700">${alert.title}</h4>
                    <span class="text-[10px] text-slate-500 font-mono font-bold">${alert.timestamp.split(' ')[1]}</span>
                </div>
                <p class="text-xs font-semibold text-slate-800 mt-1">${alert.message}</p>
                <p class="text-[10px] text-slate-500 font-mono mt-1">Incident ID: ${alert.incident_id}</p>
            </div>
        </div>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 400);
    }, 6000);
}

// Web Audio API Sound Generator for Real-Time Audible Alert
function playAlertSound() {
    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5 tone
        osc.frequency.exponentialRampToValueAtTime(440, audioCtx.currentTime + 0.3);
        gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gain.gain.linearRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.35);
    } catch(e) {
        console.debug("Audio autoplay prevented", e);
    }
}

// Actuator Toggle
function toggleLed() {
    fetch('/api/toggle_led', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            pollSensorData();
        });
}

// Jury Demo Lux Simulation
function setSimulatedLux(luxVal) {
    fetch('/api/simulate_lux', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lux: luxVal })
    })
    .then(res => res.json())
    .then(data => {
        pollSensorData();
    });
}

// Manual Capture
function triggerSnapshot() {
    fetch('/api/manual_capture', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                alert("Incident snapshot captured and recorded: " + data.incident_id);
                window.location.reload();
            } else {
                alert("Capture failed: " + (data.error || "Unknown"));
            }
        });
}

// Test Municipal Dispatch Alert
function testMunicipalDispatch() {
    fetch('/api/test_municipal_alert', { method: 'POST' })
        .then(res => res.json())
        .then(data => {
            if (data.success && data.dispatch) {
                alert("🚨 [MUNICIPAL ALERT SENT SUCCESSFULLY]\n\n" + data.dispatch.message);
                window.location.reload();
            } else {
                alert("Dispatch failed: " + (data.error || "Unknown error"));
            }
        })
        .catch(err => alert("Error: " + err));
}

// Initialize polling loops
document.addEventListener('DOMContentLoaded', () => {
    pollSensorData();
    setInterval(pollSensorData, 1500);
    setInterval(pollAlerts, 2500);
});
