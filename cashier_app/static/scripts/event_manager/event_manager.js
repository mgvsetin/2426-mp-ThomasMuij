// event_manager.js
// Minimal scaffold. Replace /api/... endpoints with your own.
// Hooks: #event-id-val, #event-name, #event-start, #event-end, #event-created-by, #event-created-at
// Tables: #employees-table-body, #products-table-body, #booths-table-body
// Charts: #profit-chart, #products-chart

import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";

const employeesTbody = document.querySelector('#employees-table-body');
const productsTbody = document.querySelector('#products-table-body');
const boothsTbody = document.querySelector('#booths-table-body');

loadPage({ 
  header: true,
  sidebar: true,
  data: true });

async function loadPage({
  header = false,
  sidebar = false,
  data = false } = {}
) {
  const tasks = [];
  if (header) tasks.push(renderHeader());
  if (sidebar) tasks.push(renderSidebar());
  if (data) tasks.push(loadEventData());
  await Promise.all(tasks);
}

document.addEventListener('click', (event) => {
  headerClickListeners(event);
  sidebarClickListeners(event);

  if (event.target.closest('#refresh-event')) {
    loadEventData();
    return;
  }
  if (event.target.closest('#add-employee-to-event')) {
    openAddEmployeeToEventOverlay();
    return;
  }
  if (event.target.closest('.employee-link')) {
    // sample handler for employee row click
    const id = event.target.closest('tr')?.id;
    if (id) openEditEmployeeRoleOverlay(id);
  }
  if (event.target.closest('#open-graph-modal')) {
    openGraphModal();
  }
});

/* ---------- Data loading ---------- */

async function loadEventData() {
  // Placeholder: your server should provide event + employees + products + booths endpoints.
  // Example: GET /api/events/selected -> { event: {...}, employees: [...], products: [...], booths: [...] }
  try {
    const eventId = location.pathname.split('/')[2];
    const res = await fetch(`/api/events/${eventId}`);
    if (res.status === 401) {
      const json = await res.json();
      window.location.href = json.redirect_url;
      return;
    }
    if (!res.ok) throw new Error('failed_to_load_event');

    const data = await res.json();
    // expected structure:
    // data.event, data.employees (array), data.products (array), data.booths (array)
    renderEventHeader(data.event);
    renderEmployeesTable(data.employees || []);
    renderProductsTable(data.products || []);
    renderBoothsTable(data.booths || []);
    renderCharts(data.metrics || {}); // optional metrics: profit, products_sold...
  } catch (err) {
    console.error('loadEventData:', err);
    // show minimal error in tables
    employeesTbody.innerHTML = `<tr><td colspan="7" class="error-message">Nepodařilo se načíst data akce.</td></tr>`;
    productsTbody.innerHTML = `<tr><td colspan="6" class="error-message">Nepodařilo se načíst data akce.</td></tr>`;
    boothsTbody.innerHTML = `<tr><td colspan="7" class="error-message">Nepodařilo se načíst data akce.</td></tr>`;
  }
}

/* ---------- Renderers ---------- */

function renderEventHeader(event = {}) {
  document.getElementById('event-id-val').textContent = event.id || '—';
  document.getElementById('event-name').textContent = event.name || '—';
  document.getElementById('event-start').textContent = event.start_at ? formatDateTime(event.start_at) : '—';
  document.getElementById('event-end').textContent = event.end_at ? formatDateTime(event.end_at) : '—';
  document.getElementById('event-created-by').textContent = event.created_by || '—';
  document.getElementById('event-created-at').textContent = event.created_at ? formatDateTime(event.created_at) : '—';
}

function renderEmployeesTable(employees = []) {
  // employees: { id, username, email, role, booths: [{id, name}, ...], created_by, created_at }
  if (!employees.length) {
    employeesTbody.innerHTML = `<tr><td class="error-message" colspan="7">Žádní zaměstnanci přiřazení k této akci.</td></tr>`;
    return;
  }

  let html = '';
  let n = 1;
  for (const emp of employees) {
    const boothsHtml = (emp.booths || []).map(b => `<span class="small-chip" title="${escapeHtml(b.name)}">${escapeHtml(b.name)}</span>`).join(' ');
    const createdAt = emp.created_at ? formatDateTime(emp.created_at) : '-';
    const role = emp.role || '—';
    html += `
      <tr id="${emp.id}" data-employee='${escapeHtml(JSON.stringify(emp))}'>
        <td>${n}</td>
        <td class="username">${escapeHtml(emp.username || '-')} <span class="id muted">(${escapeHtml(emp.id || '-')})</span></td>
        <td>${escapeHtml(role)}</td>
        <td><div class="small-list">${boothsHtml || '-'}</div></td>
        <td class="muted">${escapeHtml(emp.created_by || '-')}</td>
        <td class="muted">${createdAt}</td>
        <td class="actions">
          <button class="icon-btn edit employee-link" title="Upravit roli/stánky">
            ✎
          </button>
        </td>
      </tr>
    `;
    n++;
  }
  employeesTbody.innerHTML = html;
}

function renderProductsTable(products = []) {
  // products: { id, name, price_czk, booths: [{id,name}], created_at }
  if (!products.length) {
    productsTbody.innerHTML = `<tr><td class="error-message" colspan="6">Žádné produkty pro tuto akci.</td></tr>`;
    return;
  }

  let html = '';
  let n = 1;
  for (const p of products) {
    const boothsHtml = (p.booths || []).map(b => `<span class="small-chip">${escapeHtml(b.name)}</span>`).join(' ');
    const createdAt = p.created_at ? formatDateTime(p.created_at) : '-';
    html += `
      <tr id="${p.id}" data-product='${escapeHtml(JSON.stringify(p))}'>
        <td>${n}</td>
        <td class="username">${escapeHtml(p.name || '-')} <span class="id muted">(${escapeHtml(p.id || '-')})</span></td>
        <td>${typeof p.price_czk === 'number' ? p.price_czk : '-'}</td>
        <td><div class="small-list">${boothsHtml || '-'}</div></td>
        <td class="muted">${createdAt}</td>
        <td class="actions">
          <button class="icon-btn edit" data-product-edit="${p.id}">✎</button>
        </td>
      </tr>
    `;
    n++;
  }
  productsTbody.innerHTML = html;
}

function renderBoothsTable(booths = []) {
  // booths: { id, name, booth_type, auth_required, created_by, created_at }
  if (!booths.length) {
    boothsTbody.innerHTML = `<tr><td class="error-message" colspan="7">Žádné stánky pro tuto akci.</td></tr>`;
    return;
  }

  let html = '';
  let n = 1;
  for (const b of booths) {
    const createdAt = b.created_at ? formatDateTime(b.created_at) : '-';
    html += `
      <tr id="${b.id}" data-booth='${escapeHtml(JSON.stringify(b))}'>
        <td>${n}</td>
        <td class="username">${escapeHtml(b.name || '-')} <span class="id muted">(${escapeHtml(b.id || '-')})</span></td>
        <td>${escapeHtml(b.booth_type || '-')}</td>
        <td>${b.auth_required ? 'ano' : 'ne'}</td>
        <td class="muted">${escapeHtml(b.created_by || '-')}</td>
        <td class="muted">${createdAt}</td>
        <td class="actions">
          <button class="icon-btn edit" data-booth-edit="${b.id}">✎</button>
        </td>
      </tr>
    `;
    n++;
  }
  boothsTbody.innerHTML = html;
}

/* ---------- Charts (placeholders) ---------- */

function renderCharts(metrics = {}) {
  // metrics could be: { profit_timeseries: [...], products_sold: [...], total_profit, transactions_count }
  document.getElementById('total-profit').textContent = metrics.total_profit ?? '—';
  document.getElementById('transactions-count').textContent = metrics.transactions_count ?? '—';

  // Simple placeholder drawing without external libs:
  drawPlaceholderChart('profit-chart', metrics.profit_timeseries || []);
  drawPlaceholderChart('products-chart', metrics.products_sold || []);
}

function drawPlaceholderChart(canvasId, series = []) {
  const c = document.getElementById(canvasId);
  if (!c) return;
  const ctx = c.getContext('2d');
  const w = c.width;
  const h = c.height;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = '#f3f7fb';
  ctx.fillRect(0, 0, w, h);
  ctx.fillStyle = '#1f6feb';
  ctx.font = '12px sans-serif';
  if (!series.length) {
    ctx.fillStyle = '#6b7280';
    ctx.fillText('Žádná data', 10, 20);
    return;
  }
  // draw simple bars/line
  const max = Math.max(...series.map(s => s.value || s));
  const step = w / series.length;
  series.forEach((s, i) => {
    const val = s.value ?? s;
    const hval = (val / max) * (h - 30);
    ctx.fillRect(i * step + 6, h - hval - 10, Math.max(6, step - 8), hval);
  });
}

/* ---------- Overlays (basic, you can expand) ---------- */

function openAddEmployeeToEventOverlay() {
  const overlay = `
    <div id="add-employee-overlay">
      <div id="add-modal" class="modal-small">
        <header>
          <h3>Přidat zaměstnance k akci</h3>
          <button id="add-employee-close">✖</button>
        </header>
        <form id="add-employee-form" style="padding:12px;">
          <label>Employee ID nebo uživatelské jméno<input name="employee_identifier" type="text" required /></label>
          <label>Role
            <select name="role">
              <option value="event_manager">event_manager</option>
              <option value="seller">seller</option>
              <option value="cashier">cashier</option>
            </select>
          </label>
          <div style="display:flex; gap:8px; justify-content:flex-end; padding-top:10px;">
            <button type="button" id="add-employee-cancel">Zrušit</button>
            <button type="submit" id="add-employee-save">Přidat</button>
          </div>
        </form>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', overlay);

  document.getElementById('add-employee-close').addEventListener('click', closeAddEmployeeOverlay);
  document.getElementById('add-employee-cancel').addEventListener('click', closeAddEmployeeOverlay);
  document.getElementById('add-employee-form').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    // collect and POST to /api/employee_event_booth_roles/create or similar
    // after success: reload data
    closeAddEmployeeOverlay();
    await loadEventData();
  });
}

function closeAddEmployeeOverlay() {
  const el = document.getElementById('add-employee-overlay');
  if (el) el.remove();
}

function openEditEmployeeRoleOverlay(employeeId) {
  // read row data
  const row = document.getElementById(employeeId);
  if (!row) return;
  const emp = JSON.parse(row.getAttribute('data-employee'));
  // build overlay (left as simple example)
  const overlay = `
    <div id="edit-role-overlay">
      <div id="edit-modal" class="modal-small">
        <header>
          <h3>Upravit přiřazení — ${escapeHtml(emp.username)}</h3>
          <button id="edit-role-close">✖</button>
        </header>
        <div style="padding:12px;">
          <p><strong>Role:</strong> ${escapeHtml(emp.role || '')}</p>
          <p><strong>Stánky:</strong> ${(emp.booths || []).map(b => escapeHtml(b.name)).join(', ') || '-'}</p>
          <div style="display:flex; gap:8px; justify-content:flex-end; padding-top:10px;">
            <button id="edit-role-cancel">Zavřít</button>
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.insertAdjacentHTML('beforeend', overlay);
  document.getElementById('edit-role-close').addEventListener('click', closeEditRoleOverlay);
  document.getElementById('edit-role-cancel').addEventListener('click', closeEditRoleOverlay);
}

function closeEditRoleOverlay() {
  const el = document.getElementById('edit-role-overlay');
  if (el) el.remove();
}

function openGraphModal() {
  // Expand charts to fullscreen — quick placeholder
  alert('Tady můžete otevřít fullscreen grafy (implementace dle preferencí).');
}

/* ---------- Utilities ---------- */

function formatDateTime(iso) {
  try {
    const d = new Date(iso);
    return `${d.getDate()}.${d.getMonth() + 1}.${d.getFullYear()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  } catch (e) {
    return iso;
  }
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
