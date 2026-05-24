const API = window.location.origin;
const socket = io(API);

let monitoringActive = false;
let temperatureChart = null;
let currentView = 'chart';
let currentTemperatures = [];
let pollingInterval = null;

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
    } else {
        monitoringActive = false;
        document.getElementById('btn-start-monitor').disabled = false;
        document.getElementById('btn-stop-monitor').disabled = true;
    }
});

socket.on('live_temperature', (data) => {
    if (monitoringActive) {
        currentTemperatures.push(data);
        updateLiveDisplay(data.value, data.timestamp);

        if (currentView === 'chart') {
            addDataToChart(data.value, data.timestamp);
        } else {
            updateVisualization(currentTemperatures);
        }
    }
});

// ============ ZAPNUTIE/VYPNUTIE SYSTÉMU ============

async function controlSystem(command) {
    try {
        const response = await fetch(`${API}/api/device/control`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ command: command })
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

// ============ ZAČAŤ SLEDOVANIE ============

async function startMonitoring() {
    try {
        socket.emit('join_monitoring');
        showNotification('Monitorovanie spustené - načítavam doterajšie dáta z relácie', 'success');
        updateVisualization(currentTemperatures);
    } catch (err) {
        console.error('Chyba pri načítaní úvodných dát relácie:', err);
    }
}
// ============ ZASTAVIŤ SLEDOVANIE ============

function stopMonitoring() {
    if (!monitoringActive) return;
    socket.emit('leave_monitoring');
    showNotification('Monitorovanie zastavené', 'info');
}

// ============ NAČÍTANIE DÁT PODĽA ČASU ============

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
            if (isNaN(toTime)) {
                toTime = now;
            }
            break;
    }

    const requestBody = {
        from_time: fromTime.toISOString()
    };

    if (toTime && !isNaN(toTime)) {
        requestBody.to_time = toTime.toISOString();
    }

    try {
        const response = await fetch(`${API}/api/temperatures/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });

        const data = await response.json();

        if (response.ok) {
            currentTemperatures = data.temperatures;
            updateVisualization(data.temperatures);
            updateStatistics(data.stats);

            const periodText = {
                'hour': 'hodinu',
                'day': '24 hodín',
                'week': 'týždeň',
                'month': 'mesiac',
                'custom': 'vybrané obdobie'
            };

            showNotification(`Načítaných ${data.temperatures.length} meraní za posledných ${periodText[period]}`, 'success');
        } else {
            showNotification(`Chyba: ${data.error}`, 'error');
        }
    } catch (err) {
        showNotification(`Chyba: ${err.message}`, 'error');
    }
}

// ============ VIZUALIZÁCIA DÁT ============

function updateVisualization(temperatures) {
    switch (currentView) {
        case 'chart':
            updateChart(temperatures);
            break;
        case 'table':
            updateTable(temperatures);
            break;
        case 'gauge':
            updateGauge(temperatures);
            break;
    }
}

function updateChart(temperatures) {
    const ctx = document.getElementById('temperature-chart').getContext('2d');
    const labels = temperatures.map(t => new Date(t.timestamp).toLocaleString());
    const values = temperatures.map(t => t.value);

    if (temperatureChart) {
        temperatureChart.data.labels = labels;
        temperatureChart.data.datasets[0].data = values;
        temperatureChart.update();
    } else {
        temperatureChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Teplota (°C)',
                    data: values,
                    borderColor: 'rgb(75, 192, 192)',
                    backgroundColor: 'rgba(75, 192, 192, 0.1)',
                    borderWidth: 2,
                    pointRadius: 3,
                    pointHoverRadius: 5,
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                interaction: {
                    intersect: false,
                    mode: 'index'
                },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top'
                    },
                    tooltip: {
                        callbacks: {
                            label: function (context) {
                                return `${context.parsed.y} °C`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        title: {
                            display: true,
                            text: 'Teplota (°C)'
                        },
                        min: 0,
                        max: 50,
                        grid: {
                            color: 'rgba(0, 0, 0, 0.05)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Čas'
                        },
                        ticks: {
                            maxRotation: 45,
                            minRotation: 45
                        }
                    }
                }
            }
        });
    }
}

function addDataToChart(temperature, timestamp) {
    if (!temperatureChart || currentView !== 'chart') return;

    const newLabel = new Date(timestamp).toLocaleString();
    temperatureChart.data.labels.push(newLabel);
    temperatureChart.data.datasets[0].data.push(temperature);

    if (temperatureChart.data.labels.length > 100) {
        temperatureChart.data.labels.shift();
        temperatureChart.data.datasets[0].data.shift();
    }

    temperatureChart.update();
}

function updateTable(temperatures) {
    const container = document.getElementById('temperature-table');

    if (!temperatures || temperatures.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Žiadne dáta na zobrazenie</div>';
        return;
    }

    const table = `
        <table class="data-table">
            <thead>
                <tr>
                    <th>#</th>
                    <th>Teplota (°C)</th>
                    <th>Čas merania</th>
                </tr>
            </thead>
            <tbody>
                ${temperatures.slice().reverse().map((t, index) => `
                    <tr>
                        <td>${temperatures.length - index}</td>
                        <td><strong>${t.value}</strong></td>
                        <td>${new Date(t.timestamp).toLocaleString()}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;

    container.innerHTML = table;
}

function updateGauge(temperatures) {
    const container = document.getElementById('gauges-container');

    if (!temperatures || temperatures.length === 0) {
        container.innerHTML = '<div class="alert alert-info">Žiadne dáta na zobrazenie</div>';
        return;
    }

    const values = temperatures.map(t => t.value);
    const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(1);
    const min = Math.min(...values).toFixed(1);
    const max = Math.max(...values).toFixed(1);
    const latest = values[values.length - 1];

    container.innerHTML = `
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

    if (!stats || !stats.count) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-icon">📊</div>
                <div class="stat-label">Počet meraní</div>
                <div class="stat-value">${stats.count}</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📈</div>
                <div class="stat-label">Priemer</div>
                <div class="stat-value">${stats.avg} °C</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📉</div>
                <div class="stat-label">Minimum</div>
                <div class="stat-value">${stats.min} °C</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">📈</div>
                <div class="stat-label">Maximum</div>
                <div class="stat-value">${stats.max} °C</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">🔄</div>
                <div class="stat-label">Prvá hodnota</div>
                <div class="stat-value">${stats.first} °C</div>
            </div>
            <div class="stat-card">
                <div class="stat-icon">⚡</div>
                <div class="stat-label">Posledná</div>
                <div class="stat-value">${stats.last} °C</div>
            </div>
        </div>
    `;
}

function switchView(view) {
    currentView = view;

    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    event.target.classList.add('active');

    document.getElementById('chart-view').style.display = 'none';
    document.getElementById('table-view').style.display = 'none';
    document.getElementById('gauge-view').style.display = 'none';

    document.getElementById(`${view}-view`).style.display = 'block';

    if (currentTemperatures.length > 0) {
        updateVisualization(currentTemperatures);
    }
}

async function loadDeviceStatus() {
    try {
        const response = await fetch(`${API}/api/device/status`);
        const data = await response.json();
        updateDeviceUI(data.status, data.connected);
    } catch (err) {
        console.error('Error loading device status:', err);
    }
}

function updateDeviceUI(status, connected) {
    const connectionSpan = document.getElementById('connection-status');
    const systemSpan = document.getElementById('system-status');
    const btnPowerOn = document.getElementById('btn-power-on');
    const btnPowerOff = document.getElementById('btn-power-off');

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
    document.getElementById('last-temp').innerHTML = `${temperature} °C`;
    document.getElementById('last-time').innerHTML = new Date(timestamp).toLocaleTimeString();

    const tempElement = document.getElementById('last-temp');
    tempElement.style.transform = 'scale(1.1)';
    setTimeout(() => {
        tempElement.style.transform = 'scale(1)';
    }, 200);
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

document.addEventListener('DOMContentLoaded', () => {
    const now = new Date();
    const hourAgo = new Date(now.getTime() - 60 * 60 * 1000);

    document.getElementById('custom-from').value = hourAgo.toISOString().slice(0, 16);
    document.getElementById('custom-to').value = now.toISOString().slice(0, 16);

    setTimeout(() => {
        loadDataForPeriod('hour');
    }, 500);
});