// Chart.js Configuration and Visualizations with Dynamic Theme Adaptation

// Global references for charts
let voltageChart = null;
let currentChart = null;
let powerChart = null;
let dailyEnergyChart = null;
let weeklyChart = null;
let runtimeChart = null;

// Telemetry sliding window data
const maxDataPoints = 20;
const chartLabels = Array.from({length: maxDataPoints}, () => "--:--:--");
const voltageData = Array(maxDataPoints).fill(0);
const currentData = Array(maxDataPoints).fill(0);
const powerData = Array(maxDataPoints).fill(0);

document.addEventListener("DOMContentLoaded", () => {
    initTelemetryCharts();
    
    // Set page link active if loaded in index page
    const dashboardActive = document.querySelector("#nav-dashboard");
    if (dashboardActive && window.location.hash === "") {
        dashboardActive.classList.add("active");
    }
});

// Listen for theme changes from main.js
window.addEventListener("themechange", (e) => {
    updateChartsTheme(e.detail.theme);
});

/* Helper to get theme-specific chart config */
function getChartThemeColors(theme = null) {
    const currentTheme = theme || document.documentElement.getAttribute("data-theme") || "dark";
    const isLight = currentTheme === "light";
    
    return {
        gridColor: isLight ? 'rgba(15, 23, 42, 0.07)' : 'rgba(255, 255, 255, 0.05)',
        tickColor: isLight ? '#475569' : '#94a3b8',
        tooltipBg: isLight ? 'rgba(255, 255, 255, 0.96)' : 'rgba(7, 11, 30, 0.95)',
        tooltipTitle: isLight ? '#0f172a' : '#f8fafc',
        tooltipBody: isLight ? '#334155' : '#e2e8f0',
        tooltipBorder: isLight ? 'rgba(15, 23, 42, 0.12)' : 'rgba(255, 255, 255, 0.12)',
    };
}

/* Helper to generate translucent linear gradient below charts */
function createChartGradient(ctx, colorHex) {
    const gradient = ctx.createLinearGradient(0, 0, 0, 220);
    gradient.addColorStop(0, `${colorHex}40`);
    gradient.addColorStop(1, `${colorHex}00`);
    return gradient;
}

/* Global options builder */
function buildChartOptions() {
    const themeColors = getChartThemeColors();
    return {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false },
            tooltip: {
                backgroundColor: themeColors.tooltipBg,
                titleColor: themeColors.tooltipTitle,
                bodyColor: themeColors.tooltipBody,
                borderColor: themeColors.tooltipBorder,
                borderWidth: 1,
                padding: 10,
                cornerRadius: 10,
                displayColors: false,
                titleFont: { family: 'Inter', size: 11, weight: '600' },
                bodyFont: { family: 'Inter', size: 12, weight: '500' },
                boxShadow: '0 10px 25px -5px rgba(0,0,0,0.1)'
            }
        },
        scales: {
            x: {
                grid: { color: themeColors.gridColor },
                ticks: { color: themeColors.tickColor, font: { family: 'JetBrains Mono', size: 9 } }
            },
            y: {
                grid: { color: themeColors.gridColor },
                ticks: { color: themeColors.tickColor, font: { family: 'JetBrains Mono', size: 9 } }
            }
        },
        elements: {
            point: { radius: 0, hoverRadius: 5, hitRadius: 10 }
        }
    };
}

/* Initialize Rolling Telemetry Charts */
function initTelemetryCharts() {
    const options = buildChartOptions();

    // 1. Voltage Chart
    const ctxVolt = document.getElementById("chart-voltage");
    if (ctxVolt) {
        const ctx = ctxVolt.getContext("2d");
        voltageChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [{
                    data: voltageData,
                    borderColor: '#38bdf8',
                    borderWidth: 2.5,
                    tension: 0.4,
                    fill: true,
                    backgroundColor: createChartGradient(ctx, '#38bdf8')
                }]
            },
            options: {
                ...options,
                scales: {
                    ...options.scales,
                    y: { ...options.scales.y, min: 0, max: 24 }
                }
            }
        });
    }

    // 2. Current Chart
    const ctxCurr = document.getElementById("chart-current");
    if (ctxCurr) {
        const ctx = ctxCurr.getContext("2d");
        currentChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [{
                    data: currentData,
                    borderColor: '#00f5ff',
                    borderWidth: 2.5,
                    tension: 0.4,
                    fill: true,
                    backgroundColor: createChartGradient(ctx, '#00f5ff')
                }]
            },
            options: {
                ...options,
                scales: {
                    ...options.scales,
                    y: { ...options.scales.y, min: 0, max: 5 }
                }
            }
        });
    }

    // 3. Power Chart
    const ctxPow = document.getElementById("chart-power");
    if (ctxPow) {
        const ctx = ctxPow.getContext("2d");
        powerChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: chartLabels,
                datasets: [{
                    data: powerData,
                    borderColor: '#c084fc',
                    borderWidth: 2.5,
                    tension: 0.4,
                    fill: true,
                    backgroundColor: createChartGradient(ctx, '#c084fc')
                }]
            },
            options: {
                ...options,
                scales: {
                    ...options.scales,
                    y: { ...options.scales.y, min: 0, max: 80 }
                }
            }
        });
    }
}

/* Update all charts when theme switches */
function updateChartsTheme(theme) {
    const themeColors = getChartThemeColors(theme);
    const charts = [voltageChart, currentChart, powerChart, dailyEnergyChart, weeklyChart, runtimeChart];
    
    charts.forEach(chart => {
        if (!chart) return;
        
        if (chart.options.scales.x) {
            chart.options.scales.x.grid.color = themeColors.gridColor;
            chart.options.scales.x.ticks.color = themeColors.tickColor;
        }
        if (chart.options.scales.y) {
            chart.options.scales.y.grid.color = themeColors.gridColor;
            chart.options.scales.y.ticks.color = themeColors.tickColor;
        }
        if (chart.options.plugins && chart.options.plugins.tooltip) {
            chart.options.plugins.tooltip.backgroundColor = themeColors.tooltipBg;
            chart.options.plugins.tooltip.titleColor = themeColors.tooltipTitle;
            chart.options.plugins.tooltip.bodyColor = themeColors.tooltipBody;
            chart.options.plugins.tooltip.borderColor = themeColors.tooltipBorder;
        }
        
        chart.update();
    });
}

/* Append live Socket data points to rolling charts */
function appendChartData(voltage, current, power) {
    const timeStr = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    
    if (voltageChart) {
        voltageChart.data.labels.push(timeStr);
        voltageChart.data.labels.shift();
        voltageChart.data.datasets[0].data.push(voltage);
        voltageChart.data.datasets[0].data.shift();
        voltageChart.update('none');
    }

    if (currentChart) {
        currentChart.data.labels.push(timeStr);
        currentChart.data.labels.shift();
        currentChart.data.datasets[0].data.push(current);
        currentChart.data.datasets[0].data.shift();
        currentChart.update('none');
    }

    if (powerChart) {
        powerChart.data.labels.push(timeStr);
        powerChart.data.labels.shift();
        powerChart.data.datasets[0].data.push(power);
        powerChart.data.datasets[0].data.shift();
        powerChart.update('none');
    }
}
window.appendChartData = appendChartData;

/* Render Analytics graphs in the second tab */
async function renderUsageGraphs() {
    try {
        const res = await fetch('/api/energy');
        const data = await res.json();
        const options = buildChartOptions();
        
        // 1. Daily Energy Bar Chart
        const ctxDaily = document.getElementById("chart-daily-energy");
        if (ctxDaily && !dailyEnergyChart) {
            const labels = data.daily_chart.map(d => {
                const dateParts = d.date.split('-');
                return `${dateParts[1]}/${dateParts[2]}`;
            });
            const values = data.daily_chart.map(d => d.energy);
            
            const ctx = ctxDaily.getContext("2d");
            dailyEnergyChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: 'rgba(16, 185, 129, 0.45)',
                        borderColor: '#10b981',
                        borderWidth: 1.5,
                        borderRadius: 6
                    }]
                },
                options: options
            });
        }

        // 2. Weekly Energy Bar Chart
        const ctxWeekly = document.getElementById("chart-weekly-energy");
        if (ctxWeekly && !weeklyChart) {
            const labels = data.weekly_chart.map(w => w.week);
            const values = data.weekly_chart.map(w => w.energy);
            
            const ctx = ctxWeekly.getContext("2d");
            weeklyChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: 'rgba(245, 158, 11, 0.45)',
                        borderColor: '#f59e0b',
                        borderWidth: 1.5,
                        borderRadius: 6
                    }]
                },
                options: options
            });
        }

        // 3. Daily Runtime Log Chart
        const ctxRun = document.getElementById("chart-runtime-daily");
        if (ctxRun && !runtimeChart) {
            const labels = data.daily_chart.map(d => {
                const dateParts = d.date.split('-');
                return `${dateParts[1]}/${dateParts[2]}`;
            });
            const values = data.daily_chart.map(d => Math.min(8.0, d.energy * 50)); 
            
            const ctx = ctxRun.getContext("2d");
            runtimeChart = new Chart(ctx, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
                        data: values,
                        backgroundColor: 'rgba(59, 130, 246, 0.45)',
                        borderColor: '#3b82f6',
                        borderWidth: 1.5,
                        borderRadius: 6
                    }]
                },
                options: options
            });
        }
        
    } catch (e) {
        console.error("Error rendering usage analytics:", e);
    }
}
window.renderUsageGraphs = renderUsageGraphs;

/* Download Chart Image helper */
function downloadChartImage(chartId) {
    let chartObj = null;
    
    if (chartId === 'voltageChart') chartObj = voltageChart;
    else if (chartId === 'currentChart') chartObj = currentChart;
    else if (chartId === 'powerChart') chartObj = powerChart;
    else if (chartId === 'dailyEnergyChart') chartObj = dailyEnergyChart;
    else if (chartId === 'weeklyChart') chartObj = weeklyChart;
    else if (chartId === 'runtimeChart') chartObj = runtimeChart;
    
    if (!chartObj) {
        if (window.showToast) window.showToast("error", "Failed to identify chart object.");
        return;
    }
    
    const url = chartObj.toBase64Image();
    const link = document.createElement("a");
    link.href = url;
    link.download = `solar_sync_graph_${chartId}_${new Date().toISOString().slice(0,10)}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    if (window.showToast) window.showToast("success", "Chart successfully exported as PNG image.");
}
window.downloadChartImage = downloadChartImage;
