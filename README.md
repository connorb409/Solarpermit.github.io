<!DOCTYPE html>

<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Charlotte County Solar Permits</title>

<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,700&family=JetBrains+Mono:wght@400;500&family=Inter+Tight:wght@400;500;600&display=swap" rel="stylesheet" />

<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
<link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />

<style>
  :root {
    --bg: #0f1419;
    --panel: #161c24;
    --panel-2: #1c232d;
    --border: #2a3340;
    --text: #e8eef5;
    --text-dim: #8a96a8;
    --accent: #f5b042;          /* solar amber */
    --accent-warm: #f57c00;
    --accent-cool: #4ec9b0;

    /* Status palette — distinct hues, all readable on dark */
    --status-issued: #4ec9b0;        /* teal-green */
    --status-review: #f5b042;        /* amber */
    --status-submitted: #6aa9ff;     /* blue */
    --status-pending: #c586c0;       /* purple */
    --status-finaled: #50c878;       /* emerald */
    --status-void: #888;             /* gray */
    --status-expired: #d9534f;       /* red */
    --status-hold: #ff8c42;          /* orange */
    --status-other: #b8a7ff;         /* lavender */
  }

  * { box-sizing: border-box; }

  html, body {
    margin: 0; padding: 0; height: 100%; width: 100%;
    background: var(--bg);
    color: var(--text);
    font-family: "Inter Tight", system-ui, sans-serif;
    overflow: hidden;
  }

  .app {
    display: grid;
    grid-template-columns: 380px 1fr;
    grid-template-rows: 64px 1fr;
    grid-template-areas:
      "header header"
      "sidebar map";
    height: 100vh;
  }

  /* ── HEADER ────────────────────────────────────────────── */
  header {
    grid-area: header;
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 0 24px;
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    position: relative;
  }
  header::before {
    content: "";
    position: absolute; left: 0; right: 0; bottom: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent) 30%, var(--accent-warm) 70%, transparent);
    opacity: .4;
  }
  .logo {
    width: 36px; height: 36px;
    border-radius: 8px;
    background: radial-gradient(circle at 30% 30%, #ffd166, var(--accent-warm) 60%, #b34700);
    box-shadow: 0 0 24px rgba(245, 176, 66, .35), inset 0 0 12px rgba(255, 209, 102, .4);
    flex-shrink: 0;
  }
  h1 {
    font-family: "Fraunces", serif;
    font-weight: 700;
    font-size: 20px;
    letter-spacing: -0.01em;
    margin: 0;
  }
  h1 .accent { color: var(--accent); font-style: italic; }
  .meta {
    margin-left: auto;
    font-family: "JetBrains Mono", monospace;
    font-size: 11px;
    color: var(--text-dim);
    text-align: right;
    line-height: 1.4;
  }
  .meta strong { color: var(--text); font-weight: 500; }

  /* ── SIDEBAR ───────────────────────────────────────────── */
  aside {
    grid-area: sidebar;
    background: var(--panel);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .controls {
    padding: 16px 20px;
    border-bottom: 1px solid var(--border);
    display: flex; flex-direction: column; gap: 12px;
  }
  .controls label {
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-dim);
    font-weight: 500;
  }
  .controls input[type="search"] {
    width: 100%;
    padding: 9px 12px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font: inherit;
    font-size: 13px;
  }
  .controls input[type="search"]:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(245, 176, 66, .15);
  }

  .status-filter {
    display: flex; flex-wrap: wrap; gap: 6px;
  }
  .chip {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 10px;
    background: var(--panel-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    font-size: 11px;
    cursor: pointer;
    user-select: none;
    transition: all .15s ease;
  }
  .chip:hover { border-color: var(--text-dim); }
  .chip.active {
    background: rgba(245, 176, 66, .12);
    border-color: var(--accent);
    color: #fff;
  }
  .chip .dot {
    width: 8px; height: 8px; border-radius: 50%;
    box-shadow: 0 0 6px currentColor;
  }
  .chip .count {
    font-family: "JetBrains Mono", monospace;
    color: var(--text-dim);
    font-size: 10px;
  }

  .list-header {
    padding: 12px 20px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-dim);
    border-bottom: 1px solid var(--border);
    display: flex; justify-content: space-between; align-items: center;
  }
  .list-header .total {
    font-family: "JetBrains Mono", monospace;
    color: var(--accent);
  }

  .permit-list {
    flex: 1;
    overflow-y: auto;
    scrollbar-width: thin;
    scrollbar-color: var(--border) transparent;
  }
  .permit-list::-webkit-scrollbar { width: 6px; }
  .permit-list::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  .permit-item {
    padding: 14px 20px;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    transition: background .12s ease;
    border-left: 3px solid transparent;
  }
  .permit-item:hover { background: var(--panel-2); }
  .permit-item.active {
    background: rgba(245, 176, 66, .08);
    border-left-color: var(--accent);
  }
  .permit-item .top {
    display: flex; justify-content: space-between; align-items: baseline;
    gap: 8px; margin-bottom: 4px;
  }
  .permit-item .record {
    font-family: "JetBrains Mono", monospace;
    font-size: 12px;
    color: var(--text);
    font-weight: 500;
  }
  .permit-item .date {
    font-family: "JetBrains Mono", monospace;
    font-size: 10px;
    color: var(--text-dim);
  }
  .permit-item .address {
    font-size: 13px;
    color: var(--text);
    margin-bottom: 6px;
    line-height: 1.3;
  }
  .permit-item .status-row {
    display: flex; align-items: center; gap: 6px;
    font-size: 11px;
  }
  .status-badge {
    display: inline-flex; align-items: center; gap: 5px;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 10px;
    font-weight: 500;
    background: rgba(255,255,255,.04);
  }
  .status-badge .dot {
    width: 6px; height: 6px; border-radius: 50%;
    box-shadow: 0 0 4px currentColor;
  }
  .no-coords {
    font-size: 9px;
    color: var(--text-dim);
    font-family: "JetBrains Mono", monospace;
  }

  /* ── MAP ───────────────────────────────────────────────── */
  #map {
    grid-area: map;
    background: #1a1f26;
  }
  /* Dark Leaflet attribution */
  .leaflet-container { background: #1a1f26; font-family: inherit; }
  .leaflet-popup-content-wrapper {
    background: var(--panel);
    color: var(--text);
    border-radius: 8px;
    border: 1px solid var(--border);
  }
  .leaflet-popup-tip { background: var(--panel); }
  .leaflet-popup-content { margin: 12px 14px; font-size: 13px; line-height: 1.5; }
  .leaflet-popup-content .pop-record {
    font-family: "JetBrains Mono", monospace;
    font-weight: 500;
    margin-bottom: 4px;
  }
  .leaflet-popup-content .pop-address { font-weight: 500; margin-bottom: 6px; }
  .leaflet-popup-content .pop-meta {
    font-size: 11px; color: var(--text-dim);
    font-family: "JetBrains Mono", monospace;
  }
  .leaflet-popup-content a {
    color: var(--accent);
    font-size: 11px;
    text-decoration: none;
    display: inline-block;
    margin-top: 6px;
  }
  .leaflet-popup-content a:hover { text-decoration: underline; }

  /* Empty state */
  .empty {
    display: flex; align-items: center; justify-content: center;
    height: 100%;
    flex-direction: column;
    padding: 40px;
    text-align: center;
    color: var(--text-dim);
  }
  .empty h2 {
    font-family: "Fraunces", serif;
    color: var(--text);
    font-weight: 500;
    font-size: 18px;
    margin: 0 0 8px;
  }
  .empty p { font-size: 13px; line-height: 1.5; max-width: 280px; margin: 0 0 16px; }
  .empty .upload-btn {
    background: var(--accent);
    color: #1a1208;
    padding: 8px 16px;
    border-radius: 6px;
    border: none;
    cursor: pointer;
    font: inherit;
    font-weight: 500;
    font-size: 12px;
  }
  .empty .upload-btn:hover { background: #ffc870; }

  /* Custom marker dot */
  .marker-dot {
    width: 18px; height: 18px;
    border-radius: 50%;
    border: 2px solid #fff;
    box-shadow: 0 0 0 1px rgba(0,0,0,.5), 0 0 8px currentColor;
  }

  @media (max-width: 800px) {
    .app {
      grid-template-columns: 1fr;
      grid-template-rows: 56px 40vh 1fr;
      grid-template-areas: "header" "map" "sidebar";
    }
    aside { border-right: none; border-top: 1px solid var(--border); }
    .meta { display: none; }
  }
</style>

</head>
<body>

<div class="app">
  <header>
    <div class="logo" aria-hidden="true"></div>
    <h1>Charlotte County <span class="accent">Solar</span> Permits</h1>
    <div class="meta">
      <div>Last refresh: <strong id="last-refresh">—</strong></div>
      <div>Source: <strong>BOCC Accela Citizen Access</strong></div>
    </div>
  </header>

  <aside>
    <div class="controls">
      <div>
        <label for="search-input">Search</label>
        <input id="search-input" type="search" placeholder="Address, record #, contractor…" />
      </div>
      <div>
        <label>Filter by status</label>
        <div id="status-filter" class="status-filter"></div>
      </div>
    </div>
    <div class="list-header">
      <span>Permits</span>
      <span class="total" id="visible-count">0</span>
    </div>
    <div id="permit-list" class="permit-list"></div>
  </aside>

  <div id="map"></div>
</div>

<input type="file" id="file-input" accept="application/json" style="display:none" />

<script>
// ────────────────────────────────────────────────────────────
// Status → color mapping
// ────────────────────────────────────────────────────────────
const STATUS_COLORS = {
  issued:    getComputedStyle(document.documentElement).getPropertyValue('--status-issued').trim(),
  review:    getComputedStyle(document.documentElement).getPropertyValue('--status-review').trim(),
  submitted: getComputedStyle(document.documentElement).getPropertyValue('--status-submitted').trim(),
  pending:   getComputedStyle(document.documentElement).getPropertyValue('--status-pending').trim(),
  finaled:   getComputedStyle(document.documentElement).getPropertyValue('--status-finaled').trim(),
  void:      getComputedStyle(document.documentElement).getPropertyValue('--status-void').trim(),
  expired:   getComputedStyle(document.documentElement).getPropertyValue('--status-expired').trim(),
  hold:      getComputedStyle(document.documentElement).getPropertyValue('--status-hold').trim(),
  other:     getComputedStyle(document.documentElement).getPropertyValue('--status-other').trim(),
};

function statusKey(rawStatus) {
  const s = (rawStatus || '').toLowerCase();
  if (!s) return 'other';
  if (s.includes('finaled') || s.includes('closed') || s.includes('complete')) return 'finaled';
  if (s.includes('issued') || s.includes('approved')) return 'issued';
  if (s.includes('review') || s.includes('plan check')) return 'review';
  if (s.includes('submitted') || s.includes('intake') || s.includes('received')) return 'submitted';
  if (s.includes('pending') || s.includes('incomplete') || s.includes('in process')) return 'pending';
  if (s.includes('void') || s.includes('withdraw') || s.includes('cancel')) return 'void';
  if (s.includes('expired')) return 'expired';
  if (s.includes('hold')) return 'hold';
  return 'other';
}

const STATUS_LABELS = {
  issued: 'Issued',
  review: 'In Review',
  submitted: 'Submitted',
  pending: 'Pending',
  finaled: 'Finaled / Closed',
  void: 'Void / Withdrawn',
  expired: 'Expired',
  hold: 'On Hold',
  other: 'Other / Unknown',
};

// ────────────────────────────────────────────────────────────
// State
// ────────────────────────────────────────────────────────────
let allPermits = [];
let activeStatuses = new Set(); // empty = all
let searchQuery = '';
let map, markerLayer;
const markerById = new Map();

// ────────────────────────────────────────────────────────────
// Map setup — Charlotte County, FL is centered around Punta Gorda.
// ────────────────────────────────────────────────────────────
function initMap() {
  map = L.map('map', { zoomControl: true }).setView([26.95, -82.05], 11);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '© OpenStreetMap contributors © CARTO',
    subdomains: 'abcd',
    maxZoom: 19,
  }).addTo(map);

  markerLayer = L.markerClusterGroup({
    showCoverageOnHover: false,
    maxClusterRadius: 40,
  });
  map.addLayer(markerLayer);
}

function makeMarker(permit) {
  const key = statusKey(permit.status);
  const color = STATUS_COLORS[key];
  const icon = L.divIcon({
    className: '',
    html: `<div class="marker-dot" style="background:${color}; color:${color};"></div>`,
    iconSize: [18, 18],
    iconAnchor: [9, 9],
  });
  const marker = L.marker([permit.lat, permit.lon], { icon });
  marker.bindPopup(buildPopup(permit));
  marker.permitId = permit._id;
  return marker;
}

function buildPopup(p) {
  const key = statusKey(p.status);
  const color = STATUS_COLORS[key];
  return `
    <div>
      <div class="pop-record">${escapeHtml(p.record_number || '—')}</div>
      <div class="pop-address">${escapeHtml(p.address || 'Address unknown')}</div>
      <div class="pop-meta">
        ${escapeHtml(p.date || '')}<br/>
        <span class="status-badge" style="color:${color}">
          <span class="dot" style="background:${color}"></span>${escapeHtml(p.status || 'Unknown')}
        </span>
      </div>
      ${p.description ? `<div class="pop-meta" style="margin-top:6px">${escapeHtml(truncate(p.description, 140))}</div>` : ''}
      ${p.detail_url ? `<a href="${escapeHtml(p.detail_url)}" target="_blank" rel="noopener">Open in Accela ↗</a>` : ''}
    </div>
  `;
}

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
}
function truncate(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }

// ────────────────────────────────────────────────────────────
// Render
// ────────────────────────────────────────────────────────────
function applyFilters() {
  const q = searchQuery.toLowerCase().trim();
  return allPermits.filter(p => {
    const k = statusKey(p.status);
    if (activeStatuses.size > 0 && !activeStatuses.has(k)) return false;
    if (q) {
      const hay = [p.record_number, p.address, p.description, p.status].join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

function renderStatusFilter() {
  const counts = {};
  for (const p of allPermits) {
    const k = statusKey(p.status);
    counts[k] = (counts[k] || 0) + 1;
  }
  const order = ['review','submitted','pending','hold','issued','finaled','expired','void','other'];
  const present = order.filter(k => counts[k]);

  const container = document.getElementById('status-filter');
  container.innerHTML = '';
  for (const k of present) {
    const chip = document.createElement('span');
    chip.className = 'chip' + (activeStatuses.has(k) ? ' active' : '');
    chip.dataset.key = k;
    chip.innerHTML = `
      <span class="dot" style="background:${STATUS_COLORS[k]}; color:${STATUS_COLORS[k]}"></span>
      ${STATUS_LABELS[k]}
      <span class="count">${counts[k]}</span>
    `;
    chip.addEventListener('click', () => {
      if (activeStatuses.has(k)) activeStatuses.delete(k);
      else activeStatuses.add(k);
      renderStatusFilter();
      renderList();
      renderMarkers();
    });
    container.appendChild(chip);
  }
}

function renderList() {
  const filtered = applyFilters();
  document.getElementById('visible-count').textContent = filtered.length;

  const list = document.getElementById('permit-list');
  list.innerHTML = '';
  for (const p of filtered) {
    const k = statusKey(p.status);
    const item = document.createElement('div');
    item.className = 'permit-item';
    item.dataset.id = p._id;
    item.innerHTML = `
      <div class="top">
        <span class="record">${escapeHtml(p.record_number || '—')}</span>
        <span class="date">${escapeHtml(p.date || '')}</span>
      </div>
      <div class="address">${escapeHtml(p.address || 'Address unknown')}</div>
      <div class="status-row">
        <span class="status-badge" style="color:${STATUS_COLORS[k]}">
          <span class="dot" style="background:${STATUS_COLORS[k]}"></span>${escapeHtml(p.status || 'Unknown')}
        </span>
        ${(p.lat == null || p.lon == null) ? '<span class="no-coords">(not on map)</span>' : ''}
      </div>
    `;
    item.addEventListener('click', () => focusPermit(p));
    list.appendChild(item);
  }
}

function renderMarkers() {
  markerLayer.clearLayers();
  markerById.clear();
  const filtered = applyFilters();
  const layers = [];
  for (const p of filtered) {
    if (p.lat == null || p.lon == null) continue;
    const m = makeMarker(p);
    layers.push(m);
    markerById.set(p._id, m);
  }
  if (layers.length) markerLayer.addLayers(layers);
}

function focusPermit(p) {
  document.querySelectorAll('.permit-item').forEach(el => el.classList.toggle('active', el.dataset.id === String(p._id)));
  const m = markerById.get(p._id);
  if (m) {
    map.setView(m.getLatLng(), 16, { animate: true });
    m.openPopup();
  }
}

// ────────────────────────────────────────────────────────────
// Data loading
// ────────────────────────────────────────────────────────────
async function loadData() {
  try {
    const r = await fetch('permits.json', { cache: 'no-cache' });
    if (!r.ok) throw new Error('not found');
    const data = await r.json();
    onDataLoaded(data);
  } catch {
    showEmptyState();
  }
}

function onDataLoaded(data) {
  allPermits = (data.permits || []).map((p, i) => ({ ...p, _id: i }));
  document.getElementById('last-refresh').textContent =
    data.generated_at ? new Date(data.generated_at).toLocaleString() : '—';
  renderStatusFilter();
  renderList();
  renderMarkers();
  // Auto-fit to data
  const withCoords = allPermits.filter(p => p.lat != null && p.lon != null);
  if (withCoords.length) {
    const bounds = L.latLngBounds(withCoords.map(p => [p.lat, p.lon]));
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 13 });
  }
}

function showEmptyState() {
  const aside = document.querySelector('aside');
  aside.innerHTML = `
    <div class="empty">
      <h2>No permits.json found</h2>
      <p>Run <code>python scraper.py</code> to fetch the latest data, or load a file manually.</p>
      <button class="upload-btn" id="upload-trigger">Load permits.json</button>
    </div>
  `;
  document.getElementById('upload-trigger').addEventListener('click', () => {
    document.getElementById('file-input').click();
  });
}

document.getElementById('file-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const text = await file.text();
  try {
    const data = JSON.parse(text);
    location.reload(); // simplest path: stash & reload
    sessionStorage.setItem('permits_data', text);
  } catch (err) {
    alert('Could not parse JSON: ' + err.message);
  }
});

// Restore from sessionStorage if user uploaded after empty state
const stashed = sessionStorage.getItem('permits_data');
if (stashed) {
  // Rebuild full UI (since empty state replaced sidebar)
  location.hash = '';
}

// ────────────────────────────────────────────────────────────
// Wiring
// ────────────────────────────────────────────────────────────
document.getElementById('search-input').addEventListener('input', (e) => {
  searchQuery = e.target.value;
  renderList();
  renderMarkers();
});

initMap();

if (sessionStorage.getItem('permits_data')) {
  onDataLoaded(JSON.parse(sessionStorage.getItem('permits_data')));
} else {
  loadData();
}
</script>

</body>
</html>
