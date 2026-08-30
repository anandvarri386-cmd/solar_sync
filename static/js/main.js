// Core Application JavaScript - Theme, Clock, Sockets, and Toast manager

// Global SocketIO Reference
let socket = null;

const AVAILABLE_THEMES = [
    { id: "dark", name: "Obsidian Midnight", icon: "fa-moon" },
    { id: "light", name: "Crystal Sunlight", icon: "fa-sun" },
    { id: "emerald", name: "Eco Emerald", icon: "fa-leaf" },
    { id: "sunset", name: "Solar Sunset", icon: "fa-fire-flame-curved" }
];

document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initClock();
    initSocket();
    initLoader();
});

/* Sidebar Toggle controls */
function toggleSidebar() {
    const sidebar = document.getElementById("sidebar");
    const overlay = document.getElementById("sidebar-overlay");
    
    if (!sidebar) return;
    
    if (sidebar.classList.contains("-translate-x-full")) {
        sidebar.classList.remove("-translate-x-full");
        if (overlay) {
            overlay.classList.remove("hidden");
            overlay.classList.add("opacity-100");
        }
    } else {
        sidebar.classList.add("-translate-x-full");
        if (overlay) {
            overlay.classList.add("hidden");
            overlay.classList.remove("opacity-100");
        }
    }
}

/* Clock Node updater */
function initClock() {
    const timeEl = document.getElementById("nav-clock-time");
    const dateEl = document.getElementById("nav-clock-date");
    
    if (!timeEl || !dateEl) return;
    
    const updateTime = () => {
        const now = new Date();
        
        // Formatted Time (HH:MM:SS AM/PM)
        let hours = now.getHours();
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        const ampm = hours >= 12 ? 'PM' : 'AM';
        hours = hours % 12;
        hours = hours ? hours : 12;
        const hoursStr = String(hours).padStart(2, '0');
        
        timeEl.textContent = `${hoursStr}:${minutes}:${seconds} ${ampm}`;
        
        // Formatted Date (MMM DD, YYYY)
        const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
        dateEl.textContent = `${months[now.getMonth()]} ${now.getDate()}, ${now.getFullYear()}`;
    };
    
    updateTime();
    setInterval(updateTime, 1000);
}

/* ==========================================================================
   Multi-Theme Manager (Dark, Light, Emerald, Sunset)
   ========================================================================== */
function initTheme() {
    const savedTheme = localStorage.getItem("theme") || "dark";
    applyTheme(savedTheme, false);
}

function setTheme(themeId) {
    applyTheme(themeId, true);
}
window.setTheme = setTheme;

function toggleTheme() {
    const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
    const currentIndex = AVAILABLE_THEMES.findIndex(t => t.id === currentTheme);
    const nextIndex = (currentIndex + 1) % AVAILABLE_THEMES.length;
    const nextTheme = AVAILABLE_THEMES[nextIndex].id;
    
    applyTheme(nextTheme, true);
}
window.toggleTheme = toggleTheme;

function applyTheme(themeId, notify = false) {
    const themeObj = AVAILABLE_THEMES.find(t => t.id === themeId) || AVAILABLE_THEMES[0];
    
    document.documentElement.setAttribute("data-theme", themeObj.id);
    localStorage.setItem("theme", themeObj.id);
    updateThemeUI(themeObj);
    
    // Broadcast event for charts and other listeners
    window.dispatchEvent(new CustomEvent("themechange", { 
        detail: { theme: themeObj.id } 
    }));
    
    if (notify && window.showToast) {
        showToast("info", `Theme switched to ${themeObj.name}.`);
    }
}

function updateThemeUI(themeObj) {
    const icon = document.getElementById("theme-toggle-icon");
    if (icon) {
        icon.className = `fa-solid ${themeObj.icon}`;
    }
    
    const themeNameLabel = document.getElementById("theme-current-label");
    if (themeNameLabel) {
        themeNameLabel.textContent = themeObj.name;
    }
    
    // Update theme selector pills in settings/modals if present
    document.querySelectorAll("[data-theme-select]").forEach(el => {
        if (el.getAttribute("data-theme-select") === themeObj.id) {
            el.classList.add("theme-pill-active");
        } else {
            el.classList.remove("theme-pill-active");
        }
    });
}

function toggleThemeMenu() {
    const menu = document.getElementById("theme-dropdown-menu");
    if (menu) {
        menu.classList.toggle("hidden");
    }
}
window.toggleThemeMenu = toggleThemeMenu;

/* Close theme dropdown when clicked outside */
document.addEventListener("click", (e) => {
    const menu = document.getElementById("theme-dropdown-menu");
    const toggleBtn = document.getElementById("btn-theme-toggle");
    if (menu && !menu.classList.contains("hidden")) {
        if (!menu.contains(e.target) && !toggleBtn.contains(e.target)) {
            menu.classList.add("hidden");
        }
    }
});

/* ==========================================================================
   SocketIO Connection manager
   ========================================================================== */
function updateGlobalESP32Status(isOnline) {
    const tag = document.getElementById("esp32-status-tag");
    if (!tag) return;
    
    if (isOnline) {
        tag.className = "flex items-center space-x-1.5 px-3 py-1.5 bg-emerald-950/30 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors duration-300";
        tag.innerHTML = `
            <span class="relative flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span>ESP32 ONLINE</span>
        `;
    } else {
        tag.className = "flex items-center space-x-1.5 px-3 py-1.5 bg-red-950/30 border border-red-500/20 text-red-400 rounded-lg text-xs font-semibold uppercase tracking-wider transition-colors duration-300";
        tag.innerHTML = `
            <span class="relative flex h-2 w-2">
              <span class="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
              <span class="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
            </span>
            <span>ESP32 OFFLINE</span>
        `;
    }
}
window.updateGlobalESP32Status = updateGlobalESP32Status;

async function checkInitialESP32Status() {
    try {
        const res = await fetch('/api/live');
        if (res.ok) {
            const data = await res.json();
            updateGlobalESP32Status(data.esp32_online);
        }
    } catch (err) {
        console.warn("Could not fetch live status:", err);
    }
}

function initSocket() {
    const indicator = document.getElementById("socket-status-indicator");
    
    // Check initial online status immediately on page load
    checkInitialESP32Status();
    
    // Connect to same host & port serving Flask app
    socket = io();
    
    socket.on('connect', () => {
        console.log("WebSocket connected.");
        if (indicator) {
            indicator.className = "w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-[var(--sidebar-bg)] glow-green animate-pulse";
            indicator.title = "Connected to Dashboard Gateway Server";
        }
        checkInitialESP32Status();
    });
    
    socket.on('disconnect', () => {
        console.warn("WebSocket disconnected.");
        if (indicator) {
            indicator.className = "w-3.5 h-3.5 rounded-full bg-red-500 border-2 border-[var(--sidebar-bg)] glow-red animate-pulse";
            indicator.title = "Disconnected from Dashboard Gateway Server";
        }
    });
    
    // Global telemetry broadcast listener (updates header ESP32 status on ALL pages)
    socket.on('telemetry', (data) => {
        updateGlobalESP32Status(data.esp32_online);
    });
    
    socket.on('toast', (data) => {
        showToast(data.type, data.message);
    });
    
    window.socket = socket;
}

/* ==========================================================================
   Toast Alerts Scheduler
   ========================================================================== */
function showToast(type, message) {
    const container = document.getElementById("toast-container");
    if (!container) return;
    
    const toast = document.createElement("div");
    toast.className = "glass-card p-3.5 shadow-xl flex items-center justify-between border-l-4 pointer-events-auto transform translate-x-12 opacity-0 transition-all duration-300";
    
    let typeConfig = {
        success: { border: "border-emerald-500", text: "text-emerald-400", icon: "fa-circle-check" },
        error: { border: "border-red-500", text: "text-red-400", icon: "fa-triangle-exclamation" },
        warning: { border: "border-amber-500", text: "text-amber-400", icon: "fa-circle-exclamation" },
        info: { border: "border-cyan-500", text: "text-cyan-400", icon: "fa-circle-info" }
    };
    
    const cfg = typeConfig[type] || typeConfig.info;
    toast.classList.add(cfg.border);
    
    toast.innerHTML = `
        <div class="flex items-center space-x-3.5">
            <i class="fa-solid ${cfg.icon} ${cfg.text} text-base"></i>
            <span class="text-xs font-mono font-medium text-theme-primary">${message}</span>
        </div>
        <button onclick="this.parentElement.remove()" class="text-theme-muted hover:text-theme-primary transition-colors pl-3">
            <i class="fa-solid fa-xmark text-xs"></i>
        </button>
    `;
    
    container.appendChild(toast);
    
    // GSAP entry animation
    if (window.gsap) {
        gsap.to(toast, {
            x: 0,
            opacity: 1,
            duration: 0.4,
            ease: "power2.out"
        });
    } else {
        toast.style.opacity = "1";
        toast.style.transform = "none";
    }
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (toast && toast.parentElement) {
            if (window.gsap) {
                gsap.to(toast, {
                    x: 100,
                    opacity: 0,
                    duration: 0.3,
                    ease: "power2.in",
                    onComplete: () => toast.remove()
                });
            } else {
                toast.remove();
            }
        }
    }, 5000);
}
window.showToast = showToast;

/* Global loader fadeout */
function initLoader() {
    const screen = document.getElementById("loading-screen");
    const bar = document.getElementById("loading-bar");
    const text = document.getElementById("loading-text");
    
    if (!screen) return;
    
    let progress = 0;
    const progressInterval = setInterval(() => {
        progress += Math.floor(Math.random() * 18) + 8;
        if (progress >= 100) {
            progress = 100;
            clearInterval(progressInterval);
            
            if (text) text.textContent = "Telemetry synchronised. Booting dashboard...";
            
            if (window.gsap) {
                gsap.to(screen, {
                    opacity: 0,
                    duration: 0.7,
                    delay: 0.2,
                    onComplete: () => {
                        screen.style.display = "none";
                        gsap.from(".glass-card", {
                            y: 20,
                            opacity: 0,
                            duration: 0.5,
                            stagger: 0.04,
                            ease: "power3.out"
                        });
                    }
                });
            } else {
                screen.style.display = "none";
            }
        }
        
        if (bar) bar.style.width = `${progress}%`;
        
        if (progress > 30 && progress < 70 && text) {
            text.textContent = "Connecting database tables...";
        } else if (progress >= 70 && progress < 90 && text) {
            text.textContent = "Establishing WebSocket gateway link...";
        }
    }, 60);
}

/* Terminate Session simulation */
function triggerLogout() {
    if (confirm("Are you sure you want to terminate the Secure Admin Session? This locks telemetry inputs.")) {
        showToast("warning", "Admin Node Session Terminated. Dashboard locked in View Only mode.");
    }
}

/* ==========================================================================
   PWA (Progressive Web App) Mobile Installer
   ========================================================================== */
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/sw.js')
            .then(reg => console.log('SolarSync PWA Service Worker Registered:', reg.scope))
            .catch(err => console.warn('PWA Service Worker Registration Failed:', err));
    });
}

let deferredPwaPrompt = null;
window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPwaPrompt = e;
    const installBtn = document.getElementById('btn-pwa-install');
    if (installBtn) {
        installBtn.classList.remove('hidden');
    }
});

function installPWAApp() {
    if (deferredPwaPrompt) {
        deferredPwaPrompt.prompt();
        deferredPwaPrompt.userChoice.then((choiceResult) => {
            if (choiceResult.outcome === 'accepted') {
                console.log('User installed SolarSync App');
                const installBtn = document.getElementById('btn-pwa-install');
                if (installBtn) installBtn.classList.add('hidden');
            }
            deferredPwaPrompt = null;
        });
    } else {
        alert("To install SolarSync as an app on your mobile phone:\n\n📱 Android (Chrome):\n1. Tap the 3 dots (⋮) in Chrome.\n2. Tap 'Add to Home screen' or 'Install app'.\n\n🍎 iPhone (Safari):\n1. Tap the Share button (square with arrow up).\n2. Tap 'Add to Home Screen'.");
    }
}
window.installPWAApp = installPWAApp;
