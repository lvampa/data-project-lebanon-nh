let _charts = {};
let _currentPage = 1;

function showTab(name) {
  ['incidents', 'stats', 'addresses', 'categories'].forEach(t => {
    document.getElementById(`tab-${t}`).classList.toggle('d-none', t !== name);
  });
  document.querySelectorAll('#nav-tabs .nav-link').forEach(el => {
    el.classList.toggle('active', el.getAttribute('onclick').includes(`'${name}'`));
  });
  if (name === 'stats') loadStats();
  if (name === 'addresses') loadAddresses();
  if (name === 'categories') loadCategories();
}

// --- Incidents ---
async function loadIncidents(page = 1) {
  _currentPage = page;
  const params = new URLSearchParams();
  const dateFrom = document.getElementById('date_from').value;
  const dateTo = document.getElementById('date_to').value;
  const type = document.getElementById('f_type').value;
  const officer = document.getElementById('f_officer').value;
  if (dateFrom) params.set('date_from', dateFrom);
  if (dateTo) params.set('date_to', dateTo);
  if (type) params.set('incident_type', type);
  if (officer) params.set('officer', officer);
  params.set('page', page);
  params.set('per_page', 50);

  const data = await fetch(`/api/incidents?${params}`).then(r => r.json());
  const tbody = document.getElementById('incidents-body');
  tbody.innerHTML = data.items.map(r => `
    <tr>
      <td>${r.reported_at ? r.reported_at.replace('T', ' ').slice(0, 16) : '—'}</td>
      <td><a href="${r.source_url}" target="_blank">${r.case_number || '—'}</a></td>
      <td>${r.incident_type || '—'}</td>
      <td>${r.disposition || '—'}</td>
      <td>${r.location || '—'}</td>
      <td>${r.officer || '—'}</td>
    </tr>
  `).join('');

  const pages = Math.ceil(data.total / data.per_page);
  const pag = document.getElementById('incidents-pagination');
  pag.innerHTML = `
    <span class="text-muted small">${data.total} results</span>
    ${page > 1 ? `<button class="btn btn-sm btn-outline-secondary" onclick="loadIncidents(${page-1})">← Prev</button>` : ''}
    <span class="small">Page ${page} / ${Math.max(1, pages)}</span>
    ${page < pages ? `<button class="btn btn-sm btn-outline-secondary" onclick="loadIncidents(${page+1})">Next →</button>` : ''}
  `;
}

// --- Stats ---
async function loadStats() {
  const [byType, byHour, byWeekday] = await Promise.all([
    fetch('/api/stats/by-type').then(r => r.json()),
    fetch('/api/stats/by-hour').then(r => r.json()),
    fetch('/api/stats/by-weekday').then(r => r.json()),
  ]);

  _renderChart('chart-type', 'bar', byType.map(r => r.incident_type), byType.map(r => r.count), 'Incidents by Type');
  _renderChart('chart-hour', 'bar', byHour.map(r => `${r.hour}:00`), byHour.map(r => r.count), 'Calls by Hour of Day');
  _renderChart('chart-weekday', 'bar', byWeekday.map(r => r.day), byWeekday.map(r => r.count), 'Calls by Day of Week');
}

function _renderChart(id, type, labels, values, title) {
  if (_charts[id]) _charts[id].destroy();
  _charts[id] = new Chart(document.getElementById(id), {
    type,
    data: { labels, datasets: [{ label: title, data: values, backgroundColor: '#0d6efd88' }] },
    options: { plugins: { legend: { display: false } }, responsive: true },
  });
}

// --- Addresses ---
async function loadAddresses() {
  const data = await fetch('/api/addresses').then(r => r.json());
  const tbody = document.getElementById('addresses-body');
  tbody.innerHTML = data.map(r => `
    <tr>
      <td><code>${_esc(r.raw_address)}</code></td>
      <td>${r.normalized_address ? _esc(r.normalized_address) : '<span class="text-danger">not normalized</span>'}</td>
      <td>${r.lat ?? '—'}</td>
      <td>${r.lng ?? '—'}</td>
      <td>${r.count}</td>
      <td>
        <button class="btn btn-xs btn-sm btn-outline-primary" onclick="editAddress(${JSON.stringify(r.raw_address)}, ${JSON.stringify(r.normalized_address || '')})">Edit</button>
      </td>
    </tr>
  `).join('');
}

async function editAddress(raw, current) {
  const normalized = prompt(`Normalize "${raw}":`, current || raw);
  if (normalized === null) return;
  const resp = await fetch(`/api/addresses/${encodeURIComponent(raw)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ normalized_address: normalized, geocode: true }),
  });
  if (resp.ok) loadAddresses();
  else alert('Failed to update address');
}

// --- Categories ---
async function loadCategories() {
  const data = await fetch('/api/categories').then(r => r.json());
  document.getElementById('categories-body').innerHTML = data.map(r => `
    <tr>
      <td><code>${_esc(r.raw_incident_type)}</code></td>
      <td>${r.category ? _esc(r.category) : '<span class="text-danger">uncategorized</span>'}</td>
      <td>${r.subcategory ? _esc(r.subcategory) : '—'}</td>
      <td>${r.count}</td>
      <td>
        <button class="btn btn-sm btn-outline-primary" onclick="editCategory(${JSON.stringify(r.raw_incident_type)}, ${JSON.stringify(r.category || '')}, ${JSON.stringify(r.subcategory || '')})">Edit</button>
      </td>
    </tr>
  `).join('');
}

async function editCategory(raw, currentCat, currentSub) {
  const category = prompt(`Category for "${raw}":`, currentCat || '');
  if (category === null) return;
  const subcategory = prompt('Subcategory (optional):', currentSub || '') || null;
  const resp = await fetch(`/api/categories/${encodeURIComponent(raw)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ category, subcategory }),
  });
  if (resp.ok) loadCategories();
  else alert('Failed to update category');
}

function _esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Boot
loadIncidents(1);
