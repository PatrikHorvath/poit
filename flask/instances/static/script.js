const API = 'http://127.0.0.1:5000';

//
//  Záznam (session)
//

let recording    = false;
let sessionData  = [];      // pole { timestamp, value }
let startTime    = null;    // ISO string
let intervalId   = null;    // setInterval pre generovanie teplôt
let timerIntervalId = null; // setInterval pre odpočet

// Generuje náhodné číslo medzi min a max zaokrúhlené na 1 des. miesto
function randTemp(min = 10, max = 40) {
  return Math.round((Math.random() * (max - min) + min) * 10) / 10;
}

function nowString() {
  return new Date().toISOString().replace('T', ' ').substring(0, 19);
}

function startRecording() {
  if (recording) return;
  recording   = true;
  sessionData = [];
  startTime   = nowString();

  document.getElementById('btn-start').disabled = true;
  document.getElementById('btn-stop').disabled  = false;
  document.getElementById('live-box').classList.remove('hidden');
  document.getElementById('rec-timer').classList.remove('hidden');
  document.getElementById('session-result').textContent = '';

  let elapsed = 0;
  timerIntervalId = setInterval(() => {
    elapsed++;
    document.getElementById('rec-timer').textContent = `${elapsed} s`;
  }, 1000);

  // Každú sekundu pridaj nové meranie
  intervalId = setInterval(() => {
    const entry = { timestamp: nowString(), value: randTemp() };
    sessionData.push(entry);
    updateLiveUI(entry);
  }, 1000);
}

function updateLiveUI(entry) {
  document.getElementById('live-count').textContent = sessionData.length;
  document.getElementById('live-last').textContent  = `${entry.value} °C`;

  // Mini bar chart – ukazuje posledných 60 hodnôt
  const barsEl = document.getElementById('live-bars');
  const visible = sessionData.slice(-60);
  const minV = Math.min(...visible.map(e => e.value));
  const maxV = Math.max(...visible.map(e => e.value));
  const range = maxV - minV || 1;

  barsEl.innerHTML = visible.map(e => {
    const pct = ((e.value - minV) / range) * 52 + 8; // 8–60 px
    return `<div class="live-bar" style="height:${pct}px" title="${e.value} °C"></div>`;
  }).join('');

  // auto-scroll bar chart doprava
  barsEl.parentElement.scrollLeft = barsEl.scrollWidth;
}

async function stopRecording() {
  if (!recording) return;
  recording = false;

  clearInterval(intervalId);
  clearInterval(timerIntervalId);

  document.getElementById('btn-start').disabled = false;
  document.getElementById('btn-stop').disabled  = true;
  document.getElementById('live-box').classList.add('hidden');
  document.getElementById('rec-timer').classList.add('hidden');

  const resultEl = document.getElementById('session-result');

  if (sessionData.length === 0) {
    resultEl.textContent = 'Žiadne dáta na uloženie.';
    resultEl.className   = 'result err';
    return;
  }

  resultEl.textContent = 'Ukladám do databázy…';
  resultEl.className   = 'result';

  try {
    const res  = await fetch(`${API}/dbdata/session`, {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ temperatures: sessionData, start_time: startTime }),
    });
    const data = await res.json();

    if (res.ok) {
      resultEl.textContent = `Záznam uložený! ID: ${data.id} | Meraní: ${sessionData.length}`;
      resultEl.className   = 'result ok';
      loadSessions(); // obnov zoznam
    } else {
      resultEl.textContent = `Chyba: ${data.error}`;
      resultEl.className   = 'result err';
    }
  } catch (err) {
    resultEl.textContent = `Sieťová chyba: ${err.message}`;
    resultEl.className   = 'result err';
  }
}


//
//  Zoznam sessions
//

async function loadSessions() {
  const el = document.getElementById('sessions-list');
  el.innerHTML = '<p style="color:var(--muted);font-size:.88rem">Načítavam…</p>';

  try {
    const res  = await fetch(`${API}/dbdata/session`);
    const data = await res.json();

    if (!res.ok) { el.innerHTML = `<p class="result err">❌ ${data.error}</p>`; return; }
    if (!data.sessions.length) { el.innerHTML = '<p class="result">Žiadne záznamy.</p>'; return; }

    el.innerHTML = data.sessions.map(s => `
      <div class="session-row">
        <span class="session-id">#${s.id}</span>
        <span>${s.start_time}</span>
        <span class="session-meta">${s.count} meraní</span>
        <button class="btn-small" onclick="showDetail(${s.id})">Detail →</button>
      </div>`).join('');
  } catch (err) {
    el.innerHTML = `<p class="result err">${err.message}</p>`;
  }
}

function showDetail(id) {
  document.getElementById('inp-session-id').value = id;
  loadSession();
  document.getElementById('session-detail').scrollIntoView({ behavior: 'smooth' });
}


//
//  Detail záznamu podľa ID
//

async function loadSession() {
  const id  = parseInt(document.getElementById('inp-session-id').value);
  const el  = document.getElementById('session-detail');

  if (!id || id < 1) {
    el.innerHTML = '<p class="result err">Zadaj platné ID.</p>';
    return;
  }

  el.innerHTML = '<p style="color:var(--muted);font-size:.88rem">Načítavam…</p>';

  try {
    const res  = await fetch(`${API}/dbdata/session/${id}`);
    const data = await res.json();

    if (!res.ok) { el.innerHTML = `<p class="result err">${data.error}</p>`; return; }

    const temps = data.temperatures;
    const vals  = temps.map(t => t.value);
    const avg   = (vals.reduce((a, b) => a + b, 0) / vals.length).toFixed(1);
    const minV  = Math.min(...vals).toFixed(1);
    const maxV  = Math.max(...vals).toFixed(1);

    const rows = temps.map((t, i) => `
      <tr>
        <td>${i + 1}</td>
        <td><strong>${t.value}</strong> °C</td>
        <td>${t.timestamp}</td>
      </tr>`).join('');

    el.innerHTML = `
      <div class="detail-header">
        <div>Záznam <strong>#${data.id}</strong></div>
        <div>Začiatok: <strong>${data.start_time}</strong></div>
        <div>Meraní: <strong>${temps.length}</strong></div>
        <div>Min: <strong>${minV} °C</strong></div>
        <div>Max: <strong>${maxV} °C</strong></div>
        <div>Priemer: <strong>${avg} °C</strong></div>
      </div>
      <table>
        <thead><tr><th>#</th><th>Teplota</th><th>Timestamp</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>`;
  } catch (err) {
    el.innerHTML = `<p class="result err">${err.message}</p>`;
  }
}


// Načítaj sessions pri štarte stránky
loadSessions();