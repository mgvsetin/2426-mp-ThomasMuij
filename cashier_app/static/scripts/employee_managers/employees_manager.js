/**
 * @file Správa zaměstnanců – přidávání, úprava, mazání a zobrazení zaměstnanců v tabulce.
 */
import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { formatDateTimeISOToDisplay } from "../general/date_utils.js";
import { fetchEmployees, resetEmployeesCache } from "../general/employees.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { clearModalErrors, closeModal, openModal } from "../general/modals_forms.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { directTo, handleCopyPasteUndoRedoOnKeydown, handleRowSelection, markSelectedRows, unselectRows } from "../general/table_utils.js";

const employeeTableBody = document.querySelector('#employee-table-body');
const tableHeader = document.querySelector('table thead');
const searchBar = document.querySelector('.search-bar');
const orderBy = { key: '', ascending: true };

resetEmployeesCache();
loadPage({
  table: true,
  header: true,
  sidebar: true
});


/**
 * Načte a vykreslí části stránky podle zadaných parametrů.
 * @param {Object} param0 - Objekt s volbami načtení.
 * @param {boolean} [param0.table=false] - Zda načíst tabulku zaměstnanců.
 * @param {boolean} [param0.sidebar=false] - Zda načíst postranní panel.
 * @param {boolean} [param0.header=false] - Zda načíst hlavičku.
 * @returns {Promise<void>} - Vrací promise po dokončení načítání.
 */
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
    toLoad.push(renderSidebar());
  }

  if (header) {
    toLoad.push(renderHeader());
  }

  await Promise.all(toLoad);
}


document.addEventListener('click', (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) {
    return;
  }

  if (event.target.matches('#add-employee-button')) {
    openAddEmployeeModal();
    return;
  }

  // zavřít přidávání zaměstnance
  const closeModalBtn = event.target.closest('.close-modal');
  if (closeModalBtn) {
    closeModal();
    return;
  }


  const isAdminToggle = event.target.closest('.is-admin-toggle');
  if (isAdminToggle && !isAdminToggle.classList.contains('disabled')) {
    const state = isAdminToggle.dataset.state || 'no';
    const option = event.target.closest('.option');

    if (option && option.classList.contains('yes')) {
      isAdminToggle.dataset.state = 'yes';
    } else if (option) {
      isAdminToggle.dataset.state = 'no';
    } else if (state === 'yes') {
      isAdminToggle.dataset.state = 'no';
    } else {
      isAdminToggle.dataset.state = 'yes';
    }
    return;
  }

  // nastavuje řazení (při kliknutí na span v header)
  const headerEl = event.target.closest('th')
  if (headerEl && event.target.matches('span')) {
    // 1. kliknutí -> ascending
    // 2. kliknutí -> descending
    // 3. kliknutí .> odendám
    if (headerEl.id === "user-header") {
      toggleOrder('username');
    } else if (headerEl.id === "email-header") {
      toggleOrder('email');
    } else if (headerEl.id === "is-admin-header") {
      toggleOrder('is_admin');
      // } else if (headerEl.id === "created-by-header") {
      //   toggleOrder('created_by');
    } else if (headerEl.id === "created-at-header") {
      toggleOrder('created_at');
    } else {
      return;
    }
    tableHeader.querySelectorAll('.order-by-arrow')
      .forEach((arrowEl) => {
        arrowEl.remove();
      });
    if (orderBy.key) {
      const orderByArrow = document.createElement('span');
      orderByArrow.classList.add('order-by-arrow');
      orderByArrow.innerHTML = orderBy.ascending ? '&#8595;' : '&#8593;';
      headerEl.querySelector('div').appendChild(orderByArrow);
    }

    loadPage({
      table: true
    })
    return;
  }

  // úprava zaměstnance
  const editButton = event.target.closest('.edit.icon-btn');
  if (editButton) {
    const row = editButton.closest('tr[id]');
    openEditModal(row.id);
    return;
  }


  // otevři potvrzení odstranění zaměstnance
  const deleteButton = event.target.closest('.delete.icon-btn');
  if (deleteButton) {
    const row = deleteButton.closest('tr[id]');
    openDeleteModal(row.id);
    return;
  }

  const openDeleteModalBtn = event.target.closest('.open-delete-modal');
  if (openDeleteModalBtn) {
    closeModal();
    const empId = openDeleteModalBtn.getAttribute('data-employee-id');
    openDeleteModal(empId);
    return;
  }


  // ukaž nebo skryj heslo a změň oko
  const showPassword = event.target.closest('.pw-eye');
  if (showPassword) {
    const passwordInput = showPassword.parentElement.querySelector('input[name="password"]');
    if (showPassword.classList.contains('state-show')) {
      passwordInput.setAttribute('type', 'password');
    } else {
      passwordInput.setAttribute('type', 'text');
    }

    const isShow = showPassword.classList.toggle('state-hide');
    showPassword.classList.toggle('state-show', !isShow);
    showPassword.classList.toggle('state-hide', isShow);
  }

  // kliknutí na id zaměstance (u vytvořil)
  const clickedDirectEl = event.target.closest('span[data-direct-to]');
  if (clickedDirectEl && employeeTableBody.contains(clickedDirectEl)) {
    directTo(clickedDirectEl, employeeTableBody)
    return;
  }

  // kliknutí na řádek ho vybere
  const row = event.target.closest('tr[id]');
  if (row) {
    handleRowSelection(event);
    return;
  }

  // zabránit výchozí akci na elementu a a přidat atribut
  // poté posunout na řádek
  // řádek s atributem bude v datech body
  // vždy nezapomenout odebrat atribut selected
  // možná přidat otevření úprav klávesou Enter pro vybraný řádek
  // možná přidat pohyb šipkami pro vybraný řádek
  // ??

  if (event.target.matches('.search-bar') || document.querySelector('.modal')) {
    return;
  }

  // když nebylo kliknuto na nic jiného:
  unselectRows();
});

document.addEventListener('dblclick', (event) => {
  const row = event.target.closest('tr[id]');
  if (row) {
    openEditModal(row.id);
  }
})


document.addEventListener('submit', async (event) => {
  // přidej zaměstnance
  const addForm = event.target.closest('#add-employee-form');
  if (addForm) {
    event.preventDefault();
    const saveButton = addForm.querySelector('.save-form');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(addForm);

    formData.set('username', formData.get('username').trim());
    formData.set('email', formData.get('email').trim());

    const isAdminToggle = addForm.querySelector('#add-is-admin-toggle');

    if (!isAdminToggle || isAdminToggle.dataset.state === 'no') {
      formData.set('is-admin', false);
    } else if (isAdminToggle.dataset.state === 'yes') {
      formData.set('is-admin', true);
    } else {
      formData.set('is-admin', false);
    }

    const response = await addEmployee(formData);

    saveButton.disabled = false;

    if (response === true) {
      closeModal();
      resetEmployeesCache();
      loadPage({
        table: true
      });
      return;
    }

    showAddErrors(response.error);
    return;
  }


  // uprav zaměstnance
  const editFrom = event.target.closest('#edit-employee-form');
  if (editFrom) {
    event.preventDefault();
    const saveButton = editFrom.querySelector('.save-form');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(editFrom);

    formData.set('username', formData.get('username').trim());
    formData.set('email', formData.get('email').trim());

    const isAdminToggle = editFrom.querySelector('#edit-is-admin-toggle');

    if (!isAdminToggle || isAdminToggle.dataset.state === 'no') {
      formData.set('is-admin', false);
    } else if (isAdminToggle.dataset.state === 'yes') {
      formData.set('is-admin', true);
    } else {
      formData.set('is-admin', false);
    }

    const response = await editEmployee(formData);

    saveButton.disabled = false;

    if (response === true) {
      closeModal();
      resetEmployeesCache();
      loadPage({
        table: true,
        header: true
      });
      return;
    }

    showEditErrors(response.error);
    return;
  }

  // odstraň zaměstnance
  const deleteForm = event.target.closest('#delete-employee-form');
  if (deleteForm) {
    event.preventDefault();
    const deleteButton = deleteForm.querySelector('.delete-confirm');
    deleteButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(deleteForm);

    const response = await deleteEmployee(formData);

    deleteButton.disabled = false;

    if (response === true) {
      closeModal();
      resetEmployeesCache();
      loadPage({
        table: true
      });
      return;
    }

    showDeleteErrors(response.error);
    return;
  }
})


searchBar.addEventListener('input', (event) => {
  // if (event.target.matches('.search-bar')) {
  loadPage({
    table: true
  })
  // }
});


document.addEventListener('keydown', (event) => {
  handleRowSelection(event);
  handleCopyPasteUndoRedoOnKeydown(event, 'employees_manager').then((result) => {
    if (['paste-employees', 'undo', 'redo'].includes(result)) {
      resetEmployeesCache();
      loadPage({
        header: true,
        sidebar: true,
        table: true
      });
    }
  });

  if (event.key === 'Enter' && !document.querySelector('.modal')) {
    const selectedRows = document.querySelectorAll('tr[id][selected]');
    if (selectedRows.length === 1) {
      openEditModal(selectedRows[0].id);
    }
  }

  if (event.key === 'Escape') {
    const overlay = document.querySelector('.overlay')
    if (overlay) {
      overlay.remove();
      return;
    }
  }

  if (event.key === 'Delete') {
    const selectedRows = document.querySelectorAll('tr[id][selected]');
    if (selectedRows.length === 1) {
      openDeleteModal(selectedRows[0].id);
    }
  }
});


/**
 * Přepíná řazení tabulky podle zadaného klíče.
 * @param {string} key - Klíč pro řazení.
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
 * Zjišťuje, zda zaměstnanec odpovídá vyhledávacímu dotazu.
 * @param {Object} employee - Objekt zaměstnance.
 * @param {string} searchQuery - Hledaný dotaz.
 * @returns {boolean} - True pokud odpovídá.
 */
function isSearchedFor(employee, searchQuery) {
  if (!searchQuery) {
    return true;
  }

  const searchQueries = searchQuery.toLowerCase().trim().split(/\s+/);

  const id = employee.id.toLowerCase();
  const username = employee.username.toLowerCase();
  const email = employee.email.toLowerCase();
  const isAdmin = employee.is_admin ? 'ano' : 'ne';
  const createdBy = employee.created_by ? employee.created_by.toLowerCase() : '-'
  const createdAt = formatDateTimeISOToDisplay(employee.created_at);

  const employeeInfo = `
    ${id}
    ${username}
    ${email}
    ${isAdmin}
    ${createdAt}
  `;

  for (const query of searchQueries) {
    if (!query.includes('=')) {
      if (!employeeInfo.includes(query)) return false;
    }
    else {
      const searchKeyWord = query.split('=')[0];
      const search = query.split('=')[1];

      if (['id',
        'identifier']
        .includes(searchKeyWord)) {
        if (!id.includes(search)) return false;
      }
      else if (['username',
        'name',
        'zaměstnanec',
        'zamestnanec',
        'jméno',
        'jmeno',
        'uživatel',
        'uzivatel',
        'uživatelské_jméno',
        'uzivatelske_jmeno',
        'uživatelskéjméno',
        'uzivatelskejmeno']
        .includes(searchKeyWord)) {
        if (!username.includes(search)) return false;
      }
      else if (['email',
        'e-mail',
        'mail']
        .includes(searchKeyWord)) {
        if (!email.includes(search)) return false;
      }
      else if (['admin']
        .includes(searchKeyWord)) {
        if (!isAdmin.includes(search)) return false;
      }
      else if (['vytvořil',
        'vytvoril',
        'created_by',
        'createdby']
        .includes(searchKeyWord)) {
        if (!createdBy.includes(search)) return false;
      }
      else if (['vytvořen',
        'vytvoren',
        'created_at',
        'createdat']
        .includes(searchKeyWord)) {
        if (!createdAt.includes(search)) return false;
      }
      else {
        if (!employeeInfo.includes(query)) return false;
      }
    }

  }
  return true;
}


/**
 * Vykreslí řádky tabulky zaměstnanců podle aktuálních dat a filtru.
 * @returns {Promise<void>} - Vrací promise po vykreslení tabulky.
 */
async function renderTableRows() {
  const employees = await fetchEmployees().catch((er) => {
    employeeTableBody.innerHTML = `
      <th class="error-message" colspan="10">
        Nepovedlo se načíst zaměstnance.
      </th>
    `;
  });
  if (!employees) return;

  let rowsHTML = '';

  // const url = new URL(location);
  // const searchQuery = url.searchParams.get('search_query');
  const searchQuery = searchBar.value;

  let sortedEmployees;

  if (!orderBy.key) {
    sortedEmployees = employees;
  } else if (orderBy.key === 'created_at') {
    sortedEmployees = employees.toSorted((a, b) => {
      a = new Date(a[orderBy.key]);
      b = new Date(b[orderBy.key]);
      return (a - b) * orderBy.ascending ? 1 : -1;
    })
  } else {
    sortedEmployees = employees.toSorted((a, b) => {
      if (orderBy.key === 'is_admin') {
        a = a[orderBy.key] ? 'ano' : 'ne';
        b = b[orderBy.key] ? 'ano' : 'ne';
      } else {
        a = a[orderBy.key] ? a[orderBy.key].toLowerCase() : '';
        b = b[orderBy.key] ? b[orderBy.key].toLowerCase() : '';
      }
      return a.localeCompare(b) * (orderBy.ascending ? 1 : -1);
    })
  }

  let rowNumber = 1;
  sortedEmployees.forEach((employee) => {
    let isAdminHTML;

    if (employee.is_admin) {
      isAdminHTML = '<span class="badge yes">ANO</span>';
    } else {
      isAdminHTML = '<span class="badge no">NE</span>';
    }

    const createdAtHTML = formatDateTimeISOToDisplay(employee.created_at);
    // let createdByHTML = '-';
    // if (employee.created_by) {
    //   const createdByEmp = employees.find((emp) => { return emp.id === employee.created_by });
    //   createdByHTML = `<span data-direct-to="${employee.created_by}">${createdByEmp?.username || employee.created_by}</span>`
    // }

    if (!isSearchedFor(employee, searchQuery)) {
      return;
    }

    rowsHTML += `
      <tr id="${employee.id}">
        <td>${rowNumber}</td>
        <td class="username" title="${employee.username}">${employee.username}</td>
        <td class="email" title="${employee.email}">${employee.email}</td>
        <td>${isAdminHTML}</td>
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
    rowNumber += 1;
  })

  employeeTableBody.innerHTML = rowsHTML;

  markSelectedRows(employeeTableBody);
}


/**
 * Otevře modální okno pro přidání nového zaměstnance.
 */
function openAddEmployeeModal() {
  const html = `
    <header>
      <h2>Přidat zaměstnance</h2>
    </header>

    <form id="add-employee-form">
      <div class="form-row">
        <label for="add-username">Uživatelské jméno</label>
        <input id="add-username" name="username" type="text" placeholder="Uživatelské jméno" required/>
        <div id="add-employee-username-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="add-email">Email</label>
        <input id="add-email" name="email" type="email" placeholder="Email" required />
        <div id="add-employee-email-error" class="form-error"></div>
      </div>

      <div class="form-row password-form-row">
        <label for="add-password">Heslo</label>
        <input id="add-password" name="password" type="password" placeholder="Heslo" required/>

        <!-- SVG: vyplněné oko <-> přeškrtnuté oko.
          Přepíná se změnou třídy mezi "state-show" a "state-hide".
          Výchozí: state-hide -->
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" class="pw-eye state-hide"
          role="img" aria-hidden="true" focusable="false">
          <!-- vnější vyplněný tvar oka (stejný pro oba stavy) -->
          <path class="eye-shape" d="M1.5 12S5.5 5.5 12 5.5 22.5 12 22.5 12 18.5 18.5 12 18.5 1.5 12 1.5 12z" />

          <!-- stav zobrazit: bílý kruh duhovky s tmavým zorníkem -->
          <g class="g-show" aria-hidden="true">
            <!-- bílý kruh duhovky -->
            <circle cx="12" cy="12" r="4" fill="var(--contrast)" />
            <!-- tmavý zorník -->
            <circle cx="12" cy="12" r="2" fill="var(--fg)" />
          </g>

          <!-- stav skrýt: stejný kruh + zorník, s úhlopříčnou čárou přes celý ikon -->
          <g class="g-hide" aria-hidden="true">
            <!-- bílý kruh duhovky -->
            <circle cx="12" cy="12" r="4" fill="var(--contrast)" />
            <!-- tmavý zorník (s kruhem) -->
            <circle cx="12" cy="12" r="2" fill="var(--fg)" />

            <!-- diagonální čára -->
            <line class="slash" x1="6.4" y1="4.8" x2="18.4" y2="19.2" stroke="var(--contrast)" stroke-width="2" />
            <line class="slash" x1="5.2" y1="4.8" x2="17.2" y2="19.2" stroke="var(--fg)" stroke-width="2" />
          </g>
        </svg>

        <div id="add-employee-password-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label>Admin</label>
        <div id="add-is-admin-toggle" class="is-admin-toggle" data-state="no">
          <div class="track"></div>
          <div class="option no">Ne</div>
          <div class="option yes">Ano</div>
        </div>
        <div id="add-employee-is-admin-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="add-employee-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Vytvořit</button>
      </div>
    </form>
  `;

  openModal(html);
}


/**
 * Otevře modální okno pro úpravu zaměstnance.
 * @param {string} employeeId - ID zaměstnance k úpravě.
 * @returns {Promise<void>} - Vrací promise po otevření modalu.
 */
async function openEditModal(employeeId) {
  if (!employeeId) return;
  const employees = await fetchEmployees();
  if (!employees) return;
  const employee = employees.find(emp => emp.id === employeeId);
  if (!employee) return;

  const html = `
    <header>
      <h2>Upravit zaměstnance</h2>
    </header>

    <form id="edit-employee-form">
      <div class="form-row">
        <input id="edit-id" name="id" type="hidden" value="${escapeHTML(employee.id) || ''}" required readonly/>
      </div>

      <div class="form-row">
        <label for="edit-username">Uživatelské jméno</label>
        <input id="edit-username" name="username" type="text" placeholder="Uživatelské jméno" autocomplete="username" value="${escapeHTML(employee.username || '')}" required/>
        <div id="edit-employee-username-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="edit-email">Email</label>
        <input id="edit-email" name="email" type="email" placeholder="Email" autocomplete="email" value="${escapeHTML(employee.email || '')}" required />
        <div id="edit-employee-email-error" class="form-error"></div>
      </div>

      <div class="form-row password-form-row">
        <label for="edit-password">Heslo</label>
        <input id="edit-password" name="password" type="password" placeholder="Nechte prázdné, pokud neměníte heslo" />

        <!-- SVG: vyplněné oko <-> přeškrtnuté oko.
          Přepíná se změnou třídy mezi "state-show" a "state-hide".
          Výchozí: state-hide -->
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" class="pw-eye state-hide"
          role="img" aria-hidden="true" focusable="false">
          <!-- vnější vyplněný tvar oka (stejný pro oba stavy) -->
          <path class="eye-shape" d="M1.5 12S5.5 5.5 12 5.5 22.5 12 22.5 12 18.5 18.5 12 18.5 1.5 12 1.5 12z" />

          <!-- stav zobrazit: bílý kruh duhovky s tmavým zorníkem -->
          <g class="g-show" aria-hidden="true">
            <!-- bílý kruh duhovky -->
            <circle cx="12" cy="12" r="4" fill="var(--contrast)" />
            <!-- tmavý zorník -->
            <circle cx="12" cy="12" r="2" fill="var(--fg)" />
          </g>

          <!-- stav skrýt: stejný kruh + zorník, s úhlopříčnou čárou přes celý ikon -->
          <g class="g-hide" aria-hidden="true">
            <!-- bílý kruh duhovky -->
            <circle cx="12" cy="12" r="4" fill="var(--contrast)" />
            <!-- tmavý zorník (s kruhem) -->
            <circle cx="12" cy="12" r="2" fill="var(--fg)" />

            <!-- diagonální čára -->
            <line class="slash" x1="6.4" y1="4.8" x2="18.4" y2="19.2" stroke="var(--contrast)" stroke-width="2" />
            <line class="slash" x1="5.2" y1="4.8" x2="17.2" y2="19.2" stroke="var(--fg)" stroke-width="2" />
          </g>
        </svg>

        <div id="edit-employee-password-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label>Admin</label>
        <div id="edit-is-admin-toggle" class="is-admin-toggle" data-state="${employee.is_admin ? 'yes' : 'no'}">
          <div class="track"></div>
          <div class="option no">Ne</div>
          <div class="option yes">Ano</div>
        </div>
        <div id="edit-employee-is-admin-error" class="form-error"></div>
      </div>


      <div class="form-row">
        <div id="edit-employee-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="button" class="btn btn-delete open-delete-modal" data-employee-id="${employee.id}">Smazat</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;

  openModal(html);
}


/**
 * Otevře modální okno pro smazání zaměstnance.
 * @param {string} employeeId - ID zaměstnance ke smazání.
 * @returns {Promise<void>} - Vrací promise po otevření modalu.
 */
async function openDeleteModal(employeeId) {
  if (!employeeId) return;
  const employees = await fetchEmployees();
  if (!employees) return;
  const employee = employees.find(emp => emp.id === employeeId);
  if (!employee) return;

  const html = `
    <header>
      <h2 class="delete-form-text">Smazat zaměstnance</h2>
    </header>

    <form id="delete-employee-form">
      <div class="form-row">
        <input id="delete-id" name="id" type="hidden" value="${escapeHTML(String(employee.id) || '')}" required readonly/>
      </div>
      
      <div class="form-row">
        <div id="delete-username-label">Uživatelské jméno:</div>
        <input id="delete-username" value="${escapeHTML(employee.username || '-')}" disabled>
      </div>
      
      <div class="form-row">
        <div id="delete-email-label">Email:</div>
        <input id="delete-email" value="${escapeHTML(employee.email || '-')}" disabled>
      </div>

      <div class="form-row">
        <label>Admin</label>
        <div class="is-admin-toggle disabled" data-state="${employee.is_admin ? 'yes' : 'no'}">
          <div class="track"></div>
          <div class="option no">Ne</div>
          <div class="option yes">Ano</div>
        </div>
      </div>

      <div class="form-row">
        <div id="delete-employee-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="delete-confirm btn btn-delete">Smazat</button>
      </div>
    </form>
  `;

  openModal(html);
}


/**
 * Zobrazí chybové hlášky při přidávání zaměstnance.
 * @param {string} error - Chybová zpráva nebo kód chyby.
 */
function showAddErrors(error) {
  const usernameError = document.querySelector('#add-employee-username-error');
  const emailError = document.querySelector('#add-employee-email-error');
  const passwordError = document.querySelector('#add-employee-password-error');
  const generalError = document.querySelector('#add-employee-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const resStr = String(error);

  switch (resStr) {
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění provést změnu.');
      return;
    case 'username_taken':
      setErr(usernameError, 'Uživatelské jméno už má jiný uživatel.');
      return;
    case 'email_taken':
      setErr(emailError, 'E-mail už má jiný uživatel.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'missing_username':
      setErr(usernameError, 'Chybí uživatelské jméno.');
      return;
    case 'missing_email':
      setErr(emailError, 'Chybí email.');
      return;
    case 'missing_password':
      setErr(passwordError, 'Chybí heslo.');
      return;
    case 'invalid_email':
      setErr(emailError, 'Neplatný e-mail.');
      return;
    case 'internal_server_error':
      setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
      return;
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
      return;
    default:
      break;
  }

  const low = resStr.toLowerCase();

  if (low.includes('username must be at least')) {
    let limit = low.split('username must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(usernameError, `Minimální délka uživatelského jména je ${limit}.`);
    return;
  }
  if (low.includes('username must be at most')) {
    let limit = low.split('username must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(usernameError, `Maximální délka uživatelského jména je ${limit}.`);
    return;
  }
  if (low.includes('username must start and end with')) {
    const allowedChars = low.split('characters: ')[1];
    setErr(usernameError, `Uživatelské jméno musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (low.includes('username must not contain')) {
    setErr(usernameError, 'Uživatelské jméno nesmí obsahovat více speciálních znaků za sebou.');
    return;
  }
  if (low.includes('username must not be all numeric')) {
    setErr(usernameError, 'Uživatelské jméno nesmí obsahovat pouze čísla.');
    return;
  }
  if (low.includes('username must not contain the reserved words')) {
    const reservedWords = low.split('reserved words: ')[1];
    setErr(usernameError, `Uživatelské jméno nesmí obsahovat: ${reservedWords}`);
    return;
  }

  if (low.includes('invalid_email')) {
    setErr(emailError, 'Email není platný');
    return;
  }

  if (low.includes('password must be at least')) {
    let limit = low.split('password must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(passwordError, `Minimální délka hesla je ${limit}.`);
    return;
  }
  if (low.includes('password must not contain spaces or tabs')) {
    setErr(passwordError, 'Heslo nesmí obsahovat mezery nebo tabulátory.');
    return;
  }
  if (low.includes('uppercase')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jedno velké písmeno.');
    return;
  }
  if (low.includes('lowercase')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jedno malé písmeno.');
    return;
  }
  if (low.includes('digit')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jedno číslo.');
    return;
  }
  if (low.includes('special character')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jeden speciální znak (např. !@#$%).');
    return;
  }
  if (low.includes('too common')) {
    setErr(passwordError, 'Heslo je příliš jednoduché nebo běžné.');
    return;
  }
  if (low.includes('must not contain the username')) {
    setErr(passwordError, 'Heslo nesmí obsahovat uživatelské jméno.');
    return;
  }
  if (low.includes('must not contain the email local-part')) {
    setErr(passwordError, 'Heslo nesmí obsahovat část e-mailu před zavináčem.');
    return;
  }
  if (low.includes('repeated characters')) {
    setErr(passwordError, 'Heslo obsahuje příliš mnoho opakujících se znaků.');
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


/**
 * Zobrazí chybové hlášky při úpravě zaměstnance.
 * @param {string} error - Chybová zpráva nebo kód chyby.
 */
function showEditErrors(error) {
  const usernameError = document.querySelector('#edit-employee-username-error');
  const emailError = document.querySelector('#edit-employee-email-error');
  const passwordError = document.querySelector('#edit-employee-password-error');
  const generalError = document.querySelector('#edit-employee-general-error');

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
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění provést změnu.');
      return;
    case 'employee_not_found':
      setErr(generalError, 'Zaměstnanec nebyl nalezen.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí id zaměstnance.');
      return;
    case 'invalid_id':
      setErr(generalError, 'Id zaměstnance není validní.');
      return;
    case 'username_taken':
      setErr(usernameError, 'Uživatelské jméno už má jiný uživatel.');
      return;
    case 'email_taken':
      setErr(emailError, 'E-mail už má jiný uživatel.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'missing_username':
      setErr(usernameError, 'Chybí uživatelské jméno.');
      return;
    case 'missing_email':
      setErr(emailError, 'Chybí email.');
      return;
    case 'invalid_email':
      setErr(emailError, 'Neplatný e-mail.');
      return;
    case 'can_not_delete_last_admin':
      setErr(generalError, 'Nelze odendat práva admina poslednímu adminovi.');
      return;
    case 'internal_server_error':
      setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
      return;
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
      return;
    default:
      break;
  }

  if (errorStr.includes('username must be at least')) {
    let limit = errorStr.split('username must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(usernameError, `Minimální délka uživatelského jména je ${limit}.`);
    return;
  }
  if (errorStr.includes('username must be at most')) {
    let limit = errorStr.split('username must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(usernameError, `Maximální délka uživatelského jména je ${limit}.`);
    return;
  }
  if (errorStr.includes('username must start and end with')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(usernameError, `Uživatelské jméno musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('username must not contain')) {
    setErr(usernameError, 'Uživatelské jméno nesmí obsahovat více speciálních znaků za sebou.');
    return;
  }
  if (errorStr.includes('username must not be all numeric')) {
    setErr(usernameError, 'Uživatelské jméno nesmí obsahovat pouze čísla.');
    return;
  }
  if (errorStr.includes('username must not contain the reserved words')) {
    const reservedWords = errorStr.split('reserved words: ')[1];
    setErr(usernameError, `Uživatelské jméno nesmí obsahovat: ${reservedWords}`);
    return;
  }

  if (errorStr.includes('invalid_email')) {
    setErr(emailError, 'Email není platný');
    return;
  }

  if (errorStr.includes('password must be at least')) {
    let limit = errorStr.split('password must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(passwordError, `Minimální délka hesla je ${limit}.`);
    return;
  }
  if (errorStr.includes('password must not contain spaces or tabs')) {
    setErr(passwordError, 'Heslo nesmí obsahovat mezery nebo tabulátory.');
    return;
  }
  if (errorStr.includes('uppercase')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jedno velké písmeno.');
    return;
  }
  if (errorStr.includes('lowercase')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jedno malé písmeno.');
    return;
  }
  if (errorStr.includes('digit')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jedno číslo.');
    return;
  }
  if (errorStr.includes('special character')) {
    setErr(passwordError, 'Heslo musí obsahovat alespoň jeden speciální znak (např. !@#$%).');
    return;
  }
  if (errorStr.includes('too common')) {
    setErr(passwordError, 'Heslo je příliš jednoduché nebo běžné.');
    return;
  }
  if (errorStr.includes('must not contain the username')) {
    setErr(passwordError, 'Heslo nesmí obsahovat uživatelské jméno.');
    return;
  }
  if (errorStr.includes('must not contain the email local-part')) {
    setErr(passwordError, 'Heslo nesmí obsahovat část e-mailu před zavináčem.');
    return;
  }
  if (errorStr.includes('repeated characters')) {
    setErr(passwordError, 'Heslo obsahuje příliš mnoho opakujících se znaků.');
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


/**
 * Zobrazí chybové hlášky při mazání zaměstnance.
 * @param {string} error - Chybová zpráva nebo kód chyby.
 */
function showDeleteErrors(error) {
  const generalError = document.querySelector('#delete-employee-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const errorStr = String(error);
  switch (errorStr) {
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění provést změnu.');
      return;
    case 'employee_not_found':
      setErr(generalError, 'Zaměstnanec nebyl nalezen.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí id zaměstnance.');
      return;
    case 'invalid_id':
      setErr(generalError, 'Id zaměstnance není validní.');
      return;
    case 'can_not_delete_last_admin':
      setErr(generalError, 'Nelze smazat posledního admina.');
      return;
    case 'internal_server_error':
      setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
      return;
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


/**
 * Přidá nového zaměstnance pomocí API.
 * @param {FormData} formData - Data z formuláře.
 * @returns {Promise<Object|boolean>} - True při úspěchu, jinak objekt s chybou.
 */
async function addEmployee(formData) {
  try {
    const response = await fetch('/api/employees/create', {
      method: 'post',
      body: formData
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


/**
 * Upraví zaměstnance pomocí API.
 * @param {FormData} formData - Data z formuláře.
 * @returns {Promise<Object|boolean>} - True při úspěchu, jinak objekt s chybou.
 */
async function editEmployee(formData) {
  try {
    const response = await fetch('/api/employees/edit', {
      method: 'post',
      body: formData
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


/**
 * Smaže zaměstnance pomocí API.
 * @param {FormData} formData - Data z formuláře.
 * @returns {Promise<Object|boolean>} - True při úspěchu, jinak objekt s chybou.
 */
async function deleteEmployee(formData) {
  try {
    const response = await fetch('/api/employees/delete', {
      method: 'delete',
      body: formData
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
