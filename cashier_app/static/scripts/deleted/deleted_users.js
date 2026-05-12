/**
 * @file Správa smazaných uživatelů – zobrazení, vyhledávání, řazení a obnova smazaných uživatelů.
 */
import { handleUnauthorizedRedirect } from '../general/api_utils.js';
import { cacheFunctionFactory } from '../general/cache_factory.js';
import { formatDateTimeISOToDisplay } from '../general/date_utils.js';
import { headerClickListeners, renderHeader } from '../general/header.js';
import { escapeHTML } from '../general/html_display_utils.js';
import { clearModalErrors, closeModal, openModal } from '../general/modals_forms.js';
import { renderSidebar, sidebarClickListeners } from '../general/sidebar.js';
import { handleRowSelection, markSelectedRows, unselectRows } from '../general/table_utils.js';
import { isTypingInEditable } from '../general/utils.js';


const tableBody = document.querySelector('#deleted-users-table-body');
const tableHeader = document.querySelector('table thead');
const usersSearchBar = document.querySelector('.search-bar');

const orderBy = { key: '', ascending: true };

const [fetchDeletedUsers, resetDeletedUsersCache] = cacheFunctionFactory(async () => {
  const response = await fetch('/api/users/deleted');

  await handleUnauthorizedRedirect(response);

  const resData = await response.json();

  if (!response.ok) {
    throw new Error(resData.error || 'unknown_error');
  }

  return resData.users;
})

loadPage({
  table: true,
  header: true,
  sidebar: true
});


/**
 * Načte a vykreslí části stránky podle zadaných parametrů.
 * @param {Object} param0 - Objekt s parametry, které části načíst.
 * @param {boolean} [param0.table=false] - Zda načíst tabulku.
 * @param {boolean} [param0.header=false] - Zda načíst hlavičku.
 * @param {boolean} [param0.sidebar=false] - Zda načíst postranní panel.
 * @returns {Promise<void>} - Vrací promise po dokončení načítání.
 */
async function loadPage({
  table = false,
  header = false,
  sidebar = false } = {}) {
  const toLoad = [];
  if (table) toLoad.push(renderTable());
  if (header) toLoad.push(renderHeader());
  if (sidebar) toLoad.push(renderSidebar());
  await Promise.all(toLoad);
}


document.addEventListener('click', async (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) return;

  const closeModalBtn = event.target.closest('.close-modal');
  if (closeModalBtn) {
    closeModal();
    return;
  }

  const restoreBtn = event.target.closest('.restore.icon-btn');
  if (restoreBtn) {
    const row = restoreBtn.closest('tr[id]');
    if (row) openRestoreModal(row.id);
    return;
  }

  // nastavuje řazení (při kliknutí na span v header)
  const headerEl = event.target.closest('th[id]');
  if (headerEl && event.target.matches('span')) {
    if (headerEl.id === 'first-name-header') {
      toggleOrder('first_name');
    } else if (headerEl.id === 'last-name-header') {
      toggleOrder('last_name');
    } else if (headerEl.id === 'email-header') {
      toggleOrder('email');
    } else if (headerEl.id === 'phone-header') {
      toggleOrder('phone_number');
    } else if (headerEl.id === 'other-identifier-header') {
      toggleOrder('other_identifier');
    } else if (headerEl.id === 'deleted-at-header') {
      toggleOrder('deleted_at');
    } else {
      return;
    }
    tableHeader.querySelectorAll('.order-by-arrow').forEach(el => el.remove());
    if (orderBy.key) {
      const orderByArrow = document.createElement('span');
      orderByArrow.classList.add('order-by-arrow');
      orderByArrow.innerHTML = orderBy.ascending ? '&#8595;' : '&#8593;';
      headerEl.querySelector('div').appendChild(orderByArrow);
    }

    loadPage({ table: true });
    return;
  }

  const forceBtn = event.target.closest('#force-user-restore')
  if (forceBtn) {
    forceBtn.disabled = true;
    const form = document.querySelector('#restore-user-form');
    if (!form) return;
    const formData = new FormData(form);
    formData.append('force', 'true');
    const response = await restoreUser(formData);
    if (response === true) {
      closeModal();
      resetDeletedUsersCache();
      loadPage({ table: true });
      return;
    }
    showRestoreErrors(response.error);
  }

  // kliknutí na řádek ho vybere
  const row = event.target.closest('tr[id]');
  if (row) {
    handleRowSelection(event);
    return;
  }

  if (event.target.matches('.search-bar') || document.querySelector('.modal')) {
    return;
  }

  // když nebylo kliknuto na nic jiného:
  unselectRows();
});


document.addEventListener('dblclick', async (event) => {
  const row = event.target.closest('tr[id]');
  if (row) {
    openRestoreModal(row.id);
    return;
  }
});


document.addEventListener('submit', async (event) => {
  const restoreForm = event.target.closest('#restore-user-form');
  if (restoreForm) {
    event.preventDefault();
    const submitButton = restoreForm.querySelector('button[type=submit]');
    submitButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(restoreForm);

    const response = await restoreUser(formData);

    submitButton.disabled = false;

    if (response === true) {
      closeModal();
      resetDeletedUsersCache();
      loadPage({ table: true });
      return;
    }

    showRestoreErrors(response.error);
    return;
  }
});


usersSearchBar.addEventListener('input', () => {
  loadPage({ table: true });
});


document.addEventListener('keydown', (event) => {
  if (isTypingInEditable()) return;

  handleRowSelection(event);

  if (event.key === 'Escape') {
    const overlay = document.querySelector('.overlay');
    if (overlay) {
      closeModal();
      return;
    }
  }

  if (event.key === 'Enter') {
    const selectedRows = document.querySelectorAll('tr[selected]');
    if (selectedRows.length === 1) {
      const row = selectedRows[0];
      if (row) {
        openRestoreModal(row.id);
        return;
      }
    }
  }

});



/**
 * Přepíná řazení tabulky podle zadaného klíče.
 * @param {string} key - Klíč, podle kterého se má řadit.
 */
function toggleOrder(key) {
  if (orderBy.key !== key) {
    orderBy.key = key;
    orderBy.ascending = true;
  } else if (orderBy.ascending) {
    orderBy.ascending = false;
  } else {
    orderBy.key = '';
    orderBy.ascending = true;
  }
}



/**
 * Zjišťuje, zda uživatel odpovídá aktuálnímu vyhledávání.
 * @param {Object} user - Objekt uživatele.
 * @returns {boolean} - Vrací true, pokud uživatel odpovídá hledání.
 */
function userIsSearchedFor(user) {
  const searchQuery = usersSearchBar.value.toLowerCase().trim();

  if (!searchQuery) return true;

  const queries = searchQuery.split(/\s+/);


  const firstName = String(user.first_name || '').toLowerCase();
  const lastName = String(user.last_name || '').toLowerCase();
  const email = String(user.email || '-').toLowerCase();
  const phoneNumber = String(user.phone_number || '-').toLowerCase().replace(/\s/g, '');
  const otherIdentifier = String(user.other_identifier || '-').toLowerCase();

  const searchable = `${firstName} ${lastName} ${email} ${phoneNumber} ${otherIdentifier}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');

      if (['name',
        'jméno',
        'jmeno',
        'uživatel',
        'uzivatel',
        'uživatelské_jméno',
        'uzivatelske_jmeno',
        'uživatelskéjméno',
        'uzivatelskejmeno'].includes(searchKeyWord)) {
        if (!`${firstName} ${lastName}`.includes(search)) return false;
      } else if ([
        'first_name',
        'firstname',
        'křestníjméno',
        'krestnijmeno',
        'křestní_jméno',
        'krestni_jmeno',
        'křestní',
        'krestni',].includes(searchKeyWord)) {
        if (!firstName.includes(search)) return false;
      } else if (['last_name',
        'lastname',
        'příjmení',
        'prijmeni'].includes(searchKeyWord)) {
        if (!lastName.includes(search)) return false;
      } else if (['email',
        'e-mail',
        'mail'].includes(searchKeyWord)) {
        if (!email.includes(search)) return false;
      } else if (['phone',
        'phone_number',
        'phonenumber',
        'telephone',
        'number',
        'telefonní_číslo',
        'telefonni_cislo',
        'telefonníčíslo',
        'telefonnicislo',
        'telefon',
        'číslo',
        'cislo',
        'telefonní',
        'telefonni'].includes(searchKeyWord)) {
        if (!phoneNumber.includes(search)) return false;
      } else if (['identifier',
        'other_identifier',
        'otheridentifier',
        'other',
        'jiný_identifikátor',
        'jiny_identifikator',
        'jinýidentifikátor',
        'jinyidentifikator',
        'identifikátor',
        'identifikator',
        'jiný',
        'jiny'].includes(searchKeyWord)) {
        if (!otherIdentifier.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}



/**
 * Vykreslí tabulku smazaných uživatelů podle aktuálního řazení a vyhledávání.
 * @returns {Promise<void>} - Vrací promise po dokončení vykreslení tabulky.
 */
async function renderTable() {
  const users = await fetchDeletedUsers().catch(() => {
    tableBody.innerHTML = '<tr><td colspan="8" class="error-message">Nepovedlo se načíst smazané uživatele.</td></tr>';
  });
  if (!users) return;

  const sorter = (a, b) => {
    if (!orderBy.key) return 0;
    const key = orderBy.key;
    let aa = a[key] || '';
    let bb = b[key] || '';

    if (key === 'deleted_at') {
      aa = aa ? new Date(aa).getTime() : Infinity;
      bb = bb ? new Date(bb).getTime() : 0;
      return (aa - bb) * (orderBy.ascending ? 1 : -1);
    }

    aa = String(aa).toLowerCase();
    bb = String(bb).toLowerCase();
    return aa.localeCompare(bb) * (orderBy.ascending ? 1 : -1);
  };

  const sorted = users.toSorted(sorter);
  let rows = '';
  let idx = 0;

  sorted.forEach(user => {
    if (!userIsSearchedFor(user)) return;
    idx++;
    rows += `
      <tr id="${user.id}">
        <td>${idx}</td>
        <td>${escapeHTML(user.first_name)}</td>
        <td>${escapeHTML(user.last_name)}</td>
        <td>${escapeHTML(user.email || '-')}</td>
        <td>${escapeHTML(user.phone_number || '-')}</td>
        <td>${escapeHTML(user.other_identifier || '-')}</td>
        <td class="deleted-at muted">${escapeHTML(formatDateTimeISOToDisplay(user.deleted_at))}</td>
        <td class="actions">
          <button class="icon-btn restore" title="Obnovit uživatele">
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

  markSelectedRows(tableBody);
}



/**
 * Otevře modální okno pro obnovení uživatele.
 * @param {string} userId - ID uživatele, který má být obnoven.
 * @returns {Promise<void>} - Vrací promise po otevření modalu.
 */
async function openRestoreModal(userId) {
  const users = await fetchDeletedUsers().catch(() => { });
  if (!users) return;
  const user = users.find(user => user.id === userId);
  if (!user) return;

  const html = `
    <header>
      <h2>Obnovit uživatele</h2>
    </header>
    <form id="restore-user-form">
      <input type="hidden" name="user-id" value="${user.id}" />
      <div class="form-row">
        <div>Opravdu chcete obnovit uživatele "${user.first_name} ${user.last_name}"?</div>
      </div>
      <div class="form-row">
        <div id="restore-general-error" class="form-error"></div>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost close-modal">Zrušit</button>
        <button type="submit" class="btn btn-primary">Obnovit</button>
      </div>
    </form>
  `;

  openModal(html, false);
}



/**
 * Zobrazí chybové hlášky při obnově uživatele v modálním okně.
 * @param {string} error - Kód chyby nebo chybová zpráva.
 */
function showRestoreErrors(error) {
  const generalError = document.querySelector('#restore-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();

  switch (errorStr) {
    case 'unexpected_error':
    case 'internal_server_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'invalid_user_id':
      setErr(generalError, 'ID uživatele není správné.');
      return;
    case 'user_not_found':
      setErr(generalError, 'Uživatel nebyl nalezen.');
      return;
    case 'user_conflict':
      setErr(generalError, 'Nelze obnovit: existuje aktivní uživatel s konfliktními údaji (např. stejný email).');
      return;
    case 'user_identifier_taken':
    case 'user_email_taken':
    case 'tag_id_taken': {
      if (!generalError) return;

      const errorMsgs = {
        'user_identifier_taken': 'Nelze obnovit: uživatel se stejnými údaji už existuje.',
        'user_email_taken': 'Nelze obnovit: uživatel se stejným emailem už existuje.',
        'tag_id_taken': 'Nelze obnovit: id karty uživatele se aktuálně používá.',
      };

      generalError.innerHTML = `
        <div>${errorMsgs[errorStr]}</div>
        <button id="force-user-restore" type="button" class="btn btn-primary">Vynutit obnovení</button>
        <div class="muted">Pro uživatele: změní email, popřípadě jiný identifikátor</div>
        <div class="muted">Pro kartu: změní její ID</div>
        <div class="muted">Konfliktních údajů může být víc než je zmíněno ve vrácené chybě</div>
      `;

      generalError.classList.add('show-form-error');
      return;
    }
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}



/**
 * Odesílá požadavek na obnovení uživatele na server.
 * @param {FormData} formData - Data formuláře s informacemi o uživateli.
 * @returns {Promise<true|{error: string}>} - Vrací true při úspěchu, jinak objekt s chybou.
 */
async function restoreUser(formData) {
  try {
    const response = await fetch('/api/users/restore', {
      method: 'POST',
      body: formData,
    });

    await handleUnauthorizedRedirect(response);

    const data = await response.json();

    if (!response.ok) {
      return data;
    }

    return true;

  } catch (error) {
    return { error: 'unexpected_error' };
  }
}
