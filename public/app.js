let _allIncidents = [];
let _page = 1;
const PER_PAGE = 50;

function _esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

async function init() {
  const [summary, incidents] = await Promise.all([
    fetch('data/summary.json').then(r => r.json()),
    fetch('data/incidents.json').then(r => r.json()),
  ]);

  _allIncidents = incidents;

  document.getElementById('stat-total').textContent = summary.total_incidents?.toLocaleString() ?? '—';
  document.getElementById('stat-range').textContent = summary.date_min
    ? `${summary.date_min.slice(0, 10)} – ${summary.date_max.slice(0, 10)}`
    : '—';
  document.getElementById('stat-updated').textContent = summary.generated_at?.slice(0, 10) ?? '—';

  // Incident type chart (client-side aggregation)
  const typeCounts = {};
  incidents.forEach(r => {
    const key = r.category || r.incident_type || 'Unknown';
    typeCounts[key] = (typeCounts[key] || 0) + 1;
  });
  const sortedTypes = Object.entries(typeCounts).sort((a, b) => b[1] - a[1]).slice(0, 15);
  new Chart(document.getElementById('chart-type'), {
    type: 'bar',
    data: {
      labels: sortedTypes.map(([t]) => t),
      datasets: [{ data: sortedTypes.map(([, c]) => c), backgroundColor: '#1a1a2e99' }],
    },
    options: { indexAxis: 'y', plugins: { legend: { display: false } }, responsive: true },
  });

  renderTable();
}

function renderTable() {
  const search = document.getElementById('f-search').value.toLowerCase();
  const type = document.getElementById('f-type').value.toLowerCase();

  const filtered = _allIncidents.filter(r => {
    if (type && !(r.incident_type || '').toLowerCase().includes(type)) return false;
    if (search) {
      const haystack = [r.case_number, r.incident_type, r.disposition, r.location, r.officer].join(' ').toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });

  const totalPages = Math.max(1, Math.ceil(filtered.length / PER_PAGE));
  if (_page > totalPages) _page = 1;
  const slice = filtered.slice((_page - 1) * PER_PAGE, _page * PER_PAGE);

  document.getElementById('table-body').innerHTML = slice.map(r => `
    <tr>
      <td>${r.reported_at ? r.reported_at.replace('T', ' ').slice(0, 16) : '—'}</td>
      <td><a href="${_esc(r.source_url)}" target="_blank">${_esc(r.case_number || '—')}</a></td>
      <td>${_esc(r.incident_type || '—')}</td>
      <td>${_esc(r.disposition || '—')}</td>
      <td>${_esc(r.normalized_address || r.location || '—')}</td>
      <td>${_esc(r.officer || '—')}</td>
    </tr>
  `).join('') || '<tr><td colspan="6" style="padding:2rem;color:#888;text-align:center">No results</td></tr>';

  document.getElementById('pagination').innerHTML = `
    <span style="color:#6c757d">${filtered.length} results</span>
    ${_page > 1 ? `<button onclick="goPage(${_page - 1})">← Prev</button>` : ''}
    <span>Page ${_page} / ${totalPages}</span>
    ${_page < totalPages ? `<button onclick="goPage(${_page + 1})">Next →</button>` : ''}
  `;
}

function goPage(p) { _page = p; renderTable(); }

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('f-search').addEventListener('input', () => { _page = 1; renderTable(); });
  document.getElementById('f-type').addEventListener('input', () => { _page = 1; renderTable(); });
  init();
});
