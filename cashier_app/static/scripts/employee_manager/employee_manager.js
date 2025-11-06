import { getEmployees } from "../general/employees.js";
import { headerClickListeners, headerKeydownListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";

const employeeTableBody = document.querySelector('#employee-table-body');

loadPage({
  table: true,
  header: true,
  sidebar: true
});


async function loadPage({
  table = false,
  sidebar = false,
  header = false
} = {}) {
  
  const toLoad = [];

  if (table) {
    toLoad.push(renderTableRows());
  }

  if (sidebar) {
    toLoad.push(renderSidebar('#employee-manager-link'));
  }

  if (header) {
    toLoad.push(renderHeader());
  }

  await Promise.all(toLoad);
}


document.addEventListener('click', (event) => {
  headerClickListeners(event);
  sidebarClickListeners(event);

  const editButton = event.target.closest('.edit.icon-btn');
  if (editButton) {
    const row = editButton.closest('tr[data-employee]');
    openEditOverlay(row);
  }


  const cancelButton = event.target.closest('#edit-cancel');
  const editModalClose = event.target.closest('#edit-modal-close')
  if (cancelButton || editModalClose) {
    const overlayEl = document.querySelector('#edit-overlay');
    overlayEl.remove();
  }
});

document.addEventListener('dblclick', (event) => {
  const row = event.target.closest('tr[data-employee]');
  if (row) {
    openEditOverlay(row);
  }
})

document.addEventListener('keydown', (event) => {
  headerKeydownListeners(event);
})


async function renderTableRows() {
  const employees = await getEmployees();

  let rowsHTML = '';

  if (employees === 'unexpected_error' || employees === 'insufficient_priviliges') {
    employeeTableBody.innerHTML = `
      <th class="error-message" colspan="10">
        Nepovedlo se načíst zaměstnance.
      </th>
    `;
    return;
  }
  

  employees.forEach((employee) => {
    let isAdminHTML;

    if (employee.is_admin) {
      isAdminHTML = '<span class="badge yes">ANO</span>';
    } else {
      isAdminHTML = '<span class="badge no">NE</span>';
    }

    const createdAt = new Date(employee.created_at);
    const createdAtHTML = `
      ${createdAt.getDate()}. ${createdAt.getMonth()}. ${createdAt.getFullYear()}
    `;

    rowsHTML += `
      <tr data-employee='${JSON.stringify(employee)}'>
        <td class="username">${employee.username} <span class="id muted">(${employee.id})</span></td>
        <td class="email">${employee.email}</td>
        <td>${isAdminHTML}</td>
        <td class="created-by muted">${employee.created_by}</td>
        <td class="created-at muted">${createdAtHTML}</td>
        <td class="actions">
          <button class="icon-btn edit">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  })

  employeeTableBody.innerHTML = rowsHTML;
}


function openEditOverlay(row) {
  if (!row) return;
  let employee;
  try {
    employee = JSON.parse(row.getAttribute('data-employee'));
  } catch (err) {
    console.error('Failed to parse employee data:', err);
    return;
  }

  const overlayHTML = `
    <div id="edit-overlay">
      <div id="edit-modal">
        <header id="edit-modal-header">
          <h2 id="edit-overlay-title">Upravit zaměstnance</h2>
          <button id="edit-modal-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>

        <form id="edit-form">
          <div class="form-row">
            <label for="edit-username">Uživatelské jméno</label>
            <input id="edit-username" name="username" type="text" autocomplete="username" value="${escapeHTML(employee.username || '')}" required/>
          </div>

          <div class="form-row">
            <label for="edit-email">Email</label>
            <input id="edit-email" name="email" type="email" autocomplete="email" value="${escapeHTML(employee.email || '')}" required />
          </div>

          <div class="form-row">
            <label for="edit-password">Heslo</label>
            <input id="edit-password" name="password" type="password" placeholder="Nechte prázdné, pokud neměníte heslo" />
          </div>

          <div id="edit-form-actions">
            <button type="button" id="edit-cancel">Zrušit</button>
            <button type="button" id="edit-save" data-employee-id="${employee.id}">Uložit</button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', overlayHTML);
}


function escapeHTML(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}