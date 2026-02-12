import { handleUnauthorizedRedirect } from '../general/api_utils.js';
import { escapeHTML } from '../general/html_display_utils.js';
import { closeModal, openModal } from '../general/modals_forms.js';



const tableBody = document.querySelector('#deleted-users-table-body');
const searchBar = document.querySelector('#search-bar');

const orderBy = { key: '', ascending: true };

let users = [];


async function fetchDeletedUsers() {
  const response = await fetch('/api/users/deleted');
  await handleUnauthorizedRedirect(response);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'unknown_error');
  return data.users;
}


function formatDeletedAt(isoString) {
  if (!isoString) return '-';
  const d = new Date(isoString);
  return d.toLocaleString('cs-CZ', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit'
  });
}


function userMatchesSearch(user) {
  const query = searchBar.value.trim().toLowerCase();
  if (!query) return true;
  const searchable = [
    user.first_name,
    user.last_name,
    user.email,
    user.phone_number,
    user.other_identifier,
  ].filter(Boolean).map(v => v.toLowerCase()).join(' ');
  return searchable.includes(query);
}


function toggleOrder(key, headerEl) {
  if (orderBy.key !== key) {
    orderBy.key = key;
    orderBy.ascending = true;
  } else {
    orderBy.ascending = !orderBy.ascending;
  }
  document.querySelectorAll('th[id]').forEach(th => th.removeAttribute('sort-ascending'));
  if (orderBy.ascending) {
    headerEl.setAttribute('sort-ascending', '');
  }
  renderTable();
}


async function renderTable() {
  const sorter = (a, b) => {
    if (!orderBy.key) return 0;
    let aVal = String(a[orderBy.key] || '').toLowerCase();
    let bVal = String(b[orderBy.key] || '').toLowerCase();
    return aVal.localeCompare(bVal) * (orderBy.ascending ? 1 : -1);
  };

  const sorted = users.toSorted(sorter);
  let rows = '';
  let idx = 0;

  sorted.forEach(user => {
    if (!userMatchesSearch(user)) return;
    idx++;
    rows += `
      <tr id="${user.id}">
        <td>${idx}</td>
        <td>${escapeHTML(user.first_name)}</td>
        <td>${escapeHTML(user.last_name)}</td>
        <td>${escapeHTML(user.email || '-')}</td>
        <td>${escapeHTML(user.phone_number || '-')}</td>
        <td>${escapeHTML(user.other_identifier || '-')}</td>
        <td class="deleted-at">${escapeHTML(formatDeletedAt(user.deleted_at))}</td>
        <td class="actions">
          <button class="restore-btn" title="Obnovit uživatele">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M3 3v5h5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  tableBody.innerHTML = rows || '<tr><td colspan="8" class="empty-message">Žádní smazaní uživatelé.</td></tr>';
}


async function loadUsers() {
  try {
    users = await fetchDeletedUsers();
  } catch {
    tableBody.innerHTML = '<tr><td colspan="8" class="error-message">Nepovedlo se načíst smazané uživatele.</td></tr>';
    return;
  }
  renderTable();
}


async function openRestoreModal(userId) {
  const user = users.find(u => u.id === userId);
  if (!user) return;

  const overlay = openModal(`
    <header>
      <h2>Obnovit uživatele</h2>
    </header>
    <form id="restore-user-form">
      <input type="hidden" name="user-id" value="${userId}" />
      <div class="form-row">
        <div>Opravdu chcete obnovit uživatele „${escapeHTML(user.first_name)} ${escapeHTML(user.last_name)}"?</div>
      </div>
      <div class="form-row">
        <div id="restore-general-error" class="form-error"></div>
      </div>
      <div class="modal-actions">
        <button type="button" class="cancel-form close-modal">Zrušit</button>
        <button type="submit" class="save-form">Obnovit</button>
      </div>
    </form>
  `, false);

  overlay.querySelector('#restore-user-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const errorEl = overlay.querySelector('#restore-general-error');
    errorEl.textContent = '';

    const formData = new FormData(e.target);

    const response = await fetch('/api/users/restore', {
      method: 'POST',
      body: formData,
    });

    await handleUnauthorizedRedirect(response);

    if (response.ok) {
      closeModal();
      users = users.filter(u => u.id !== userId);
      renderTable();
      return;
    }

    const data = await response.json();
    if (data.error === 'user_conflict') {
      errorEl.textContent = 'Nelze obnovit: existuje aktivní uživatel s confliktními údaji (např. stejný email).';
    } else {
      errorEl.textContent = 'Nepovedlo se obnovit uživatele.';
    }
  });
}


document.addEventListener('click', async (event) => {
  const closeBtn = event.target.closest('.close-modal');
  if (closeBtn) {
    closeModal();
    return;
  }

  const restoreBtn = event.target.closest('.restore-btn');
  if (restoreBtn) {
    const row = restoreBtn.closest('tr[id]');
    if (row) await openRestoreModal(row.id);
    return;
  }

  const headerEl = event.target.closest('th[id]');
  if (headerEl && event.target.matches('span')) {
    switch (headerEl.id) {
      case 'first-name-header': toggleOrder('first_name', headerEl); break;
      case 'last-name-header': toggleOrder('last_name', headerEl); break;
      case 'email-header': toggleOrder('email', headerEl); break;
      case 'phone-header': toggleOrder('phone_number', headerEl); break;
      case 'other-identifier-header': toggleOrder('other_identifier', headerEl); break;
      case 'deleted-at-header': toggleOrder('deleted_at', headerEl); break;
    }
  }
});

searchBar.addEventListener('input', renderTable);

loadUsers();
