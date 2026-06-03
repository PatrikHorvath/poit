const API = window.location.origin;
const socket = io(API);

let monitoringActive = false;

// Oddelené stavy pre live a historické dáta
let liveTemperatures = [];
let historyTemperatures = [];

let liveChart = null;
let historyChart = null;

let currentLiveView = 'chart';
let currentHistoryView = 'chart';

// ============ SOCKET EVENTY ============

socket.on('connect', () => {
    console.log('Pripojené k serveru');
    loadDeviceStatus();
});

socket.on('device_status_update', (data) => {
    updateDeviceUI(data.status, data.connected);
});

socket.on('monitoring_confirmed', (data) => {
    if (data.status === 'active') {
        monitoringActive = true;
        document.getElementById('btn-start-monitor').disabled = true;
        document.getElementById('btn-stop-monitor').disabled = false;
        document.getElementById('monitoring-panel').style.display = 'block';
    } else {
        monitoringActive = false;
        document.getElementById('btn-start-monitor').disabled = false;
        document.getElementById('btn-stop-monitor').disabled = true;
        document.getElementById('monitoring-panel').style.display = 'none';
    }
});

socket.on('debug_error', (data) => {
    showNotification(`Chyba: ${data.error}`, 'error');
});

socket.on('debug_success', (data) => {
    showNotification(data.message, 'success');
});

socket.on('live_temperature', (data) => {
    if (!monitoringActive) return;

    liveTemperatures.push(data);
    updateLiveDisplay(data.value, data.timestamp);

    if (currentLiveView === 'chart') {
        addDataToLiveChart(data.value, data.pwm, data.timestamp);
    } else if (currentLiveView === 'table') {
        updateLiveTable(liveTemperatures);
    } else if (currentLiveView === 'gauge') {
        updateLiveGauge(liveTemperatures);
    }
});

// ============ ZAPNUTIE/VYPNUTIE SYSTÉMU ============

async function controlSystem(command) {
    try {
        const response = await fetch(`${API}/api/device/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command })
        });
        const data = await response.json();
        if (response.ok) {
            showNotification(data.message, 'success');
        } else {
            showNotification(`Chyba: ${data.error}`, 'error');
        }
    } catch (err) {
        showNotification(`Chyba: ${err.message}`, 'error');
    }
}

function sendDebugPwm() {
    const input = document.getElementById('debug-pwm-input');
    const pwmValue = parseInt(input.value, 10);

    if (isNaN(pwmValue) || pwmValue < 0 || pwmValue > 100) {
        showNotification('Zadajte platnú hodnotu PWM medzi 0 a 100', 'error');
        return;
    }

    socket.emit('set_peltier_pwm', { pwm: pwmValue });
}

// ============ SLEDOVANIE ============

async function startMonitoring() {
    liveTemperatures = [];
    if (liveChart) {
        liveChart.data.labels = [];
        liveChart.data.datasets[0].data = [];
        liveChart.data.datasets[1].data = [];
        liveChart.update();
    }
    socket.emit('join_monitoring');
    showNotification('Monitorovanie spustené', 'success');
}
function stopMonitoring() {
    if (!monitoringActive) return;
    socket.emit('leave_monitoring');
    showNotification('Monitorovanie zastavené', 'info');
}

function downloadLiveDataJSON() {
    if (liveTemperatures.length === 0) {
        showNotification('Žiadne live dáta na stiahnutie', 'error');
        return;
    }

    const measurements = liveTemperatures.map((t, index) => ({
        id: index + 1,
        temperature: t.value,
        peltier_pwm: t.pwm,
        time_measured: t.timestamp
    }));

    const exportData = {
        exported_at: new Date().toISOString(),
        count: measurements.length,
        from: measurements[0].time_measured,
        to: measurements[measurements.length - 1].time_measured,
        measurements: measurements
    };

    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const a = document.createElement('a');
    a.href = url;
    a.download = `live-temperatures-${ts}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    showNotification(`Stiahnutých ${measurements.length} meraní`, 'success');
}

// ============ LIVE VIZUALIZÁCIA ============

function switchLiveView(view, event) {
    currentLiveView = view;

    document.querySelectorAll('#monitoring-panel .view-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    document.getElementById('live-chart-view').style.display = 'none';
    document.getElementById('live-table-view').style.display = 'none';
    document.getElementById('live-gauge-view').style.display = 'none';
    document.getElementById(`live-${view}-view`).style.display = 'block';

    if (liveTemperatures.length > 0) {
        updateLiveVisualization(liveTemperatures);
    }
}

function updateLiveVisualization(temperatures) {
    switch (currentLiveView) {
        case 'chart': updateLiveChartFull(temperatures); break;
        case 'table': updateLiveTable(temperatures); break;
        case 'gauge': updateLiveGauge(temperatures); break;
    }
}

function updateLiveChartFull(temperatures) {
    const ctx = document.getElementById('live-temperature-chart').getContext('2d');
    const labels = temperatures.map(t => new Date(t.timestamp).toLocaleTimeString());
    const tempValues = temperatures.map(t => t.value);
    const pwmValues = temperatures.map(t => t.pwm);

    if (liveChart) {
        liveChart.data.labels = labels;
        liveChart.data.datasets[0].data = tempValues;
        liveChart.data.datasets[1].data = pwmValues;
        liveChart.update();
    } else {
        liveChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Teplota (°C)',
                        data: tempValues,
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        tension: 0.3,
                        fill: true,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Peltier PWM (%)',
                        data: pwmValues,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        tension: 0.3,
                        fill: false,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: chartOptions()
        });
    }
}

function addDataToLiveChart(temperature, pwm, timestamp) {
    if (currentLiveView !== 'chart') return;

    const ctx = document.getElementById('live-temperature-chart').getContext('2d');
    const newLabel = new Date(timestamp).toLocaleTimeString();

    if (!liveChart) {
        updateLiveChartFull(liveTemperatures);
        return;
    }

    liveChart.data.labels.push(newLabel);
    liveChart.data.datasets[0].data.push(temperature);
    liveChart.data.datasets[1].data.push(pwm);

    if (liveChart.data.labels.length > 100) {
        liveChart.data.labels.shift();
        liveChart.data.datasets[0].data.shift();
        liveChart.data.datasets[1].data.shift();
    }

    liveChart.update();
}

function updateLiveTable(temperatures) {
    const container = document.getElementById('live-temperature-table');
    if (!temperatures || temperatures.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Žiadne dáta na zobrazenie</div>';
        return;
    }
    container.innerHTML = buildTable(temperatures);
}

function updateLiveGauge(temperatures) {
    const container = document.getElementById('live-gauges-container');
    if (!temperatures || temperatures.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Žiadne dáta na zobrazenie</div>';
        return;
    }

    const lastTen = temperatures.slice(-10);

    const tempValues = lastTen.map(t => t.value).filter(v => v !== undefined && v !== null);
    const avgTemp = tempValues.length > 0 ? (tempValues.reduce((a, b) => a + b, 0) / tempValues.length).toFixed(1) : '0.0';

    const pwmValues = lastTen.map(t => t.pwm).filter(v => v !== undefined && v !== null);
    const avgPwm = pwmValues.length > 0 ? (pwmValues.reduce((a, b) => a + b, 0) / pwmValues.length).toFixed(0) : '0';

    container.innerHTML = `
        <div class="gauge-grid">
            <div class="gauge-card">
                <h3>Priemerná teplota (posledných 10)</h3>
                <div class="gauge-value-large">${avgTemp}°C</div>
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: ${(avgTemp / 50) * 100}%; background: linear-gradient(90deg, #2196f3, #4caf50);"></div>
                </div>
            </div>
            <div class="gauge-card">
                <h3>Priemerný PWM výkon (posledných 10)</h3>
                <div class="gauge-value-large">${avgPwm}%</div>
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: ${avgPwm}%; background: linear-gradient(90deg, #ff9800, #f44336);"></div>
                </div>
            </div>
        </div>
    `;
}
// ============ HISTORICKÁ VIZUALIZÁCIA ============

function switchHistoryView(view, event) {
    currentHistoryView = view;

    document.querySelectorAll('#history-chart-view, #history-table-view').forEach(el => el.style.display = 'none');

    const historyCard = document.getElementById('history-chart-view').closest('.card');
    historyCard.querySelectorAll('.view-btn').forEach(btn => btn.classList.remove('active'));
    event.target.classList.add('active');

    document.getElementById(`history-${view}-view`).style.display = 'block';

    if (historyTemperatures.length > 0) {
        updateHistoryVisualization(historyTemperatures);
    }
}

function updateHistoryVisualization(temperatures) {
    switch (currentHistoryView) {
        case 'chart': updateHistoryChart(temperatures); break;
        case 'table': updateHistoryTable(temperatures); break;
    }
}

function updateHistoryChart(temperatures) {
    const ctx = document.getElementById('temperature-chart').getContext('2d');
    const labels = temperatures.map(t => new Date(t.timestamp).toLocaleString());
    const tempValues = temperatures.map(t => t.value);
    const pwmValues = temperatures.map(t => t.pwm);

    if (historyChart) {
        historyChart.data.labels = labels;
        historyChart.data.datasets[0].data = tempValues;
        historyChart.data.datasets[1].data = pwmValues;
        historyChart.update();
    } else {
        historyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Teplota (°C)',
                        data: tempValues,
                        borderColor: 'rgb(75, 192, 192)',
                        backgroundColor: 'rgba(75, 192, 192, 0.1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        tension: 0.3,
                        fill: true,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Peltier PWM (%)',
                        data: pwmValues,
                        borderColor: 'rgb(255, 99, 132)',
                        backgroundColor: 'rgba(255, 99, 132, 0.1)',
                        borderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        tension: 0.3,
                        fill: false,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: chartOptions()
        });
    }
}

function updateHistoryTable(temperatures) {
    const container = document.getElementById('temperature-table');
    if (!temperatures || temperatures.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Žiadne dáta na zobrazenie</div>';
        return;
    }
    container.innerHTML = buildTable(temperatures);
}

function updateHistoryGauge(temperatures) {
    const container = document.getElementById('gauges-container');
    container.innerHTML = buildGauge(temperatures);
}

// ============ NAČÍTANIE HISTORICKÝCH DÁT ============

async function loadDataForPeriod(period) {
    let fromTime, toTime;
    const now = new Date();

    switch (period) {
        case 'hour':
            fromTime = new Date(now.getTime() - 60 * 60 * 1000);
            toTime = now;
            break;
        case 'day':
            fromTime = new Date(now.getTime() - 24 * 60 * 60 * 1000);
            toTime = now;
            break;
        case 'week':
            fromTime = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
            toTime = now;
            break;
        case 'month':
            fromTime = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
            toTime = now;
            break;
        case 'custom':
            fromTime = new Date(document.getElementById('custom-from').value);
            toTime = new Date(document.getElementById('custom-to').value);
            if (isNaN(fromTime)) {
                showNotification('Zadajte platný dátum začiatku', 'error');
                return;
            }
            if (isNaN(toTime)) toTime = now;
            break;
    }

    // Konverzia na Unix timestamp s offsetom — interpretujeme lokálny čas ako keby bol UTC
    const toLocalTs = (d) => Math.floor((d.getTime() - d.getTimezoneOffset() * 60000) / 1000);
    const startTs = toLocalTs(fromTime);
    const endTs = toLocalTs(toTime);

    try {
        const response = await fetch(`${API}/api/archive/${startTs}/${endTs}`);
        const data = await response.json();

        if (response.ok) {
            historyTemperatures = data.temperatures;

            const pwmValues = data.temperatures.map(t => t.pwm).filter(v => v !== undefined && v !== null);
            const localStats = {
                ...data.stats,
                pwm_avg: pwmValues.length > 0 ? (pwmValues.reduce((a, b) => a + b, 0) / pwmValues.length).toFixed(0) : '-',
                pwm_min: pwmValues.length > 0 ? Math.min(...pwmValues) : '-',
                pwm_max: pwmValues.length > 0 ? Math.max(...pwmValues) : '-'
            };

            updateHistoryVisualization(data.temperatures);
            updateStatistics(localStats);

            const periodText = {
                'hour': 'hodinu', 'day': '24 hodín',
                'week': 'týždeň', 'month': 'mesiac', 'custom': 'vybrané obdobie'
            };
            showNotification(`Načítaných ${data.temperatures.length} meraní za posledn${period === 'hour' ? 'ú' : 'ých'} ${periodText[period]}`, 'success');
        } else {
            showNotification(`Chyba: ${data.error}`, 'error');
        }
    } catch (err) {
        showNotification(`Chyba: ${err.message}`, 'error');
    }
}

// ============ ZDIEĽANÉ POMOCNÉ FUNKCIE ============

function chartOptions() {
    return {
        responsive: true,
        maintainAspectRatio: true,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
            legend: { display: true, position: 'top' }
        },
        scales: {
            y: {
                type: 'linear',
                display: true,
                position: 'left',
                title: { display: true, text: 'Teplota (°C)' },
                min: 0, max: 50,
                grid: { color: 'rgba(0, 0, 0, 0.05)' }
            },
            y1: {
                type: 'linear',
                display: true,
                position: 'right',
                title: { display: true, text: 'Peltier PWM (%)' },
                min: 0, max: 100,
                grid: { drawOnChartArea: false }
            },
            x: {
                title: { display: true, text: 'Čas' },
                ticks: { maxRotation: 45, minRotation: 45 }
            }
        }
    };
}

function buildTable(temperatures) {
    return `
        <table class="data-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Teplota (°C)</th>
                    <th>Peltier PWM (%)</th>
                    <th>Čas merania</th>
                </tr>
            </thead>
            <tbody>
                ${temperatures.slice().reverse().map((t, index) => `
                    <tr>
                        <td>${temperatures.length - index}</td>
                        <td><strong>${t.value}</strong></td>
                        <td>${t.pwm !== undefined && t.pwm !== null ? t.pwm : '-'} %</td>
                        <td>${new Date(t.timestamp).toLocaleString()}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function buildGauge(temperatures) {
    if (!temperatures || temperatures.length === 0) {
        return '<div class="alert alert-info">Žiadne dáta na zobrazenie</div>';
    }
    const values = temperatures.map(t => t.value);
    const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
    const min = Math.min(...values).toFixed(1);
    const max = Math.max(...values).toFixed(1);
    const latest = values[values.length - 1];

    return `
        <div class="gauge-grid">
            <div class="gauge-card">
                <h3>Aktuálna teplota</h3>
                <div class="gauge-value-large">${latest}°C</div>
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: ${(latest / 50) * 100}%; background: linear-gradient(90deg, #4caf50, #ff9800);"></div>
                </div>
            </div>
            <div class="gauge-card">
                <h3>Priemerná teplota</h3>
                <div class="gauge-value-large">${avg}°C</div>
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: ${(avg / 50) * 100}%; background: linear-gradient(90deg, #2196f3, #9c27b0);"></div>
                </div>
            </div>
            <div class="gauge-card">
                <h3>Minimálna teplota</h3>
                <div class="gauge-value">${min}°C</div>
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: ${(min / 50) * 100}%; background: #4caf50;"></div>
                </div>
            </div>
            <div class="gauge-card">
                <h3>Maximálna teplota</h3>
                <div class="gauge-value">${max}°C</div>
                <div class="gauge-bar">
                    <div class="gauge-fill" style="width: ${(max / 50) * 100}%; background: #f44336;"></div>
                </div>
            </div>
        </div>
    `;
}

function updateStatistics(stats) {
    const container = document.getElementById('statistics');
    if (!stats || !stats.count) { container.innerHTML = ''; return; }

    container.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-label">Počet meraní</div>
                <div class="stat-value">${stats.count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📈</div>
                <div class="stat-label">Priemerná teplota</div>
                <div class="stat-value">${stats.avg} °C</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📉</div>
                <div class="stat-label">Minimálna teplota</div>
                <div class="stat-value">${stats.min} °C</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📈</div>
                <div class="stat-label">Maximálna teplota</div>
                <div class="stat-value">${stats.max} °C</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-label">Priemerné PWM</div>
                <div class="stat-value">${stats.pwm_avg !== undefined ? stats.pwm_avg : '-'} %</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⚡</div>
                <div class="stat-label">Rozsah PWM</div>
                <div class="stat-value">${stats.pwm_min !== undefined ? stats.pwm_min : '-'}% - ${stats.pwm_max !== undefined ? stats.pwm_max : '-'}%</div>
            </div>
        </div>
    `;
}

// ============ STAV ZARIADENIA ============

async function loadDeviceStatus() {
    try {
        const response = await fetch(`${API}/api/device/status`);
        const data = await response.json();
        updateDeviceUI(data.status, data.connected, data.debug_mode);
    } catch (err) {
        console.error('Error loading device status:', err);
    }
}

function updateDeviceUI(status, connected, debugMode = false) {
    const connectionSpan = document.getElementById('connection-status');
    const systemSpan = document.getElementById('system-status');
    const btnPowerOn = document.getElementById('btn-power-on');
    const btnPowerOff = document.getElementById('btn-power-off');
    const debugPanel = document.getElementById('debug-control-panel');

    if (debugPanel) {
        debugPanel.style.display = debugMode ? 'block' : 'none';
    }

    if (connected) {
        connectionSpan.innerHTML = 'Pripojené';
        connectionSpan.className = 'status-badge status-connected';
        if (status === 'on') {
            systemSpan.innerHTML = 'ZAPNUTÝ';
            systemSpan.className = 'status-badge status-on';
            btnPowerOn.disabled = true;
            btnPowerOff.disabled = false;
        } else {
            systemSpan.innerHTML = 'VYPNUTÝ';
            systemSpan.className = 'status-badge status-off';
            btnPowerOn.disabled = false;
            btnPowerOff.disabled = true;
        }
    } else {
        connectionSpan.innerHTML = 'Nepripojené';
        connectionSpan.className = 'status-badge status-disconnected';
        systemSpan.innerHTML = 'VYPNUTÝ';
        systemSpan.className = 'status-badge status-off';
        btnPowerOn.disabled = true;
        btnPowerOff.disabled = true;
    }
}

function updateLiveDisplay(temperature, timestamp) {
    document.getElementById('last-temp').innerHTML = `${temperature}`;
    document.getElementById('last-time').innerHTML = new Date(timestamp).toLocaleTimeString();

    const tempElement = document.getElementById('last-temp');
    tempElement.style.transform = 'scale(1.1)';
    setTimeout(() => { tempElement.style.transform = 'scale(1)'; }, 200);
}

function showNotification(message, type) {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <span class="notification-icon">${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
        <span>${message}</span>
    `;
    document.body.appendChild(notification);
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// ============ INICIALIZÁCIA ============

document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    const hourAgo = new Date(now.getTime() - 60 * 60 * 1000);
    document.getElementById('custom-from').value = hourAgo.toISOString().slice(0, 16);
    document.getElementById('custom-to').value = now.toISOString().slice(0, 16);
});