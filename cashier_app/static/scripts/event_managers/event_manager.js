import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { formatDateTimeISOToDisplay, formatForDatetimeLocalInput, isValidDate } from "../general/date_utils.js";
import { directTo, handleCopyPasteUndoRedoOnKeydown, handleRowSelection, markSelectedRows, unselectRows } from "../general/table_utils.js";
import { fetchEmployees } from "../general/employees.js";
import { MissingEventIdError, UnauthorizedRedirectError } from "../general/errors.js";
import { changeSelectedCode, initValues, phoneInputClickListeners, phoneInputFocusinisteners, phoneInputInputisteners, phoneInputKeydownListeners, renderDropdown } from "../index/phone_number_input.js";
import { clearModalErrors, closeModal, openModal } from "../general/modals_forms.js";
import { fetchEventData as getEventDataOriginal, getEventIdFromPath, resetEventDataCache } from "../general/events.js";
import { handleUnauthorizedRedirect } from "../general/api_utils.js";


const card = document.querySelector('#card');

const boothsSearchBar = document.querySelector('#booths-search-bar');
const managersSearchBar = document.querySelector('#managers-search-bar');
const employeesSearchBar = document.querySelector('#employees-search-bar');
const productsSearchBar = document.querySelector('#products-search-bar');
const categoriesSearchBar = document.querySelector('#categories-search-bar');
const usersSearchBar = document.querySelector('#users-search-bar');
const walletsSearchBar = document.querySelector('#wallets-search-bar');

const boothsTableBody = document.querySelector('#booths-table tbody');
const managersTableBody = document.querySelector('#managers-table tbody');
const employeesTableBody = document.querySelector('#employees-table tbody');
const productsTableBody = document.querySelector('#products-table tbody');
const categoriesTableBody = document.querySelector('#categories-table tbody');
const usersTableBody = document.querySelector('#users-table tbody');
const walletsTableBody = document.querySelector('#wallets-table tbody');

// Multi-select: state stored per container element
const multiSelectState = new WeakMap();
const pendingMultiSelectStates = [];

let statsData = null;
let charts = {};

const orderBy = {
  booths: { key: '', ascending: true },
  managers: { key: '', ascending: true },
  employees: { key: '', ascending: true },
  products: { key: '', ascending: true },
  categories: { key: '', ascending: true },
  users: { key: '', ascending: true },
  wallets: { key: '', ascending: true }
};

const eventId = getEventIdFromPath();


/**
 * Načte data o akci ze serveru.
 * @returns {Promise<Object>} Data akce
 */
async function getEventData() {
  try {
    return await getEventDataOriginal();
  } catch (err) {
    let errorMessage = '';
    if (err instanceof MissingEventIdError) {
      errorMessage = 'Nelze určit ID akce z URL.';
    } else if (err instanceof UnauthorizedRedirectError) {
      errorMessage = 'Nejste admin nebo manažer akce.';
    } else {
      errorMessage = 'Nepovedlo se načíst akci';
    }
    const loadErrorMessage = card.querySelector('#load-error-message');
    if (loadErrorMessage) loadErrorMessage.remove();
    card.insertAdjacentHTML('afterbegin', `
      <div id="load-error-message" class="panel">
        ${escapeHTML(errorMessage)}
      </div>`);

    resetEventDataCache();
    throw new err;
  }
}



loadPage({
  eventInfo: true,
  header: true,
  sidebar: true,
  boothsTable: true,
  managersTable: true,
  employeesTable: true,
  productsTable: true,
  categoriesTable: true,
  usersTable: true,
  walletsTable: true,
  statistics: true
});


document.addEventListener('click', async (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) return;

  if (phoneInputClickListeners(event)) {
    return;
  }

  // upravit akci
  if (event.target.matches('#edit-event')) {
    await openEditEventModal();
    return;
  }

  // zobrazit historii transakcí akce
  if (event.target.matches('#view-event-transactions')) {
    window.open(`/events/${encodeURIComponent(eventId)}/transaction-history`, '_blank');
    return;
  }

  // smazat akci
  const deleteEventBtn = event.target.closest('#delete-event');
  if (deleteEventBtn) {
    openDeleteEventModal();
    return;
  }

  // přidat stánek
  if (event.target.matches('#add-booth')) {
    openAddBoothModal();
    return;
  }

  // přiřadit manažera
  if (event.target.matches('#add-manager')) {
    await openAssignEmployeeModal(true);
    return;
  }

  // přiřadit zaměstnance
  if (event.target.matches('#add-employee')) {
    await openAssignEmployeeModal(false);
    return;
  }

  // přidat produkt
  if (event.target.matches('#add-product')) {
    await openAddProductModal();
    return;
  }

  // přidat kategorii
  if (event.target.matches('#add-category')) {
    await openAddCategoryModal();
    return;
  }

  // přidat uživatele
  if (event.target.matches('#add-user')) {
    openAddUserModal();
    return;
  }

  // upravit stánek, zaměstnance (vrámci akce), produkt,...
  const editIcon = event.target.closest('.edit.icon-btn');
  if (editIcon) {
    const row = editIcon.closest('tr[id]');
    await openRowModal(row, 'edit');
    return;
  }

  // smazat stánek, produkt...
  const deleteIcon = event.target.closest('.delete.icon-btn');
  if (deleteIcon) {
    const row = deleteIcon.closest('tr[id]');
    await openRowModal(row, 'delete');
    return;
  }

  const openDeleteModalBtn = event.target.closest('.open-delete-modal');
  if (openDeleteModalBtn) {
    const toOpen = openDeleteModalBtn.getAttribute('data-modal-to-open');
    const targetId = openDeleteModalBtn.getAttribute('data-target-id');

    closeModal();

    if (toOpen === 'event') {
      openDeleteEventModal();
    } else if (toOpen === 'booth') {
      openDeleteBoothModal(targetId);
    } else if (toOpen === 'employee') {
      openRemoveEmployeeModal(targetId);
    } else if (toOpen === 'product') {
      openDeleteProductModal(targetId);
    } else if (toOpen === 'category') {
      openDeleteCategoryModal(targetId);
    } else if (toOpen === 'user') {
      openDeleteUserModal(targetId);
    }
    return;
  }

  // zobrazit transakce uživatele
  const viewUserTransactionsBtn = event.target.closest('.view-user-transactions');
  if (viewUserTransactionsBtn) {
    const userId = viewUserTransactionsBtn.getAttribute('data-user-id');
    window.open(`/events/${encodeURIComponent(eventId)}/users/${userId}/transaction-history`, '_blank');
    return;
  }


  const closeModalBtn = event.target.closest('.close-modal');
  if (closeModalBtn) {
    closeModal();
    return;
  }


  const panelHeader = event.target.closest('.panel-header');
  if (panelHeader && event.target.matches('h2, h3')) {
    if (event.target.closest('button, input, .search-icon-container')) return;

    const panel = panelHeader.closest('.panel');
    const tableWrap = panel.querySelector('.table-wrap, #statistics');

    tableWrap.classList.toggle('closed');
    return;
  }


  // klinutí na span v záhlaví
  // nastavuje řazení
  const headerEl = event.target.closest('th');
  if (headerEl && event.target.matches('span')) {
    setOrder(headerEl);
    return;
  }


  // kliknutí na element, který ukazuje na jinou řadu na stránce
  const clickedDirectEl = event.target.closest('span[data-direct-to]');
  if (clickedDirectEl) {
    directTo(clickedDirectEl, card)
    return;
  }


  // kliknutí na řádek ho vybere (musí být pod ostatníma, aby nebral kliknutí na jiné věci)
  const row = event.target.closest('tr[id]');
  if (row) {
    handleRowSelection(event);
    return;
  }

  const boothStatHeader = event.target.closest('.booth-stat-header');
  if (boothStatHeader) {
    toggleBoothProducts(boothStatHeader.getAttribute('data-booth-id'));
  }

  // Multi-select: handle tag removal
  const tagRemoveBtn = event.target.closest('.tag-remove');
  if (tagRemoveBtn) {
    event.preventDefault();
    const tag = tagRemoveBtn.closest('.multi-select-tag');
    const container = tag.closest('.multi-select-container');
    multiSelectToggleItem(container, tag.dataset.itemId);
    return;
  }

  // Multi-select: handle option click (toggle select/unselect)
  const msOption = event.target.closest('.multi-select-option');
  if (msOption) {
    event.preventDefault();
    const container = msOption.closest('.multi-select-container');
    multiSelectToggleItem(container, msOption.dataset.itemId);

    // Re-open dropdown (render resets innerHTML) and keep focus
    const dropdown = container.querySelector('.multi-select-dropdown');
    dropdown.classList.add('active');
    const input = container.querySelector('.multi-select-input');
    input.focus();
    return;
  }

  // Multi-select: close all dropdowns when clicking outside any multi-select
  const multiSelect = event.target.closest('.multi-select-container');
  const dropdown = multiSelect?.querySelector('.multi-select-dropdown');
  closeOtherMultiSelectDropdowns([dropdown]);

  if (event.target.matches('.search-bar') || document.querySelector('.modal')) {
    return;
  }
  // kliknutí na "nic" odvybere řádek
  unselectRows(card);
});


document.addEventListener('dblclick', async (event) => {
  const row = event.target.closest('tr[id]');
  if (row) {
    openRowModal(row, 'edit')
  }
});


document.addEventListener('submit', async (event) => {
  // EDIT EVENT FORM
  const editEventForm = event.target.closest('#edit-event-form');
  if (editEventForm) {
    event.preventDefault();
    const saveButton = editEventForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(editEventForm);

    const startAtStr = formData.get('start-at');
    const endAtStr = formData.get('end-at');

    const startAt = new Date(startAtStr);
    const endAt = new Date(endAtStr);

    if (startAtStr && !isValidDate(startAt)) {
      showEditEventErrors('invalid_start_at');
      saveButton.disabled = false;
      return;
    }
    if (endAtStr && !isValidDate(endAt)) {
      showEditEventErrors('invalid_end_at');
      saveButton.disabled = false;
      return;
    }

    if (startAtStr) {
      const startAtIsoUtc = startAt.toISOString();
      formData.set('start-at', startAtIsoUtc);
    }

    if (endAtStr) {
      const endAtIsoUtc = endAt.toISOString();
      formData.set('end-at', endAtIsoUtc);
    }

    formData.set('name', formData.get('name').trim());
    formData.set('id', eventId);

    try {
      const response = await fetch('/api/events/edit', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditEventErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();

      resetEventDataCache();
      loadPage({
        eventInfo: true,
        header: true
      });

    } catch (err) {
      showEditEventErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // DELETE EVENT FORM
  const deleteEventForm = event.target.closest('#delete-event-form');
  if (deleteEventForm) {
    event.preventDefault();
    const saveButton = deleteEventForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData();
    formData.set('id', eventId);

    try {
      const response = await fetch('/api/events/delete', {
        method: 'delete',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showDeleteEventErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();

      window.location.href = data.redirect_url;
      return;

    } catch (err) {
      showDeleteEventErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // ADD BOOTH FORM
  const addBoothForm = event.target.closest('#add-booth-form');
  if (addBoothForm) {
    event.preventDefault();
    const saveButton = addBoothForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(addBoothForm);
    formData.set('name', formData.get('name').trim());
    formData.set('event-id', eventId);

    try {
      const response = await fetch('/api/events/booths/create', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showAddBoothErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ boothsTable: true, productsTable: true, categoriesTable: true });

    } catch (err) {
      showAddBoothErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // EDIT BOOTH FORM
  const editBoothForm = event.target.closest('#edit-booth-form');
  if (editBoothForm) {
    event.preventDefault();
    const saveButton = editBoothForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(editBoothForm);
    formData.set('name', formData.get('name').trim());

    try {
      const response = await fetch('/api/events/booths/edit', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditBoothErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ boothsTable: true, employeesTable: true, productsTable: true, categoriesTable: true, header: true });

    } catch (err) {
      showEditBoothErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // DELETE BOOTH FORM
  const deleteBoothForm = event.target.closest('#delete-booth-form');
  if (deleteBoothForm) {
    event.preventDefault();
    const saveButton = deleteBoothForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(deleteBoothForm);

    try {
      const response = await fetch('/api/events/booths/delete', {
        method: 'delete',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showDeleteBoothErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ boothsTable: true, employeesTable: true, productsTable: true, categoriesTable: true, header: true });

    } catch (err) {
      showDeleteBoothErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // ASSIGN MANAGER/EMPLOYEE FORM
  const assignEmployeeForm = event.target.closest('#assign-employee-form');
  if (assignEmployeeForm) {
    event.preventDefault();
    const saveButton = assignEmployeeForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(assignEmployeeForm);
    formData.set('username-or-email', formData.get('username-or-email').trim());
    formData.set('event-id', eventId);

    const isManager = formData.get('is-manager') === 'true';

    try {
      const endpoint = isManager ? '/api/events/employees/assign-manager' : '/api/events/employees/assign-employee';
      const response = await fetch(endpoint, {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showAssignEmployeeErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ managersTable: true, employeesTable: true });

    } catch (err) {
      showAssignEmployeeErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // EDIT EMPLOYEE FORM
  const editEmployeeForm = event.target.closest('#edit-employee-form');
  if (editEmployeeForm) {
    event.preventDefault();
    const saveButton = editEmployeeForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(editEmployeeForm);
    formData.set('username-or-email', formData.get('username-or-email'));
    formData.set('event-id', eventId);

    try {
      const response = await fetch('/api/events/employees/assign-employee', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditEmployeeErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ employeesTable: true });

    } catch (err) {
      showEditEmployeeErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // REMOVE EMPLOYEE FORM
  const removeEmployeeForm = event.target.closest('#remove-employee-form');
  if (removeEmployeeForm) {
    event.preventDefault();
    const saveButton = removeEmployeeForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(removeEmployeeForm);
    formData.set('event-id', eventId);

    try {
      const response = await fetch('/api/events/employees/unassign', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showRemoveEmployeeErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ managersTable: true, employeesTable: true });

    } catch (err) {
      showRemoveEmployeeErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // ADD PRODUCT FORM
  const addProductForm = event.target.closest('#add-product-form');
  if (addProductForm) {
    event.preventDefault();
    const saveButton = addProductForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(addProductForm);
    formData.set('name', formData.get('name').trim());
    formData.set('event-id', eventId);

    try {
      const response = await fetch('/api/events/products/create', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showAddProductErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ productsTable: true, categoriesTable: true });

    } catch (err) {
      showAddProductErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // EDIT PRODUCT FORM
  const editProductForm = event.target.closest('#edit-product-form');
  if (editProductForm) {
    event.preventDefault();
    const saveButton = editProductForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(editProductForm);
    formData.set('name', formData.get('name').trim());

    try {
      const response = await fetch('/api/events/products/edit', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditProductErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ productsTable: true, categoriesTable: true });

    } catch (err) {
      showEditProductErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // DELETE PRODUCT FORM
  const deleteProductForm = event.target.closest('#delete-product-form');
  if (deleteProductForm) {
    event.preventDefault();
    const saveButton = deleteProductForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(deleteProductForm);

    try {
      const response = await fetch('/api/events/products/delete', {
        method: 'delete',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showDeleteProductErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ productsTable: true, categoriesTable: true });

    } catch (err) {
      showDeleteProductErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // ADD CATEGORY FORM
  const addCategoryForm = event.target.closest('#add-category-form');
  if (addCategoryForm) {
    event.preventDefault();
    const saveButton = addCategoryForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(addCategoryForm);
    formData.set('name', formData.get('name').trim());
    formData.set('event-id', eventId);

    try {
      const response = await fetch('/api/events/categories/create', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showAddCategoryErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ categoriesTable: true, productsTable: true });

    } catch (err) {
      showAddCategoryErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // EDIT CATEGORY FORM
  const editCategoryForm = event.target.closest('#edit-category-form');
  if (editCategoryForm) {
    event.preventDefault();
    const saveButton = editCategoryForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(editCategoryForm);
    formData.set('name', formData.get('name').trim());

    try {
      const response = await fetch('/api/events/categories/edit', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditCategoryErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ categoriesTable: true, productsTable: true });

    } catch (err) {
      showEditCategoryErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // DELETE CATEGORY FORM
  const deleteCategoryForm = event.target.closest('#delete-category-form');
  if (deleteCategoryForm) {
    event.preventDefault();
    const saveButton = deleteCategoryForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(deleteCategoryForm);

    try {
      const response = await fetch('/api/events/categories/delete', {
        method: 'delete',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showDeleteCategoryErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ categoriesTable: true, productsTable: true });

    } catch (err) {
      showDeleteCategoryErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // ADD USER FORM
  const addUserForm = event.target.closest('#add-user-form');
  if (addUserForm) {
    event.preventDefault();
    const saveButton = addUserForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(addUserForm);
    formData.set('first-name', formData.get('first-name').trim());
    formData.set('last-name', formData.get('last-name').trim());
    formData.set('email', formData.get('email').trim());
    formData.set('phone-number', formData.get('phone-number').trim());
    formData.set('other-identifier', formData.get('other-identifier').trim());

    try {
      const response = await fetch('/api/users/create', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showAddUserErrors(data.error || 'unexpected_error', data.detail);
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ usersTable: true, walletsTable: true });

    } catch (err) {
      showAddUserErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // EDIT USER FORM
  const editUserForm = event.target.closest('#edit-user-form');
  if (editUserForm) {
    event.preventDefault();
    const saveButton = editUserForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(editUserForm);
    formData.set('first-name', formData.get('first-name').trim());
    formData.set('last-name', formData.get('last-name').trim());
    formData.set('email', formData.get('email').trim());
    formData.set('phone-number', formData.get('phone-number').trim());
    formData.set('other-identifier', formData.get('other-identifier').trim());

    try {
      const response = await fetch('/api/users/edit', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditUserErrors(data.error || 'unexpected_error', data.detail);
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ usersTable: true, walletsTable: true });

    } catch (err) {
      showEditUserErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

  // DELETE USER FORM
  const deleteUserForm = event.target.closest('#delete-user-form');
  if (deleteUserForm) {
    event.preventDefault();
    const saveButton = deleteUserForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(deleteUserForm);

    try {
      const response = await fetch('/api/users/delete', {
        method: 'delete',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showDeleteUserErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();
      resetEventDataCache();
      loadPage({ usersTable: true, walletsTable: true });

    } catch (err) {
      showDeleteUserErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }
});


document.addEventListener('input', (event) => {
  // Multi-select: handle search/filter
  const multiSelectInput = event.target.closest('.multi-select-input');
  if (multiSelectInput) {
    const container = multiSelectInput.closest('.multi-select-container');
    const dropdown = container.querySelector('.multi-select-dropdown');
    dropdown.classList.add('active');
    renderMultiSelectDropdown(container);
    return;
  }

  const searchBar = event.target.closest('.search-bar');
  if (searchBar) {
    if (searchBar === boothsSearchBar) {
      loadPage({ boothsTable: true });
    } else if (searchBar === managersSearchBar) {
      loadPage({ managersTable: true });
    } else if (searchBar === employeesSearchBar) {
      loadPage({ employeesTable: true });
    } else if (searchBar === productsSearchBar) {
      loadPage({ productsTable: true });
    } else if (searchBar === categoriesSearchBar) {
      loadPage({ categoriesTable: true });
    } else if (searchBar === usersSearchBar) {
      loadPage({ usersTable: true });
    } else if (searchBar === walletsSearchBar) {
      loadPage({ walletsTable: true });
    }
  }

  phoneInputInputisteners(event);
});


document.addEventListener('keydown', (event) => {
  if (multiSelectKeydownHandler(event)) return;
  if (phoneInputKeydownListeners(event)) return;
  handleRowSelection(event);

  handleCopyPasteUndoRedoOnKeydown(event, eventId).then((result) => {
    if (['paste', 'undo', 'redo'].includes(result)) {
      resetEventDataCache();
      loadPage({
        eventInfo: true,
        header: true,
        sidebar: true,
        boothsTable: true,
        managersTable: true,
        employeesTable: true,
        productsTable: true,
        categoriesTable: true,
        usersTable: true,
        walletsTable: true
      });
    }
  });

  if (event.key === 'Enter' && !document.querySelector('.modal')) {
    const selectedRows = document.querySelectorAll('tr[selected]');
    if (selectedRows.length === 1) {
      const row = selectedRows[0];
      if (row) {
        openRowModal(row, 'edit');
      }
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
    const selectedRows = document.querySelectorAll('tr[selected]');
    if (selectedRows.length === 1) {
      const row = selectedRows[0];
      if (row) {
        openRowModal(row, 'delete');
      }
    }
  }
});


document.addEventListener('change', (event) => {
  const boothTypeSelect = event.target.closest('#booth-type-input')
  if (boothTypeSelect) {
    const productsRow = document.querySelector('#booth-products-row');
    const categoriesRow = document.querySelector('#booth-categories-row');
    const isSellerBooth = boothTypeSelect.value === 'seller';
    productsRow.style.display = isSellerBooth ? 'flex' : 'none';
    categoriesRow.style.display = isSellerBooth ? 'flex' : 'none';

    if (!isSellerBooth) {
      const productsMultiSelect = productsRow.querySelector('.multi-select-container');
      const categoriesMultiSelect = categoriesRow.querySelector('.multi-select-container');
      if (productsMultiSelect) multiSelectClearAll(productsMultiSelect);
      if (categoriesMultiSelect) multiSelectClearAll(categoriesMultiSelect);
    }
  }
});


document.addEventListener('focusin', (event) => {
  // Multi-select: show dropdown on focus
  const multiSelectInput = event.target.closest('.multi-select-input');
  if (multiSelectInput) {
    const container = multiSelectInput.closest('.multi-select-container');
    const dropdown = container.querySelector('.multi-select-dropdown');
    dropdown.classList.add('active');
    return;
  }

  phoneInputFocusinisteners(event);
});


async function loadPage({
  eventInfo = false,
  header = false,
  sidebar = false,
  boothsTable = false,
  managersTable = false,
  employeesTable = false,
  productsTable = false,
  categoriesTable = false,
  usersTable = false,
  walletsTable = false,
  statistics = false } = {}) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const toLoad = [];
  if (eventInfo) toLoad.push(renderEvent(eventData));
  if (header) toLoad.push(renderHeader());
  if (sidebar) toLoad.push(renderSidebar());
  if (boothsTable) toLoad.push(renderBooths(eventData));
  if (managersTable) toLoad.push(renderManagers(eventData));
  if (employeesTable) toLoad.push(renderEmployees(eventData));
  if (productsTable) toLoad.push(renderProducts(eventData));
  if (categoriesTable) toLoad.push(renderCategories(eventData));
  if (usersTable) toLoad.push(renderUsers(eventData));
  if (walletsTable) toLoad.push(renderWallets(eventData));
  if (statistics) toLoad.push(loadStatistics());
  await Promise.all(toLoad);
}


/**
 * Nastaví řazení tabulky podle kliknutého záhlaví.
 * @param {HTMLElement} headerEl - Element záhlaví tabulky
 */
function setOrder(headerEl) {
  const id = headerEl.id || '';

  switch (id) {
    case 'booths-name-header':
      toggleOrder(orderBy.booths, 'name', headerEl);
      break;
    case 'booths-booth_type-header':
      toggleOrder(orderBy.booths, 'booth_type', headerEl);
      break;
    case 'managers-username-header':
      toggleOrder(orderBy.managers, 'username', headerEl);
      break;
    case 'managers-email-header':
      toggleOrder(orderBy.managers, 'email', headerEl);
      break;
    case 'employees-username-header':
      toggleOrder(orderBy.employees, 'username', headerEl);
      break;
    case 'employees-email-header':
      toggleOrder(orderBy.employees, 'email', headerEl);
      break;
    case 'employees-booths-header':
      toggleOrder(orderBy.employees, 'booths', headerEl);
      break;
    case 'products-name-header':
      toggleOrder(orderBy.products, 'name', headerEl);
      break;
    case 'products-price-header':
      toggleOrder(orderBy.products, 'price', headerEl);
      break;
    case 'products-image_path-header':
      toggleOrder(orderBy.products, 'image_path', headerEl);
      break;
    case 'products-booths-header':
      toggleOrder(orderBy.products, 'booths', headerEl);
      break;
    case 'products-categories-header':
      toggleOrder(orderBy.products, 'categories', headerEl);
      break;
    case 'categories-name-header':
      toggleOrder(orderBy.categories, 'name', headerEl);
      break;
    case 'categories-booths-header':
      toggleOrder(orderBy.categories, 'booths', headerEl);
      break;
    case 'users-first-name-header':
      toggleOrder(orderBy.users, 'first_name', headerEl);
      break;
    case 'users-last-name-header':
      toggleOrder(orderBy.users, 'last_name', headerEl);
      break;
    case 'users-email-header':
      toggleOrder(orderBy.users, 'email', headerEl);
      break;
    case 'users-phone-header':
      toggleOrder(orderBy.users, 'phone_number', headerEl);
      break;
    case 'users-other-identifier-header':
      toggleOrder(orderBy.users, 'other_identifier', headerEl);
      break;
    case 'users-event-connected-header':
      toggleOrder(orderBy.users, 'event_connected', headerEl);
      break;
    case 'wallets-tag-id-header':
      toggleOrder(orderBy.wallets, 'tag_id', headerEl);
      break;
    case 'wallets-owner-header':
      toggleOrder(orderBy.wallets, 'owner_name', headerEl);
      break;
    case 'wallets-balance-header':
      toggleOrder(orderBy.wallets, 'balance_czk', headerEl);
      break;
  }

  const parentPanel = headerEl.closest('.panel');
  const panelId = parentPanel.id;

  switch (panelId) {
    case 'booths-panel':
      loadPage({ boothsTable: true });
      break;
    case 'managers-panel':
      loadPage({ managersTable: true });
      break;
    case 'employees-panel':
      loadPage({ employeesTable: true });
      break;
    case 'products-panel':
      loadPage({ productsTable: true });
      break;
    case 'categories-panel':
      loadPage({ categoriesTable: true });
      break;
    case 'users-panel':
      loadPage({ usersTable: true });
      break;
    case 'wallets-panel':
      loadPage({ walletsTable: true });
      break;
  }
}


/**
 * Přepne směr řazení a nastaví klíč pro řazení.
 * @param {Object} dict - Objekt s informací o řazení
 * @param {string} key - Klíč podle kterého se řadí
 * @param {HTMLElement} headerEl - Element záhlaví
 */
function toggleOrder(dict, key, headerEl) {
  if (dict.key !== key) {
    dict.key = key;
    dict.ascending = true;
  } else if (dict.ascending) {
    dict.ascending = false;
  } else {
    dict.key = '';
    dict.ascending = true;
  }

  const parentPanel = headerEl.closest('.panel');
  parentPanel.querySelectorAll('.order-by-arrow').forEach(el => el.remove());

  if (dict.key) {
    const orderByArrow = document.createElement('span');
    orderByArrow.classList.add('order-by-arrow');
    orderByArrow.innerHTML = dict.ascending ? '&#8595;' : '&#8593;';
    headerEl.querySelector('div').appendChild(orderByArrow);
  }
}


/**
 * Vytvoří funkci pro řazení podle zadaného klíče a směru.
 * @param {Object} dict - Objekt s klíčem a směrem řazení
 * @returns {Function} Funkce pro použití v sort
 */
function sorterFactory(dict) {
  const sorter = (a, b) => {
    if (!dict.key) return 0;
    const key = dict.key;
    let aValue = a[key] || '';
    let bValue = b[key] || '';

    if (key === 'booths') {
      aValue = aValue.map(booth => booth.name).join(', ').toLowerCase();
      bValue = bValue.map(booth => booth.name).join(', ').toLowerCase();
    } else if (key === 'categories') {
      aValue = aValue.map(category => category.name).join(', ').toLowerCase();
      bValue = bValue.map(category => category.name).join(', ').toLowerCase();
    } else if (key === 'booth_type') {
      aValue = boothTypeToDisplay(aValue).toLowerCase();
      bValue = boothTypeToDisplay(bValue).toLowerCase();
    } else if (key === 'price' || key === 'balance_czk') {
      return (Number(aValue) - Number(bValue)) * (dict.ascending ? 1 : -1);
    } else {
      aValue = String(aValue).toLowerCase();
      bValue = String(bValue).toLowerCase();
    }

    return aValue.localeCompare(bValue) * (dict.ascending ? 1 : -1);
  }

  return sorter
}


/**
 * Zjistí, zda stánek odpovídá hledanému dotazu.
 * @param {Object} booth - Objekt stánku
 * @param {string} searchQuery - Hledaný text
 * @returns {boolean}
 */
function boothIsSearchedFor(booth, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const name = String(booth.name || '').toLowerCase();
  const type = String(boothTypeToDisplay(booth.booth_type) || '').toLowerCase();

  const searchable = `${name} ${type}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');
      if (['name', 'stánek', 'stanek', 'booth', 'nazev', 'název'].includes(searchKeyWord)) {
        if (!name.includes(search)) return false;
      } else if (['type', 'typ', 'druh'].includes(searchKeyWord)) {
        if (!type.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}

/**
 * Zjistí, zda zaměstnanec odpovídá hledanému dotazu.
 * @param {Object} employee - Objekt zaměstnance
 * @param {string} searchQuery - Hledaný text
 * @returns {boolean}
 */
function employeeIsSearchedFor(employee, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const username = String(employee.username || '').toLowerCase();
  const email = String(employee.email || '').toLowerCase();
  let booths = employee.booths.length === 0 ? '-' : '';
  for (const booth of employee.booths) {
    booths += `${booth.name.toLowerCase()}, `;
  }

  const searchable = `${username} ${email} ${booths}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');

      if (['username',
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
        'uzivatelskejmeno',
        'manager',
        'manažer',
        'manazer'].includes(searchKeyWord)) {
        if (!username.includes(search)) return false;
      } else if (['email', 'e-mail', 'mail'].includes(searchKeyWord)) {
        if (!email.includes(search)) return false;
      } else if (!employee.isManager && ['stánek', 'stanek', 'booth', 'stánky', 'stanky', 'booths'].includes(searchKeyWord)) {
        if (!booths.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}


/**
 * Zjistí, zda produkt odpovídá hledanému dotazu.
 * @param {Object} product - Objekt produktu
 * @param {string} searchQuery - Hledaný text
 * @returns {boolean}
 */
function productIsSearchedFor(product, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const name = String(product.name || '').toLowerCase();
  const price = String(product.price || '').toLowerCase();
  const imageName = String(product.image_filename || '').toLowerCase();
  let categories = product.categories.length === 0 ? '-' : '';
  for (const category of product.categories) {
    categories += `${category.name.toLowerCase()}, `;
  }
  let booths = product.booths.length === 0 ? '-' : '';
  for (const booth of product.booths) {
    booths += `${booth.name.toLowerCase()} `;
  }

  const searchable = `${name} ${price} ${categories} ${booths}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');
      if (['name', 'produkt', 'product', 'nazev', 'název'].includes(searchKeyWord)) {
        if (!name.includes(search)) return false;
      } else if (['price', 'cena'].includes(searchKeyWord)) {
        if (!price.includes(search)) return false;
      } else if (['image', 'obrazek', 'obrázek'].includes(searchKeyWord)) {
        if (!imageName.includes(search)) return false;
      } else if (['kategorie', 'category', 'categories', 'druh'].includes(searchKeyWord)) {
        if (!categories.includes(search)) return false;
      } else if (['stánek', 'stanek', 'booth', 'stánky', 'stanky', 'booths'].includes(searchKeyWord)) {
        if (!booths.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}


/**
 * Zjistí, zda kategorie odpovídá hledanému dotazu.
 * @param {Object} category - Objekt kategorie
 * @param {string} searchQuery - Hledaný text
 * @returns {boolean}
 */
function categoryIsSearchedFor(category, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const name = String(category.name || '').toLowerCase();
  let booths = category.booths.length === 0 ? '-' : '';
  for (const booth of category.booths) {
    booths += `${booth.name.toLowerCase()} `;
  }

  const searchable = `${name} ${booths}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');
      if (['name', 'kategorie', 'category', 'categories', 'název', 'nazev'].includes(searchKeyWord)) {
        if (!name.includes(search)) return false;
      } else if (['stánek', 'stanek', 'booth', 'stánky', 'stanky', 'booths'].includes(searchKeyWord)) {
        if (!booths.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}


/**
 * Zjistí, zda uživatel odpovídá hledanému dotazu.
 * @param {Object} user - Objekt uživatele
 * @param {string} searchQuery - Hledaný text
 * @returns {boolean}
 */
function userIsSearchedFor(user, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const firstName = String(user.first_name || '').toLowerCase();
  const lastName = String(user.last_name || '').toLowerCase();
  const email = String(user.email || '-').toLowerCase();
  const phone = String(user.phone_number || '-').toLowerCase();
  const otherIdentifier = String(user.other_identifier || '-').toLowerCase();
  const eventConnected = user.event_connected ? 'ano' : 'ne';

  const searchable = `${firstName} ${lastName} ${email} ${phone} ${otherIdentifier} ${eventConnected}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');
      if (['first_name', 'firstname', 'jméno', 'jmeno'].includes(searchKeyWord)) {
        if (!firstName.includes(search)) return false;
      } else if (['last_name', 'lastname', 'příjmení', 'prijmeni'].includes(searchKeyWord)) {
        if (!lastName.includes(search)) return false;
      } else if (['email', 'e-mail', 'mail'].includes(searchKeyWord)) {
        if (!email.includes(search)) return false;
      } else if (['phone', 'phone_number', 'telefon', 'číslo', 'cislo'].includes(searchKeyWord)) {
        if (!phone.includes(search)) return false;
      } else if (['other_identifier', 'identifier', 'identifikátor', 'identifikator'].includes(searchKeyWord)) {
        if (!otherIdentifier.includes(search)) return false;
      } else if (['součástí', 'soucasti', 'connected', 'connected_to_event', 'soucastiakce', 'součástíakce', 'soucasti_akce', 'součástí_akce'].includes(searchKeyWord)) {
        if (!eventConnected.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}

/**
 * Zjistí, zda peněženka odpovídá hledanému dotazu.
 * @param {Object} wallet - Objekt peněženky
 * @param {string} searchQuery - Hledaný text
 * @returns {boolean}
 */
function walletIsSearchedFor(wallet, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const tagId = String(wallet.tag_id || '').toLowerCase();
  const ownerName = `${wallet.first_name || ''} ${wallet.last_name || ''}`.toLowerCase().trim();
  const balance = String(wallet.balance_czk || '').toLowerCase();

  const searchable = `${tagId} ${ownerName} ${balance}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');
      if (['tag_id', 'tagid', 'tag', 'id', 'karta', 'card'].includes(searchKeyWord)) {
        if (!tagId.includes(search)) return false;
      } else if (['owner', 'vlastník', 'vlastnik', 'name', 'jméno', 'jmeno'].includes(searchKeyWord)) {
        if (!ownerName.includes(search)) return false;
      } else if (['balance', 'zůstatek', 'zustatek'].includes(searchKeyWord)) {
        if (!balance.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}


/**
 * Vygeneruje HTML pro zobrazení stánků ve formě "pills".
 * @param {Array} booths - Pole stánků
 * @returns {string} HTML kód
 */
function belongingBoothsToDisplay(booths) {
  if (!booths.length) return '-';
  const pills = booths.map(booth =>
    `<span class="linked-pill" data-direct-to="${booth.id}" title="${escapeHTML(booth.name)}">${escapeHTML(booth.name)}</span>`
  ).join('');
  return `<div class="linked-pills">${pills}</div>`;
}


/**
 * Vygeneruje HTML pro zobrazení kategorií ve formě "pills".
 * @param {Array} categories - Pole kategorií
 * @returns {string} HTML kód
 */
function belongingCategoriesToDisplay(categories) {
  if (!categories.length) return '-';
  const pills = categories.map(category =>
    `<span class="linked-pill" data-direct-to="${category.id}" title="${escapeHTML(category.name)}">${escapeHTML(category.name)}</span>`
  ).join('');
  return `<div class="linked-pills">${pills}</div>`;
}


/**
 * Vrátí textový popis typu stánku.
 * @param {string} type - Typ stánku
 * @returns {string}
 */
function boothTypeToDisplay(type) {
  if (type === 'cashier') {
    return 'pokladna';
  } else if (type === 'seller') {
    return 'prodej';
  } else {
    return type;
  }
}


/**
 * Vykreslí informace o akci do stránky.
 * @param {Object} eventData - Data akce
 */
function renderEvent(eventData) {
  const event = eventData.event;
  if (!event) return;
  document.getElementById('event-name').textContent = `Akce: ${event.name}` || '-';
  const start = formatDateTimeISOToDisplay(event.start_at);
  const end = formatDateTimeISOToDisplay(event.end_at);
  document.querySelector('#event-start-at span').textContent = start;
  document.querySelector('#event-end-at span').textContent = end;
  document.getElementById('event-created-at').textContent = formatDateTimeISOToDisplay(event.created_at);
}


/**
 * Vykreslí tabulku stánků.
 * @param {Object} eventData - Data akce
 */
function renderBooths(eventData) {
  const searchQuery = boothsSearchBar.value;
  const sorter = sorterFactory(orderBy.booths);
  const sortedBooths = eventData.booths.toSorted(sorter);

  let rows = '';

  sortedBooths.forEach((booth, idx) => {
    if (!boothIsSearchedFor(booth, searchQuery)) return;

    rows += `
      <tr id="${booth.id}">
        <td>${idx + 1}</td>
        <td class="truncate-name" title="${escapeHTML(booth.name)}">${escapeHTML(booth.name)}</td>
        <td>${escapeHTML(boothTypeToDisplay(booth.booth_type))}</td>
        <td class="actions">
          <button class="icon-btn edit edit-booth">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete delete-booth">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  boothsTableBody.innerHTML = rows || `<tr><td class="muted" colspan="4">Žádné stánky.</td></tr>`;
  markSelectedRows(card);
}


/**
 * Vykreslí tabulku manažerů.
 * @param {Object} eventData - Data akce
 */
function renderManagers(eventData) {
  const searchQuery = managersSearchBar.value;
  const managers = eventData.employees.filter(employee => employee.isManager);

  const sorter = sorterFactory(orderBy.managers);
  const sortedManagers = managers.toSorted(sorter);

  let rows = '';

  sortedManagers.forEach((manager, idx) => {
    if (!employeeIsSearchedFor(manager, searchQuery)) return;

    rows += `
      <tr id="${manager.id}">
        <td>${idx + 1}</td>
        <td class="truncate-name" title="${escapeHTML(manager.username)}">${escapeHTML(manager.username)}</td>
        <td class="truncate-name" title="${escapeHTML(manager.email)}">${escapeHTML(manager.email)}</td>
        <td class="actions">
          <button class="icon-btn delete remove-employee">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  managersTableBody.innerHTML = rows || `<tr><td class="muted" colspan="4">Žádní manažeři.</td></tr>`;
  markSelectedRows(card);
}


/**
 * Vykreslí tabulku zaměstnanců.
 * @param {Object} eventData - Data akce
 */
function renderEmployees(eventData) {
  const searchQuery = employeesSearchBar.value;
  const employees = eventData.employees.filter(employee => !employee.isManager);

  const sorter = sorterFactory(orderBy.employees);
  const sortedEmployees = employees.toSorted(sorter);

  let rows = '';

  sortedEmployees.forEach((employee, idx) => {
    if (!employeeIsSearchedFor(employee, searchQuery)) return;
    const boothsStr = belongingBoothsToDisplay(employee.booths);

    rows += `
      <tr id="${employee.id}">
        <td>${idx + 1}</td>
        <td class="truncate-name" title="${escapeHTML(employee.username)}">${escapeHTML(employee.username)}</td>
        <td class="truncate-name" title="${escapeHTML(employee.email)}">${escapeHTML(employee.email)}</td>
        <td class="linked-pills-cell">${boothsStr}</td>
        <td class="actions">
          <button class="icon-btn edit edit-employee">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete remove-employee">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  employeesTableBody.innerHTML = rows || `<tr><td class="muted" colspan="4">Žádní zaměstnanci.</td></tr>`;
  markSelectedRows(card);
}

/**
 * Vykreslí tabulku produktů.
 * @param {Object} eventData - Data akce
 */
function renderProducts(eventData) {
  const searchQuery = productsSearchBar.value;
  const sorter = sorterFactory(orderBy.products);
  const sortedProducts = eventData.products.toSorted(sorter);

  let rows = '';

  sortedProducts.forEach((product, idx) => {
    if (!productIsSearchedFor(product, searchQuery)) return;
    const boothsStr = belongingBoothsToDisplay(product.booths);
    const categoriesStr = belongingCategoriesToDisplay(product.categories);
    let imageHTML;
    if (product.image_path) {
      imageHTML = `
        <div class="image-container table-image-container">
          <img class="product-image" title="${product.image_filename}" src="${product.image_path}">
        </div>
      `;
    } else {
      imageHTML = '';
    }

    rows += `
      <tr id="${product.id}">
        <td>${idx + 1}</td>
        <td class="truncate-name" title="${escapeHTML(product.name)}">${escapeHTML(product.name)}</td>
        <td>${escapeHTML(String(product.price))}</td>
        <td class="image-cell">${imageHTML}</td>
        <td class="linked-pills-cell">${boothsStr}</td>
        <td class="linked-pills-cell">${categoriesStr}</td>
        <td class="actions">
          <button class="icon-btn edit edit-product">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete delete-product">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  productsTableBody.innerHTML = rows || `<tr><td class="muted" colspan="7">Žádné produkty.</td></tr>`;
  markSelectedRows(card);
}


/**
 * Vykreslí tabulku kategorií.
 * @param {Object} eventData - Data akce
 */
function renderCategories(eventData) {
  const searchQuery = categoriesSearchBar.value;
  const sorter = sorterFactory(orderBy.categories);
  const sortedCategories = eventData.categories.toSorted(sorter);

  let rows = '';

  sortedCategories.forEach((category, idx) => {
    if (!categoryIsSearchedFor(category, searchQuery)) return;
    const boothsStr = belongingBoothsToDisplay(category.booths);

    rows += `
      <tr id="${category.id}">
        <td>${idx + 1}</td>
        <td class="truncate-name" title="${escapeHTML(category.name)}">${escapeHTML(category.name)}</td>
        <td class="linked-pills-cell">${boothsStr}</td>
        <td class="actions">
          <button class="icon-btn edit edit-category">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete delete-category">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  categoriesTableBody.innerHTML = rows || `<tr><td class="muted" colspan="4">Žádné kategorie.</td></tr>`;
  markSelectedRows(card);
}


/**
 * Vykreslí tabulku uživatelů.
 * @param {Object} eventData - Data akce
 */
function renderUsers(eventData) {
  const searchQuery = usersSearchBar.value;
  const sorter = sorterFactory(orderBy.users);
  const sortedUsers = eventData.users.toSorted(sorter);

  let rows = '';

  sortedUsers.forEach((user, idx) => {
    if (!userIsSearchedFor(user, searchQuery)) return;
    const eventConnectedText = user.event_connected ? 'Ano' : 'Ne';
    const eventConnectedClass = user.event_connected ? 'event-connected-yes' : 'event-connected-no';

    rows += `
      <tr id="${user.id}">
        <td>${idx + 1}</td>
        <td class="truncate-name" title="${escapeHTML(user.first_name)}">${escapeHTML(user.first_name)}</td>
        <td class="truncate-name" title="${escapeHTML(user.last_name)}">${escapeHTML(user.last_name)}</td>
        <td class="truncate-name" title="${escapeHTML(user.email || '-')}">${escapeHTML(user.email || '-')}</td>
        <td>${escapeHTML(user.phone_number || '-')}</td>
        <td class="truncate-name" title="${escapeHTML(user.other_identifier || '-')}">${escapeHTML(user.other_identifier || '-')}</td>
        <td><span class="${eventConnectedClass}">${eventConnectedText}</span></td>
        <td class="actions">
          <button class="icon-btn view view-user-transactions" data-user-id="${user.id}" title="Zobrazit transakce">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.4"/>
            </svg>
          </button>
          <button class="icon-btn edit edit-user">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete delete-user">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  usersTableBody.innerHTML = rows || `<tr><td class="muted" colspan="8">Žádní uživatelé.</td></tr>`;
  markSelectedRows(card);
}

/**
 * Vykreslí tabulku peněženek.
 * @param {Object} eventData - Data akce
 */
function renderWallets(eventData) {
  const searchQuery = walletsSearchBar.value;
  const sorter = sorterFactory(orderBy.wallets);

  const walletsWithOwnerName = eventData.wallets.map(w => ({
    ...w,
    owner_name: `${w.first_name || ''} ${w.last_name || ''}`.trim()
  }));

  const sortedWallets = walletsWithOwnerName.toSorted(sorter);

  let rows = '';

  sortedWallets.forEach((wallet, idx) => {
    if (!walletIsSearchedFor(wallet, searchQuery)) return;
    const ownerName = wallet.owner_name || '-';

    rows += `
      <tr id="${wallet.id}">
        <td>${idx + 1}</td>
        <td>${escapeHTML(wallet.tag_id)}</td>
        <td><span data-direct-to="${wallet.owner_id}">${escapeHTML(ownerName)}</span></td>
        <td>${formatNumber(wallet.balance_czk)} Kč</td>
        <td class="actions">
          <button class="icon-btn view view-user-transactions" data-user-id="${wallet.owner_id}" title="Zobrazit transakce">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              <circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="1.4"/>
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  walletsTableBody.innerHTML = rows || `<tr><td class="muted" colspan="5">Žádné peněženky.</td></tr>`;
  markSelectedRows(card);
}

/**
 * Formátuje číslo podle české lokalizace.
 * @param {number|string} num - Číslo
 * @returns {string}
 */
function formatNumber(num) {
  return Number(num || 0).toLocaleString('cs-CZ');
}


/**
 * Vykreslí multi-select komponentu v daném kontejneru.
 * @param {HTMLElement} container - Kontejner multi-selectu
 */
function renderMultiSelect(container) {
  const state = multiSelectState.get(container);
  if (!state) return;

  const input = container.querySelector('.multi-select-input');

  // Render tags (alphabetical order from sorted items)
  const tagsContainer = container.querySelector('.multi-select-tags');
  let tagsHTML = '';
  state.items.forEach(item => {
    if (!state.selectedIds.has(item.id)) return;
    tagsHTML += `
      <span class="multi-select-tag" data-item-id="${item.id}">
        <span class="tag-text">${escapeHTML(item.name)}</span>
        <button type="button" class="tag-remove" aria-label="Odebrat">\u00d7</button>
      </span>
    `;
  });
  tagsContainer.innerHTML = tagsHTML;

  // Render hidden inputs
  const hiddenContainer = container.querySelector('.multi-select-hidden-inputs');
  hiddenContainer.innerHTML = [...state.selectedIds]
    .map(id => `<input type="hidden" name="${state.name}" value="${id}" />`)
    .join('');

  // Render dropdown
  renderMultiSelectDropdown(container);
}


/**
 * Vykreslí dropdown pro multi-select.
 * @param {HTMLElement} container - Kontejner multi-selectu
 */
function renderMultiSelectDropdown(container) {
  const state = multiSelectState.get(container);
  if (!state) return;

  const input = container.querySelector('.multi-select-input');
  const searchValue = input ? input.value.toLowerCase() : '';
  const dropdown = container.querySelector('.multi-select-dropdown');

  let optionsHTML = '';

  if (state.items.length === 0) {
    optionsHTML = `<div class="multi-select-empty">${state.emptyMessage}</div>`;
  } else {
    let hasVisible = false;
    state.items.forEach(item => {
      const matches = !searchValue || item.name.toLowerCase().includes(searchValue);
      if (!matches) return;
      hasVisible = true;
      const isSelected = state.selectedIds.has(item.id);
      optionsHTML += `
        <div class="multi-select-option ${isSelected ? 'selected' : ''}" data-item-id="${item.id}" data-item-name="${escapeHTML(item.name)}">
          <span class="multi-select-option-name">${escapeHTML(item.name)}</span>
          <span class="multi-select-check">${isSelected ? '\u2713' : ''}</span>
        </div>
      `;
    });

    if (!hasVisible && searchValue) {
      optionsHTML = `<div class="multi-select-no-results">Žádné výsledky</div>`;
    }
  }

  dropdown.innerHTML = optionsHTML;
}


/**
 * Přepne výběr položky v multi-selectu.
 * @param {HTMLElement} container - Kontejner multi-selectu
 * @param {string|number} itemId - ID položky
 */
function multiSelectToggleItem(container, itemId) {
  const state = multiSelectState.get(container);
  if (!state) return;

  if (state.selectedIds.has(itemId)) {
    state.selectedIds.delete(itemId);
  } else {
    state.selectedIds.add(itemId);
  }

  // const input = container.querySelector('.multi-select-input');
  // input.value = '';
  renderMultiSelect(container);
}


/**
 * Zruší výběr všech položek v multi-selectu.
 * @param {HTMLElement} container - Kontejner multi-selectu
 */
function multiSelectClearAll(container) {
  const state = multiSelectState.get(container);
  if (!state) return;

  state.selectedIds.clear();
  renderMultiSelect(container);
}


/**
 * Zavře všechny aktivní dropdowny multi-selectu kromě zadaných.
 * @param {Array} dropdownsToNotClose - Dropdowny, které se nemají zavírat
 */
function closeOtherMultiSelectDropdowns(dropdownsToNotClose = []) {
  document.querySelectorAll('.multi-select-dropdown.active').forEach(dropdown => {
    if (dropdownsToNotClose.includes(dropdown)) return;
    dropdown.classList.remove('active');
  });
}


/**
 * Zpracuje klávesové události v multi-select inputu.
 * @param {KeyboardEvent} event
 * @returns {boolean}
 */
function multiSelectKeydownHandler(event) {
  const multiSelectInput = event.target.closest('.multi-select-input');
  if (!multiSelectInput) return false;

  const container = multiSelectInput.closest('.multi-select-container');
  const dropdown = container.querySelector('.multi-select-dropdown');

  // Escape: close dropdown
  if (event.key === 'Escape') {
    if (dropdown.classList.contains('active')) {
      dropdown.classList.remove('active');
      return true;
    }
    return false;
  }

  // Arrow Down / Arrow Up: navigate options
  let indexDirection;
  if (event.key === 'ArrowDown') indexDirection = 1;
  if (event.key === 'ArrowUp') indexDirection = -1;
  if (indexDirection) {
    event.preventDefault();
    dropdown.classList.add('active');

    const options = [...dropdown.querySelectorAll('.multi-select-option')];
    if (!options.length) return true;

    const activeOption = dropdown.querySelector('.multi-select-option.active');

    if (!activeOption) {
      const index = indexDirection === 1 ? 0 : options.length - 1;
      options[index].classList.add('active');
      options[index].scrollIntoView({ behavior: 'instant', block: 'nearest' });
      return true;
    }

    activeOption.classList.remove('active');
    const currentIndex = options.indexOf(activeOption);
    let nextIndex = currentIndex + indexDirection;
    if (nextIndex < 0) nextIndex = options.length - 1;
    if (nextIndex >= options.length) nextIndex = 0;
    options[nextIndex].classList.add('active');
    options[nextIndex].scrollIntoView({ behavior: 'instant', block: 'nearest' });
    return true;
  }

  // Enter: toggle active option
  if (event.key === 'Enter') {
    event.preventDefault();
    if (!dropdown.classList.contains('active')) return true;

    let activeOption = dropdown.querySelector('.multi-select-option.active');
    if (!activeOption) {
      const options = [...dropdown.querySelectorAll('.multi-select-option')];
      if (options.length === 1) {
        activeOption = options[0];
      } else {
        return true;
      }
    }

    multiSelectToggleItem(container, activeOption.dataset.itemId);
    // Re-open dropdown (render resets innerHTML)
    dropdown.classList.add('active');
    return true;
  }

  return false;
}


// Generates initial HTML for a multi-select and queues its state
/**
 * Vytvoří HTML pro multi-select s tagy a připraví jeho stav.
 * @param {Array} items - Položky k výběru
 * @param {Array} selectedItems - Předvybrané položky
 * @param {Object} config - Konfigurace
 * @returns {string} HTML kód
 */
function makeTagMultiSelect(items, selectedItems = [], config = {}) {
  const {
    name = 'items',
    label = 'Items',
    placeholder = 'Vyhledat...',
    emptyMessage = 'Žádné položky k dispozici.',
    filterFn = null
  } = config;

  let availableItems = items;
  if (filterFn) {
    availableItems = items.filter(filterFn);
  }

  const sortedItems = availableItems.toSorted((a, b) => a.name.localeCompare(b.name));
  const selectedIds = new Set(selectedItems.map(item => item.id));

  // Queue state to be attached after modal opens
  pendingMultiSelectStates.push({ items: sortedItems, selectedIds, name, emptyMessage });

  // Build initial tags HTML
  let tagsHTML = '';
  sortedItems.forEach(item => {
    if (!selectedIds.has(item.id)) return;
    tagsHTML += `
      <span class="multi-select-tag" data-item-id="${item.id}">
        <span class="tag-text">${escapeHTML(item.name)}</span>
        <button type="button" class="tag-remove" aria-label="Odebrat">\u00d7</button>
      </span>
    `;
  });

  // Build initial dropdown options HTML
  let optionsHTML = '';
  if (sortedItems.length === 0) {
    optionsHTML = `<div class="multi-select-empty">${emptyMessage}</div>`;
  } else {
    sortedItems.forEach(item => {
      const isSelected = selectedIds.has(item.id);
      optionsHTML += `
        <div class="multi-select-option ${isSelected ? 'selected' : ''}" data-item-id="${item.id}" data-item-name="${escapeHTML(item.name)}">
          <span class="multi-select-option-name">${escapeHTML(item.name)}</span>
          <span class="multi-select-check">${isSelected ? '\u2713' : ''}</span>
        </div>
      `;
    });
  }

  return `
    <div class="multi-select-container" data-multi-select-name="${name}">
      <label class="multi-select-label">${label}</label>
      <div class="multi-select-wrapper">
        <div class="multi-select-tags">
          ${tagsHTML}
        </div>
        <input
          type="text"
          class="multi-select-input"
          placeholder="${placeholder}"
          autocomplete="off"
        />
        <div class="multi-select-dropdown">
          ${optionsHTML}
        </div>
      </div>
      <div class="multi-select-hidden-inputs">
        ${[...selectedIds].map(id => `<input type="hidden" name="${name}" value="${id}" />`).join('')}
      </div>
    </div>
  `;
}


/**
 * Připojí připravené stavy multi-selectů do DOMu.
 */
function attachMultiSelectStates() {
  const containers = document.querySelectorAll('.multi-select-container');
  const unattached = [...containers].filter(c => !multiSelectState.has(c));
  unattached.forEach(container => {
    const state = pendingMultiSelectStates.shift();
    if (state) {
      multiSelectState.set(container, state);
    }
  });
}


/**
 * Vytvoří picker pro výběr stánků.
 * @param {Array} booths - Pole stánků
 * @param {Array} checkBooths - Předvybrané stánky
 * @param {string} boothType - Typ stánku
 * @returns {string} HTML kód
 */
function makeBoothsPicker(booths, checkBooths = [], boothType = 'all') {
  return makeTagMultiSelect(
    booths,
    checkBooths,
    {
      name: 'booths',
      label: 'Stánky',
      placeholder: 'Vyhledat stánek...',
      emptyMessage: 'Žádné stánky k dispozici.',
      filterFn: boothType === 'all' ? null : (booth) => booth.booth_type === boothType
    }
  );
}


/**
 * Vytvoří picker pro výběr kategorií.
 * @param {Array} categories - Pole kategorií
 * @param {Array} checkCategories - Předvybrané kategorie
 * @returns {string} HTML kód
 */
function makeCategoriesPicker(categories, checkCategories = []) {
  return makeTagMultiSelect(
    categories,
    checkCategories,
    {
      name: 'categories',
      label: 'Kategorie',
      placeholder: 'Vyhledat kategorii...',
      emptyMessage: 'Žádné kategorie k dispozici.'
    }
  );
}


/**
 * Vytvoří picker pro výběr produktů.
 * @param {Array} products - Pole produktů
 * @param {Array} checkProducts - Předvybrané produkty
 * @returns {string} HTML kód
 */
function makeProductsPicker(products, checkProducts = []) {
  return makeTagMultiSelect(
    products,
    checkProducts,
    {
      name: 'products',
      label: 'Produkty',
      placeholder: 'Vyhledat produkt...',
      emptyMessage: 'Žádné produkty k dispozici.'
    }
  );
}


async function openRowModal(row, type) {
  const parentTable = row.closest('table');
  const id = row.id;

  if (!['edit', 'delete'].includes(type)) {
    throw new Error('openRowModal type has to be edit or delete');
  }

  if (parentTable.id === 'booths-table') {
    if (type === 'edit') {
      await openEditBoothModal(id);
    } else if (type === 'delete') {
      await openDeleteBoothModal(id)
    }
    return;
  } else if (parentTable.id === 'managers-table') {
    if (type === 'edit') {
    } else if (type === 'delete') {
      await openRemoveEmployeeModal(id);
    }
    return;
  } else if (parentTable.id === 'employees-table') {
    if (type === 'edit') {
      await openEditEmployeeModal(id);
    } else if (type === 'delete') {
      await openRemoveEmployeeModal(id);
    }
    return;
  } else if (parentTable.id === 'products-table') {
    if (type === 'edit') {
      await openEditProductModal(id);
    } else if (type === 'delete') {
      await openDeleteProductModal(id)
    }
    return;
  } else if (parentTable.id === 'categories-table') {
    if (type === 'edit') {
      await openEditCategoryModal(id);
    } else if (type === 'delete') {
      await openDeleteCategoryModal(id)
    }
    return;
  } else if (parentTable.id === 'users-table') {
    if (type === 'edit') {
      await openEditUserModal(id);
    } else if (type === 'delete') {
      await openDeleteUserModal(id)
    }
    return;
  }
}


async function openEditEventModal() {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const event = eventData.event;
  if (!event) return;
  const html = `
    <header>
      <h2>Upravit akci</h2>
    </header>

    <form id="edit-event-form">
      <div class="form-row">
        <label for="event-name-input">Název</label>
        <input id="event-name-input" name="name" type="text" value="${escapeHTML(event.name || '')}"/>
        <div id="edit-event-name-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="event-start-input">Začátek</label>
        <input id="event-start-input" name="start-at" type="datetime-local" value="${event.start_at ? formatForDatetimeLocalInput(event.start_at) : ''}"/>
        <div id="edit-event-start-at-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="event-end-input">Konec</label>
        <input id="event-end-input" name="end-at" type="datetime-local" value="${event.end_at ? formatForDatetimeLocalInput(event.end_at) : ''}"/>
        <div id="edit-event-end-at-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="edit-event-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="button" class="btn btn-delete open-delete-modal" data-modal-to-open="event">Smazat</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;

  openModal(html);
  attachMultiSelectStates();
}


async function openDeleteEventModal() {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const event = eventData.event;
  if (!event) return;
  const html = `
    <header>
      <h2 class="delete-form-text">Smazat akci</h2>
    </header>

    <form id="delete-event-form">
      <div class="form-row">
        <div>Opravdu chcete smazat akci?</div>
      </div>

      <div class="form-row">
        <div id="delete-event-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-delete">Smazat</button>
      </div>
    </form>
  `;

  openModal(html);
  attachMultiSelectStates();
}


async function openAddBoothModal() {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;

  const products = eventData.products;
  const categories = eventData.categories;
  const productsPickerStr = makeProductsPicker(products);
  const categoriesPickerStr = makeCategoriesPicker(categories, []);

  const html = `
    <header>
      <h2>Přidat stánek</h2>
    </header>

    <form id="add-booth-form">
      <div class="form-row">
        <label for="booth-name-input">Název</label>
        <input id="booth-name-input" name="name" type="text"/>
        <div id="add-booth-name-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="booth-type-input">Typ</label>
        <select id="booth-type-input" name="type">
          <option value="seller">${boothTypeToDisplay('seller')}</option>
          <option value="cashier">${boothTypeToDisplay('cashier')}</option>
        </select>
        <div id="add-booth-type-error" class="form-error"></div>
      </div>
      
      <div class="form-row" id="booth-products-row">
        ${productsPickerStr}
        <div id="add-booth-products-error" class="form-error"></div>
      </div>
      
      <div class="form-row" id="booth-categories-row">
        ${categoriesPickerStr}
        <div id="add-booth-categories-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <div id="add-booth-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Vytvořit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();



  const boothTypeSelect = document.querySelector('#booth-type-input');
  const productsRow = document.querySelector('#booth-products-row');
  const categoriesRow = document.querySelector('#booth-categories-row');

  const isSellerBooth = boothTypeSelect.value === 'seller';
  productsRow.style.display = isSellerBooth ? 'flex' : 'none';
  categoriesRow.style.display = isSellerBooth ? 'flex' : 'none';

  if (!isSellerBooth) {
    productsRow.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
    categoriesRow.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
  }
}


async function openEditBoothModal(boothId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const booth = eventData.booths.find(booth => booth.id === boothId);
  if (!booth) return;

  let productsPickerStr = '';
  let categoriesPickerStr = '';

  if (booth.booth_type === 'seller') {
    const boothProducts = eventData.products.filter(p =>
      p.booths.some(b => b.id === boothId)
    );
    const boothCategories = eventData.categories.filter(c =>
      c.booths.some(b => b.id === boothId)
    );

    productsPickerStr = makeProductsPicker(eventData.products, boothProducts);
    categoriesPickerStr = makeCategoriesPicker(eventData.categories, boothCategories);
  }

  const html = `
    <header>
      <h2>Upravit stánek</h2>
    </header>
    <form id="edit-booth-form">
      <input type="hidden" name="id" value="${boothId}"/>
      
      <div class="form-row">
        <label for="booth-name-input">Název</label>
        <input id="booth-name-input" name="name" type="text" value="${escapeHTML(booth.name)}"/>
        <div id="edit-booth-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <label for="booth-type-display">Typ</label>
        <input id="booth-type-display" type="text" value="${escapeHTML(boothTypeToDisplay(booth.booth_type))}" disabled/>
        <div class="muted" style="font-size: 12px; margin-top: -2px;">Typ stánku nelze změnit po vytvoření</div>
      </div>
      
      <div class="form-row" id="booth-products-row">
        ${productsPickerStr}
        <div id="edit-booth-products-error" class="form-error"></div>
      </div>
      
      <div class="form-row" id="booth-categories-row">
        ${categoriesPickerStr}
        <div id="edit-booth-categories-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="edit-booth-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="button" class="btn btn-delete open-delete-modal" data-modal-to-open="booth" data-target-id="${booth.id}">Smazat</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();

  if (booth.booth_type === 'cashier') {
    const productsRow = document.querySelector('#booth-products-row');
    const categoriesRow = document.querySelector('#booth-categories-row');
    if (productsRow) productsRow.style.display = 'none';
    if (categoriesRow) categoriesRow.style.display = 'none';
  }
}


async function openDeleteBoothModal(boothId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const booth = eventData.booths.find(booth => booth.id === boothId);
  if (!booth) return;

  const html = `
    <header>
      <h2 class="delete-form-text">Smazat stánek</h2>
    </header>
    
    <form id="delete-booth-form">
      <input type="hidden" name="id" value="${boothId}"/>
      <div class="form-row">
        <div>Opravdu chcete smazat stánek "${escapeHTML(booth.name)}"?</div>
      </div>

      <div class="form-row">
        <div id="delete-booth-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-delete">Smazat</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openAssignEmployeeModal(assignManager) {
  const [eventData, allEmployees] = await Promise.all([
    getEventData().catch(() => { }),
    fetchEmployees().catch(() => { })
  ]);
  if (!eventData || !allEmployees) return;

  const booths = eventData.booths;

  const boothsPickerStr = assignManager ? '' : makeBoothsPicker(booths);

  const html = `
    <header>
      <h2>${assignManager ? 'Přiřadit manažera' : 'Přiřadit zaměstnance'}</h2>
    </header>

    <form id="assign-employee-form">
      <input type="hidden" name="is-manager" value="${assignManager}"/>
      
      <div class="form-row">
        <label for="emp-username-or-email-input">Uživatelské jméno nebo email</label>
        <input id="emp-username-or-email-input" name="username-or-email" type="text" list="employee-options" placeholder="Uživatelské jméno nebo email"/>
        <datalist id="employee-options">
          ${allEmployees.map(employee => `<option value="${employee.username}"></option><option value="${employee.email}"></option>`).join('')}
        </datalist>
        <div id="assign-employee-username-or-email-error" class="form-error"></div>
      </div>
      
      ${assignManager ? '' : `
      <div class="form-row">
        ${boothsPickerStr}
        <div id="assign-employee-booths-error" class="form-error"></div>
      </div>
      `}

      <div class="form-row">
        <div id="assign-employee-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Přiřadit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openEditEmployeeModal(employeeId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const emp = eventData.employees.find(employee => employee.id === employeeId);
  if (!emp) return;
  const boothsPickerStr = makeBoothsPicker(eventData.booths, emp.booths);

  const html = `
    <header>
      <h2>Upravit zaměstnance</h2>
    </header>
    
    <form id="edit-employee-form">
      <input type="hidden" name="username-or-email" value="${escapeHTML(emp.username)}"/>
      <div class="form-row">
        <label for="emp-username-input">Uživatel</label>
        <input id="emp-username-input" type="text" value="${escapeHTML(emp.username)}" disabled/>
      </div>
      <div class="form-row">
        ${boothsPickerStr}
        <div id="edit-employee-booths-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="edit-employee-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="button" class="btn btn-delete open-delete-modal" data-modal-to-open="employee" data-target-id="${emp.id}">Odebrat</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openRemoveEmployeeModal(employeeId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const emp = eventData.employees.find(employee => employee.id === employeeId);
  if (!emp) return;

  const html = `
    <header>
      <h2 class="delete-form-text">Odebrat ${emp.isManager ? 'manažera' : 'zaměstnance'}</h2>
    </header>

    <form id="remove-employee-form">
      <input type="hidden" name="id" value="${employeeId}"/>
      <div class="form-row">
        <div>Opravdu chcete odebrat ${emp.isManager ? 'manažera' : 'zaměstnance'} "${escapeHTML(emp.username)}" z této akce?</div>
      </div>

      <div class="form-row">
        <div id="remove-employee-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-delete">Odebrat</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openAddProductModal() {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const booths = eventData.booths;
  const categories = eventData.categories;
  const boothsPickerStr = makeBoothsPicker(booths, [], 'seller');
  const categoriesPickerStr = makeCategoriesPicker(categories, []);

  const html = `
    <header>
      <h2>Přidat produkt</h2>
    </header>

    <form id="add-product-form">
      <div class="form-row">
        <label for="product-name-input">Název</label>
        <input id="product-name-input" name="name" type="text"/>
        <div id="add-product-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <label for="product-price-input">Cena (Kč)</label>
        <input id="product-price-input" name="price" type="number" step="1"/>
        <div id="add-product-price-error" class="form-error"></div>
      </div>
      
      <div class="form-row image-form-row">
        <label for="product-image-input" class="image-upload-label">Obrázek</label>
        <input
          id="product-image-input"
          type="file"
          name="image"
          accept="image/jpeg,image/png,image/webp"/>
        <div id="add-product-image-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        ${boothsPickerStr}
        <div id="add-product-booths-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        ${categoriesPickerStr}
        <div id="add-product-categories-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="add-product-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Vytvořit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openEditProductModal(productId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const product = eventData.products.find(product => product.id === productId);
  if (!product) return;
  const boothsPickerStr = makeBoothsPicker(eventData.booths, product.booths, 'seller');
  const categoriesPickerStr = makeCategoriesPicker(eventData.categories, product.categories);

  let imageHTML;
  if (product.image_path) {
    imageHTML = `
      <div class="image-container edit-product-image-container">
        <img class="product-image" src="${product.image_path}">
      </div>
    `;
  } else {
    imageHTML = '-';
  }

  const html = `
    <header>
      <h2>Upravit produkt</h2>
    </header>

    <form id="edit-product-form">
      <input type="hidden" name="id" value="${productId}"/>

      <div class="form-row">
        <label for="product-name-input">Název</label>
        <input id="product-name-input" name="name" type="text" value="${escapeHTML(product.name)}"/>
        <div id="edit-product-name-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="product-price-input">Cena (Kč)</label>
        <input id="product-price-input" name="price" type="number" step="1" value="${escapeHTML(String(product.price))}"/>
        <div id="edit-product-price-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="product-image-input" class="image-upload-label">Změnit obrázek</label>
        <input
          id="product-image-input"
          type="file"
          name="image"
          accept="image/jpeg,image/png,image/webp"/>
        <div id="edit-product-image-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label class="remove-product-image-label">
          <input id="remove-product-image-input" type="checkbox" name="remove-curent-image"/>
          Odstranit aktuální obrázek
        </label>
        <div>
          ${imageHTML}
        </div>
      </div>

      <div class="form-row">
        ${boothsPickerStr}
        <div id="edit-product-booths-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        ${categoriesPickerStr}
        <div id="edit-product-categories-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="edit-product-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="button" class="btn btn-delete open-delete-modal" data-modal-to-open="product" data-target-id="${product.id}">Smazat</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openDeleteProductModal(productId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const product = eventData.products.find(product => product.id === productId);
  if (!product) return;

  const html = `
    <header>
      <h2 class="delete-form-text">Smazat produkt</h2>
    </header>
    
    <form id="delete-product-form">
      <input type="hidden" name="id" value="${productId}"/>
      <div class="form-row">
        <div>Opravdu chcete smazat produkt "${escapeHTML(product.name)}"?</div>
      </div>

      <div class="form-row">
        <div id="delete-product-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-delete">Smazat</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openAddCategoryModal() {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const booths = eventData.booths;
  const products = eventData.products;
  const boothsPickerStr = makeBoothsPicker(booths, [], 'seller');
  const productsPickerStr = makeProductsPicker(products);

  const html = `
    <header>
      <h2>Přidat kategorii</h2>
    </header>
    
    <form id="add-category-form">
      <div class="form-row">
        <label for="category-name-input">Název</label>
        <input id="category-name-input" name="name" type="text"/>
        <div id="add-category-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        ${boothsPickerStr}
        <div id="add-category-booths-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        ${productsPickerStr}
        <div id="add-category-products-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="add-category-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Vytvořit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openEditCategoryModal(categoryId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const category = eventData.categories.find(category => category.id === categoryId);
  if (!category) return;

  // Get products for this category
  const categoryProducts = eventData.products.filter(p =>
    p.categories.some(c => c.id === categoryId)
  );

  const boothsPickerStr = makeBoothsPicker(eventData.booths, category.booths, 'seller');
  const productsPickerStr = makeProductsPicker(eventData.products, categoryProducts);

  const html = `
    <header>
      <h2>Upravit kategorii</h2>
    </header>
    
    <form id="edit-category-form">
      <input type="hidden" name="id" value="${categoryId}"/>
      
      <div class="form-row">
        <label for="category-name-input">Název</label>
        <input id="category-name-input" name="name" type="text" value="${escapeHTML(category.name)}"/>
        <div id="edit-category-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        ${boothsPickerStr}
        <div id="edit-category-booths-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        ${productsPickerStr}
        <div id="edit-category-products-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="edit-category-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="button" class="btn btn-delete open-delete-modal" data-modal-to-open="category" data-target-id="${category.id}">Smazat</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openDeleteCategoryModal(categoryId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const category = eventData.categories.find(category => category.id === categoryId);
  if (!category) return;

  const html = `
    <header>
      <h2 class="delete-form-text">Smazat kategorii</h2>
    </header>
    
    <form id="delete-category-form">
      <input type="hidden" name="id" value="${categoryId}"/>
      <div class="form-row">
        <div>Opravdu chcete smazat kategorii "${escapeHTML(category.name)}"?</div>
      </div>

      <div class="form-row">
        <div id="delete-category-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-delete">Smazat</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


async function openAddUserModal() {
  const html = `
    <header>
      <h2>Přidat uživatele</h2>
    </header>
    
    <form id="add-user-form" autocomplete="off">
      <div class="form-row">
        <label for="user-first-name-input">Jméno</label>
        <input id="user-first-name-input" name="first-name" type="text"/>
        <div id="add-user-first-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <label for="user-last-name-input">Příjmení</label>
        <input id="user-last-name-input" name="last-name" type="text"/>
        <div id="add-user-last-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <label for="user-email-input">Email</label>
        <input id="user-email-input" name="email" type="email"/>
        <div id="add-user-email-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="user-phone-input">Telefonní číslo</label>
        <div class="phone-input-wrapper">
          <div class="country-code-container">
            <input type="text" id="country-code-input" name="phone-number-country-code">
            <!-- <div class="country-code-selector" tabindex="0">
              <span class="selected-code"></span>
            </div> -->
            <div class="country-code-dropdown">
              <!-- <div class="search-box">
                <input type="text" placeholder="Hledat zemi nebo kód..." class="search-input">
              </div> -->
              <div class="dropdown-content"></div>
            </div>
          </div>
          <input id="user-phone-input" class="user-phone-input" name="phone-number" type="tel" />
        </div>
        <div id="add-user-phone-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="user-other-identifier-input">Jiný identifikátor</label>
        <input id="user-other-identifier-input" name="other-identifier" type="text"/>
        <div id="add-user-other-identifier-error" class="form-error"></div>
      </div>
      <div class="form-row">
        <div class="muted">Vyplňte alespoň jeden z: email, telefon, jiný identifikátor</div>
      </div>

      <div class="form-row">
        <div id="add-user-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Vytvořit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();

  initValues();
  renderDropdown();
}

async function openEditUserModal(userId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const user = eventData.users.find(u => u.id === userId);
  if (!user) return;

  const html = `
    <header>
      <h2>Upravit uživatele</h2>
    </header>
    
    <form id="edit-user-form" autocomplete="off">
      <input type="hidden" name="user-id" value="${userId}"/>
      
      <div class="form-row">
        <label for="user-first-name-input">Jméno</label>
        <input id="user-first-name-input" name="first-name" type="text" value="${escapeHTML(user.first_name)}"/>
        <div id="edit-user-first-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <label for="user-last-name-input">Příjmení</label>
        <input id="user-last-name-input" name="last-name" type="text" value="${escapeHTML(user.last_name)}"/>
        <div id="edit-user-last-name-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <label for="user-email-input">Email</label>
        <input id="user-email-input" name="email" type="email" value="${escapeHTML(user.email || '')}"/>
        <div id="edit-user-email-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="user-phone-input">Telefonní číslo</label>
        <div class="phone-input-wrapper">
          <div class="country-code-container">
            <input type="text" id="country-code-input" name="phone-number-country-code">
            <!-- <div class="country-code-selector" tabindex="0">
              <span class="selected-code"></span>
            </div> -->
            <div class="country-code-dropdown">
              <!-- <div class="search-box">
                <input type="text" placeholder="Hledat zemi nebo kód..." class="search-input" value="${escapeHTML(user.phone_number_country_code || '')}>
              </div> -->
              <div class="dropdown-content"></div>
            </div>
          </div>
          <input id="user-phone-input" class="user-phone-input" name="phone-number" type="tel" value="${escapeHTML(user.phone_number_national_significant_number || '')}"/>
        </div>
        <div id="edit-user-phone-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="user-other-identifier-input">Jiný identifikátor</label>
        <input id="user-other-identifier-input" name="other-identifier" type="text" value="${escapeHTML(user.other_identifier || '')}"/>
        <div id="edit-user-other-identifier-error" class="form-error"></div>
      </div>
      
      <div class="form-row">
        <div class="muted">Vyplňte alespoň jeden z: email, telefon, jiný identifikátor</div>
      </div>

      <div class="form-row">
        <div id="edit-user-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="button" class="btn btn-delete open-delete-modal" data-modal-to-open="user" data-target-id="${user.id}">Smazat</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();

  initValues();
  changeSelectedCode(user.phone_number_country_code);
  renderDropdown();
}

async function openDeleteUserModal(userId) {
  const eventData = await getEventData().catch(() => { });
  if (!eventData) return;
  const user = eventData.users.find(u => u.id === userId);
  if (!user) return;

  const html = `
    <header>
      <h2 class="delete-form-text">Smazat uživatele</h2>
    </header>
    
    <form id="delete-user-form">
      <input type="hidden" name="user-id" value="${userId}"/>
      <div class="form-row">
        <div>Opravdu chcete smazat uživatele "${escapeHTML(user.first_name)} ${escapeHTML(user.last_name)}"?</div>
      </div>

      <div class="form-row">
        <div id="delete-user-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-delete">Smazat</button>
      </div>
    </form>
  `;
  openModal(html);
  attachMultiSelectStates();
}


// ERROR HANDLING FUNCTIONS


function showEditEventErrors(error) {
  const nameError = document.querySelector('#edit-event-name-error');
  const startAtError = document.querySelector('#edit-event-start-at-error');
  const endAtError = document.querySelector('#edit-event-end-at-error');
  const generalError = document.querySelector('#edit-event-general-error');

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
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění upravit akci.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'event_not_found':
      setErr(generalError, 'Akce nebyla pomocí ID nalezena.');
      return;
    case 'missing_name':
      setErr(nameError, 'Chybí název.');
      return;
    case 'invalid_start_at':
      setErr(startAtError, 'Zkuste začátek vybrat znovu.');
      return;
    case 'invalid_end_at':
      setErr(endAtError, 'Zkuste konec vybrat znovu.');
      return;
    case 'invalid_start_at_end_at_dates':
      setErr(generalError, 'Začátek musí být dříve než konec.');
      return;
    case 'event_name_taken':
      setErr(nameError, 'Název už má jiná akce.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Minimální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Maximální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must start and end with')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(nameError, `Název musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('name must not contain')) {
    setErr(nameError, 'Název nesmí obsahovat více speciálních znaků za sebou.');
    return;
  }
  if (errorStr.includes('name must not be all numeric')) {
    setErr(nameError, 'Název nesmí obsahovat pouze čísla.');
    return;
  }
  if (errorStr.includes('name must not contain the reserved words')) {
    const reservedWords = errorStr.split('reserved words: ')[1];
    setErr(nameError, `Název nesmí obsahovat: ${reservedWords}`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showDeleteEventErrors(error) {
  const generalError = document.querySelector('#delete-event-general-error');

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
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění smazat akci.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'event_not_found':
      setErr(generalError, 'Akce nebyla pomocí ID nalezena.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showAddBoothErrors(error) {
  const nameError = document.querySelector('#add-booth-name-error');
  const typeError = document.querySelector('#add-booth-type-error');
  const productsError = document.querySelector('#add-booth-products-error');
  const categoriesError = document.querySelector('#add-booth-categories-error');
  const generalError = document.querySelector('#add-booth-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění přidat stánek.');
      return;
    case 'invalid_event_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_event_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'missing_name':
      setErr(nameError, 'Chybí název.');
      return;
    case 'missing_type':
      setErr(typeError, 'Chybí typ.');
      return;
    case 'invalid_type':
      setErr(typeError, 'Neplatný typ.');
      return;
    case 'product_not_found':
      setErr(productsError, 'Jeden z produktů nebyl nalezen.');
      return;
    case 'invalid_product_id':
      setErr(productsError, 'ID produktu není správné.');
      return;
    case 'category_not_found':
      setErr(categoriesError, 'Jedna z kategorií nebyla nalezena.');
      return;
    case 'invalid_category_id':
      setErr(categoriesError, 'ID kategorie není správné.');
      return;
    case 'cashier_cannot_have_products_or_categories':
      setErr(generalError, 'Pokladna nemůže mít přiřazeny produkty nebo kategorie.');
      return;
    case 'booth_name_taken':
      setErr(nameError, 'Název už má jiný stánek v této akci.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Minimální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Maximální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must start and end with')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(nameError, `Název musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('name must not contain')) {
    setErr(nameError, 'Název nesmí obsahovat více speciálních znaků za sebou.');
    return;
  }
  if (errorStr.includes('name must not be all numeric')) {
    setErr(nameError, 'Název nesmí obsahovat pouze čísla.');
    return;
  }
  if (errorStr.includes('name must not contain the reserved words')) {
    const reservedWords = errorStr.split('reserved words: ')[1];
    setErr(nameError, `Název nesmí obsahovat: ${reservedWords}`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showEditBoothErrors(error) {
  const nameError = document.querySelector('#edit-booth-name-error');
  const productsError = document.querySelector('#edit-booth-products-error');
  const categoriesError = document.querySelector('#edit-booth-categories-error');
  const generalError = document.querySelector('#edit-booth-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění upravit stánek.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID stánku není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID stánku.');
      return;
    case 'booth_not_found':
      setErr(generalError, 'Stánek nebyl pomocí ID nalezen.');
      return;
    case 'missing_name':
      setErr(nameError, 'Chybí název.');
      return;
    case 'product_not_found':
      setErr(productsError, 'Jeden z produktů nebyl nalezen.');
      return;
    case 'invalid_product_id':
      setErr(productsError, 'ID produktu není správné.');
      return;
    case 'category_not_found':
      setErr(categoriesError, 'Jedna z kategorií nebyla nalezena.');
      return;
    case 'invalid_category_id':
      setErr(categoriesError, 'ID kategorie není správné.');
      return;
    case 'cashier_cannot_have_products_or_categories':
      setErr(generalError, 'Pokladna nemůže mít přiřazeny produkty nebo kategorie.');
      return;
    case 'booth_name_taken':
      setErr(nameError, 'Název už má jiný stánek v této akci.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Minimální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Maximální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must start and end with')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(nameError, `Název musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('name must not contain')) {
    setErr(nameError, 'Název nesmí obsahovat více speciálních znaků za sebou.');
    return;
  }
  if (errorStr.includes('name must not be all numeric')) {
    setErr(nameError, 'Název nesmí obsahovat pouze čísla.');
    return;
  }
  if (errorStr.includes('name must not contain the reserved words')) {
    const reservedWords = errorStr.split('reserved words: ')[1];
    setErr(nameError, `Název nesmí obsahovat: ${reservedWords}`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showDeleteBoothErrors(error) {
  const generalError = document.querySelector('#delete-booth-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění smazat stánek.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID stánku není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID stánku.');
      return;
    case 'booth_not_found':
      setErr(generalError, 'Stánek nebyl pomocí ID nalezen.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showAssignEmployeeErrors(error) {
  const usernameOrEmailError = document.querySelector('#assign-employee-username-or-email-error');
  const boothsError = document.querySelector('#assign-employee-booths-error');
  const generalError = document.querySelector('#assign-employee-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění přiřadit zaměstnance.');
      return;
    case 'invalid_event_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_event_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'missing_username_or_email':
      setErr(usernameOrEmailError, 'Chybí uživatelské jméno nebo email.');
      return;
    case 'event_not_found':
      setErr(generalError, 'Akce nebyla nalezena.');
      return;
    case 'employee_not_found':
      setErr(usernameOrEmailError, 'Zaměstnanec nebyl nalezen.');
      return;
    case 'can_not_assign_admin':
      setErr(generalError, 'Nelze přiřadit admina.');
      return;
    case 'booth_not_found':
      setErr(boothsError, 'Jeden ze stánků nebyl nalezen.');
      return;
    case 'invalid_booth_id':
      setErr(boothsError, 'ID stánku není správné.');
      return;
    case 'can_not_assign_manager_to_booths':
      setErr(generalError, 'Nelze přiřadit manažera ke stánkům.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showEditEmployeeErrors(error) {
  const boothsError = document.querySelector('#edit-employee-booths-error');
  const generalError = document.querySelector('#edit-employee-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění upravit zaměstnance.');
      return;
    case 'invalid_event_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_event_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'missing_username_or_email':
      setErr(generalError, 'Chybí uživatelské jméno nebo email.');
      return;
    case 'event_not_found':
      setErr(generalError, 'Akce nebyla nalezena.');
      return;
    case 'employee_not_found':
      setErr(generalError, 'Zaměstnanec nebyl nalezen.');
      return;
    case 'can_not_assign_admin':
      setErr(generalError, 'Nelze upravit admina.');
      return;
    case 'booth_not_found':
      setErr(boothsError, 'Jeden ze stánků nebyl nalezen.');
      return;
    case 'invalid_booth_id':
      setErr(boothsError, 'ID stánku není správné.');
      return;
    case 'can_not_assign_manager_to_booths':
      setErr(generalError, 'Nelze přiřadit manažera ke stánkům.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showRemoveEmployeeErrors(error) {
  const generalError = document.querySelector('#remove-employee-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění odebrat zaměstnance.');
      return;
    case 'invalid_event_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_event_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID zaměstnance není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID zaměstnance.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showAddProductErrors(error) {
  const nameError = document.querySelector('#add-product-name-error');
  const priceError = document.querySelector('#add-product-price-error');
  const imageError = document.querySelector('#add-product-image-error');
  const boothsError = document.querySelector('#add-product-booths-error');
  const categoriesError = document.querySelector('#add-product-categories-error');
  const generalError = document.querySelector('#add-product-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění přidat produkt.');
      return;
    case 'invalid_event_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_event_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'event_not_found':
      setErr(generalError, 'Akce nebyla nalezena.');
      return;
    case 'missing_name':
      setErr(nameError, 'Chybí název.');
      return;
    case 'missing_price':
      setErr(priceError, 'Chybí cena.');
      return;
    case 'booth_not_found':
      setErr(boothsError, 'Jeden ze stánků nebyl nalezen.');
      return;
    case 'invalid_booth_id':
      setErr(boothsError, 'ID stánku není správné.');
      return;
    case 'category_not_found':
      setErr(categoriesError, 'Jedna z kategorií nebyla nalezena.');
      return;
    case 'invalid_category_id':
      setErr(categoriesError, 'ID kategorie není správné.');
      return;
    case 'file_too_large':
      setErr(imageError, 'Soubor je příliš velký.');
      return;
    case 'disallowed_image_extension':
      setErr(imageError, 'Nepodporovaný formát obrázku.');
      return;
    case 'image_file_is_invalid':
      setErr(imageError, 'Soubor obrázku není validní.');
      return;
    case 'unable_to_save_file':
      setErr(imageError, 'Nepodařilo se uložit soubor.');
      return;
    case 'product_name_taken':
      setErr(nameError, 'Název už má jiný produkt.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Minimální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Maximální délka názvu je ${limit}.`);
    return;
  }

  if (errorStr.includes('price must be a number') || errorStr.includes('price must be a whole number') || errorStr.includes('price must be positive')) {
    setErr(priceError, 'Cena musí být celé číslo.');
    return;
  } else if (errorStr.includes('price must be a number')) {
    setErr(priceError, 'Cena musí být celé číslo.');
    return;
  } if (errorStr.includes('price must be more than or equal to')) {
    let limit = errorStr.split('price must be more than or equal to ')[1];
    setErr(priceError, `Minimální cena je ${limit}.`);
    return;
  } if (errorStr.includes('price must be less than or equal to')) {
    let limit = errorStr.split('price must be less than or equal to ')[1];
    setErr(priceError, `Maximální cena je ${limit}.`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showEditProductErrors(error) {
  const nameError = document.querySelector('#edit-product-name-error');
  const priceError = document.querySelector('#edit-product-price-error');
  const imageError = document.querySelector('#edit-product-image-error');
  const boothsError = document.querySelector('#edit-product-booths-error');
  const categoriesError = document.querySelector('#edit-product-categories-error');
  const generalError = document.querySelector('#edit-product-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění upravit produkt.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID produktu není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID produktu.');
      return;
    case 'product_not_found':
      setErr(generalError, 'Produkt nebyl pomocí ID nalezen.');
      return;
    case 'missing_name':
      setErr(nameError, 'Chybí název.');
      return;
    case 'missing_price':
      setErr(priceError, 'Chybí cena.');
      return;
    case 'booth_not_found':
      setErr(boothsError, 'Jeden ze stánků nebyl nalezen.');
      return;
    case 'invalid_booth_id':
      setErr(boothsError, 'ID stánku není správné.');
      return;
    case 'category_not_found':
      setErr(categoriesError, 'Jedna z kategorií nebyla nalezena.');
      return;
    case 'invalid_category_id':
      setErr(categoriesError, 'ID kategorie není správné.');
      return;
    case 'file_too_large':
      setErr(imageError, 'Soubor je příliš velký.');
      return;
    case 'disallowed_image_extension':
      setErr(imageError, 'Nepodporovaný formát obrázku.');
      return;
    case 'image_file_is_invalid':
      setErr(imageError, 'Soubor obrázku není validní.');
      return;
    case 'unable_to_save_file':
      setErr(imageError, 'Nepodařilo se uložit soubor.');
      return;
    case 'product_name_taken':
      setErr(nameError, 'Název už má jiný produkt.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Minimální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Maximální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must start and end with')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(nameError, `Název musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('name must not contain')) {
    setErr(nameError, 'Název nesmí obsahovat více speciálních znaků za sebou.');
    return;
  }
  if (errorStr.includes('name must not be all numeric')) {
    setErr(nameError, 'Název nesmí obsahovat pouze čísla.');
    return;
  }
  if (errorStr.includes('name must not contain the reserved words')) {
    const reservedWords = errorStr.split('reserved words: ')[1];
    setErr(nameError, `Název nesmí obsahovat: ${reservedWords}`);
    return;
  }

  if (errorStr.includes('price must be a number') || errorStr.includes('price must be a whole number') || errorStr.includes('price must be positive')) {
    setErr(priceError, 'Cena musí být celé číslo.');
    return;
  } else if (errorStr.includes('price must be a number')) {
    setErr(priceError, 'Cena musí být celé číslo.');
    return;
  } if (errorStr.includes('price must be more than or equal to')) {
    let limit = errorStr.split('price must be more than or equal to ')[1];
    setErr(priceError, `Minimální cena je ${limit}.`);
    return;
  } if (errorStr.includes('price must be less than or equal to')) {
    let limit = errorStr.split('price must be less than or equal to ')[1];
    setErr(priceError, `Maximální cena je ${limit}.`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showDeleteProductErrors(error) {
  const generalError = document.querySelector('#delete-product-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění smazat produkt.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID produktu není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID produktu.');
      return;
    case 'product_not_found':
      setErr(generalError, 'Produkt nebyl pomocí ID nalezen.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showAddCategoryErrors(error) {
  const nameError = document.querySelector('#add-category-name-error');
  const boothsError = document.querySelector('#add-category-booths-error');
  const productsError = document.querySelector('#add-category-products-error');
  const generalError = document.querySelector('#add-category-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění přidat kategorii.');
      return;
    case 'invalid_event_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'missing_event_id':
      setErr(generalError, 'Chybí ID akce.');
      return;
    case 'event_not_found':
      setErr(generalError, 'Akce nebyla nalezena.');
      return;
    case 'missing_name':
      setErr(nameError, 'Chybí název.');
      return;
    case 'booth_not_found':
      setErr(boothsError, 'Jeden ze stánků nebyl nalezen.');
      return;
    case 'invalid_booth_id':
      setErr(boothsError, 'ID stánku není správné.');
      return;
    case 'product_not_found':
      setErr(productsError, 'Jeden z produktů nebyl nalezen.');
      return;
    case 'invalid_product_id':
      setErr(productsError, 'ID produktu není správné.');
      return;
    case 'category_name_taken':
      setErr(nameError, 'Název už má jiná kategorie.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Minimální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Maximální délka názvu je ${limit}.`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showEditCategoryErrors(error) {
  const nameError = document.querySelector('#edit-category-name-error');
  const boothsError = document.querySelector('#edit-category-booths-error');
  const productsError = document.querySelector('#edit-category-products-error');
  const generalError = document.querySelector('#edit-category-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění upravit kategorii.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID kategorie není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID kategorie.');
      return;
    case 'category_not_found':
      setErr(generalError, 'Kategorie nebyla pomocí ID nalezena.');
      return;
    case 'missing_name':
      setErr(nameError, 'Chybí název.');
      return;
    case 'booth_not_found':
      setErr(boothsError, 'Jeden ze stánků nebyl nalezen.');
      return;
    case 'invalid_booth_id':
      setErr(boothsError, 'ID stánku není správné.');
      return;
    case 'product_not_found':
      setErr(productsError, 'Jeden z produktů nebyl nalezen.');
      return;
    case 'invalid_product_id':
      setErr(productsError, 'ID produktu není správné.');
      return;
    case 'category_name_taken':
      setErr(nameError, 'Název už má jiná kategorie.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Minimální délka názvu je ${limit}.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ');
    limit = limit[1].split(' characters')[0];
    setErr(nameError, `Maximální délka názvu je ${limit}.`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showDeleteCategoryErrors(error) {
  const generalError = document.querySelector('#delete-category-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění smazat kategorii.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID kategorie není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID kategorie.');
      return;
    case 'category_not_found':
      setErr(generalError, 'Kategorie nebyla pomocí ID nalezena.');
      return;
    default:
      break;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}


function showAddUserErrors(error, detail) {
  const firstNameError = document.querySelector('#add-user-first-name-error');
  const lastNameError = document.querySelector('#add-user-last-name-error');
  const emailError = document.querySelector('#add-user-email-error');
  const phoneError = document.querySelector('#add-user-phone-error');
  const otherIdentifierError = document.querySelector('#add-user-other-identifier-error');
  const generalError = document.querySelector('#add-user-general-error');

  let nameErrorEl = generalError;
  let nameStr = 'Jméno nebo příjmení';
  if (detail === 'first_name_error') {
    nameErrorEl = firstNameError;
    nameStr = 'Jméno';
  } else if (detail === 'last_name_error') {
    nameErrorEl = lastNameError;
    nameStr = 'Příjmení';
  }

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění přidat uživatele.');
      return;
    case 'missing_first_name':
      setErr(firstNameError, 'Chybí jméno.');
      return;
    case 'missing_last_name':
      setErr(lastNameError, 'Chybí příjmení.');
      return;
    case 'missing_country_code':
      setErr(phoneError, 'Chybí předčíslí.');
      return;
    case 'invalid_phone_number':
      setErr(phoneError, 'Telefonní číslo není platné.');
      return;
    case 'at_least_one_of_email_phone_number_other_identifier_is_required':
      setErr(generalError, 'Vyplňte alespoň jeden z: email, telefonní číslo, jiný identifikátor.');
      return;
    case 'user_email_taken':
      setErr(emailError, 'Email už má jiný uživatel.');
      return;
    case 'user_identifier_taken':
      setErr(generalError, 'Uživatel se stejnými údaji už existuje.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }


  if (errorStr.includes('name must be a string')) {
    setErr(nameErrorEl, `${nameStr} není správně zadané.`);
    return;
  }
  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ')[1].split(' characters')[0];
    setErr(nameErrorEl, `${nameStr} může mít minimálně ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ')[1].split(' characters')[0];
    setErr(nameErrorEl, `${nameStr} může mít maximálně ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('name may only contain letters, digits, and these characters:')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(nameErrorEl, `${nameStr} může obsahovat pouze písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('name must not be all numeric')) {
    setErr(nameErrorEl, `${nameStr} nesmí obsahovat pouze čísla.`);
    return;
  }
  if (errorStr.includes('name must not contain the reserved word:')) {
    const reservedWord = errorStr.split('reserved word: ')[1];
    setErr(nameErrorEl, `${nameStr} nesmí obsahovat: ${reservedWord}`);
    return;
  }


  if (errorStr.includes('email must be a string')) {
    setErr(emailError, 'Email není správně zadaný.');
    return;
  }
  if (errorStr.includes('email is empty')) {
    setErr(emailError, 'Email je prázdný.');
    return;
  }

  if (errorStr.includes('email') && !errorStr.includes('must not contain')) {
    setErr(emailError, 'Email není platný.');
    return;
  }

  if (errorStr.includes('other_identifier must be at least')) {
    let limit = errorStr.split('other_identifier must be at least ')[1].split(' characters')[0];
    setErr(otherIdentifierError, `Minimální délka identifikátoru je ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('other_identifier must be at most')) {
    let limit = errorStr.split('other_identifier must be at most ')[1].split(' characters')[0];
    setErr(otherIdentifierError, `Maximální délka identifikátoru je ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('other_identifier must not contain the reserved word:')) {
    const reservedWord = errorStr.split('reserved word: ')[1];
    setErr(otherIdentifierError, `Identifikátor nesmí obsahovat: ${reservedWord}`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}

function showEditUserErrors(error, detail) {
  const firstNameError = document.querySelector('#edit-user-first-name-error');
  const lastNameError = document.querySelector('#edit-user-last-name-error');
  const emailError = document.querySelector('#edit-user-email-error');
  const phoneError = document.querySelector('#edit-user-phone-error');
  const otherIdentifierError = document.querySelector('#edit-user-other-identifier-error');
  const generalError = document.querySelector('#edit-user-general-error');

  let nameErrorEl = generalError;
  let nameStr = 'Jméno nebo příjmení';
  if (detail === 'first_name_error') {
    nameErrorEl = firstNameError;
    nameStr = 'Jméno';
  } else if (detail === 'last_name_error') {
    nameErrorEl = lastNameError;
    nameStr = 'Příjmení';
  }

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění upravit uživatele.');
      return;
    case 'invalid_id':
      setErr(generalError, 'ID uživatele není správné.');
      return;
    case 'missing_id':
      setErr(generalError, 'Chybí ID uživatele.');
      return;
    case 'user_not_found':
      setErr(generalError, 'Uživatel nebyl nalezen.');
      return;
    case 'missing_first_name':
      setErr(firstNameError, 'Chybí jméno.');
      return;
    case 'missing_last_name':
      setErr(lastNameError, 'Chybí příjmení.');
      return;
    case 'missing_country_code':
      setErr(phoneError, 'Chybí předčíslí.');
      return;
    case 'invalid_phone_number':
      setErr(phoneError, 'Telefonní číslo není platné.');
      return;
    case 'at_least_one_of_email_phone_number_other_identifier_is_required':
      setErr(generalError, 'Vyplňte alespoň jeden z: email, telefonní číslo, jiný identifikátor.');
      return;
    case 'user_email_taken':
      setErr(emailError, 'Email už má jiný uživatel.');
      return;
    case 'user_identifier_taken':
      setErr(generalError, 'Uživatel se stejnými údaji už existuje.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be a string')) {
    setErr(nameErrorEl, `${nameStr} není správně zadané.`);
    return;
  }
  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ')[1].split(' characters')[0];
    setErr(nameErrorEl, `${nameStr} může mít minimálně ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ')[1].split(' characters')[0];
    setErr(nameErrorEl, `${nameStr} může mít maximálně ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('name may only contain letters, digits, and these characters:')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(nameErrorEl, `${nameStr} může obsahovat pouze písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('name must not be all numeric')) {
    setErr(nameErrorEl, `${nameStr} nesmí obsahovat pouze čísla.`);
    return;
  }
  if (errorStr.includes('name must not contain the reserved word:')) {
    const reservedWord = errorStr.split('reserved word: ')[1];
    setErr(nameErrorEl, `${nameStr} nesmí obsahovat: ${reservedWord}`);
    return;
  }


  if (errorStr.includes('email must be a string')) {
    setErr(emailError, 'Email není správně zadaný.');
    return;
  }
  if (errorStr.includes('email is empty')) {
    setErr(emailError, 'Email je prázdný.');
    return;
  }

  if (errorStr.includes('email') && !errorStr.includes('must not contain')) {
    setErr(emailError, 'Email není platný.');
    return;
  }

  if (errorStr.includes('other_identifier must be at least')) {
    let limit = errorStr.split('other_identifier must be at least ')[1].split(' characters')[0];
    setErr(otherIdentifierError, `Minimální délka identifikátoru je ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('other_identifier must be at most')) {
    let limit = errorStr.split('other_identifier must be at most ')[1].split(' characters')[0];
    setErr(otherIdentifierError, `Maximální délka identifikátoru je ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('other_identifier must not contain the reserved word:')) {
    const reservedWord = errorStr.split('reserved word: ')[1];
    setErr(otherIdentifierError, `Identifikátor nesmí obsahovat: ${reservedWord}`);
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}

function showDeleteUserErrors(error) {
  const generalError = document.querySelector('#delete-user-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'insufficient_privileges':
      setErr(generalError, 'Nemáte oprávnění smazat uživatele.');
      return;
    case 'invalid_user_id':
      setErr(generalError, 'ID uživatele není správné.');
      return;
    case 'missing_user_id':
      setErr(generalError, 'Chybí ID uživatele.');
      return;
    case 'user_not_found':
      setErr(generalError, 'Uživatel nebyl nalezen.');
      return;
    default:
      break;
  }
  setErr(generalError, 'Něco se nepovedlo.');
}





/**
 * Načte statistiky akce ze serveru.
 */
async function loadStatistics() {
  if (!eventId) return;

  try {
    const response = await fetch(`/api/events/${encodeURIComponent(eventId)}/statistics`);

    await handleUnauthorizedRedirect(response);

    if (!response.ok) {
      console.error('Failed to load statistics');
      return;
    }

    statsData = await response.json();
    renderStatistics();

  } catch (err) {
    console.error('Error loading statistics:', err);
  }
}


/**
 * Vykreslí statistiky akce.
 */
function renderStatistics() {
  if (!statsData) return;

  const statisticsContainer = document.getElementById('statistics');
  if (!statisticsContainer) return;

  // Vyčistit container
  statisticsContainer.innerHTML = '';

  // 1. CELKOVÉ KARTY STATISTIK
  const overall = statsData.overall_statistics;
  const overallHTML = `
    <div class="stats-overview">
      <h3>Přehled</h3>
      <div class="stats-cards">
        <div class="stat-card">
          <div class="stat-label">Celkové tržby</div>
          <div class="stat-value">${formatNumber(overall.total_revenue_czk)} Kč</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Počet transakcí</div>
          <div class="stat-value">${formatNumber(overall.total_transactions)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Vklady celkem</div>
          <div class="stat-value">${formatNumber(overall.total_deposits_czk)} Kč</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Výběry celkem</div>
          <div class="stat-value">${formatNumber(overall.total_withdrawals_czk)} Kč</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Počet zákazníků</div>
          <div class="stat-value">${formatNumber(overall.unique_users)}</div>
        </div>
        <div class="stat-card">
          <div class="stat-label">Zůstatek v peněženkách</div>
          <div class="stat-value">${formatNumber(statsData.wallet_statistics.total_balance_czk)} Kč</div>
        </div>
      </div>
    </div>
  `;

  // 2. GRAFY
  const chartsHTML = `
    <div class="stats-charts">
      <h3>Grafy</h3>
      
      <div class="chart-wrapper">
        <h4>Vývoj tržeb v čase</h4>
        <div class="chart-container">
          <canvas id="revenue-timeline-chart"></canvas>
        </div>
      </div>
    </div>
  `;

  // 3. DETAIL STÁNKŮ S DROPDOWN PRO PRODUKTY
  const boothsHTML = renderBoothsStatistics();

  // 4. PRODUKTY CELKEM
  const productsHTML = renderProductsStatistics();

  statisticsContainer.innerHTML = overallHTML + chartsHTML + boothsHTML + productsHTML;

  // Vykreslení grafů (musí být po přidání do DOM)
  setTimeout(() => {
    renderRevenueTimelineChart();
  }, 100);
}


/**
 * Vykreslí statistiky stánků.
 */
function renderBoothsStatistics() {
  const sellerBooths = statsData.booth_statistics.filter(b => b.booth_type === 'seller');
  const cashierBooths = statsData.booth_statistics.filter(b => b.booth_type === 'cashier');

  // Seskupit produkty podle stánků
  const boothProducts = {};
  statsData.booth_product_statistics.forEach(bp => {
    if (!boothProducts[bp.booth_id]) {
      boothProducts[bp.booth_id] = [];
    }
    boothProducts[bp.booth_id].push(bp);
  });

  let html = `
    <div class="stats-booths">
      <h3>Detail stánků</h3>
  `;

  // Prodejní stánky
  if (sellerBooths.length > 0) {
    html += '<h4>Prodejní stánky</h4>';
    sellerBooths.sort((a, b) => b.revenue_czk - a.revenue_czk).forEach(booth => {
      const products = boothProducts[booth.booth_id] || [];
      const hasProducts = products.length > 0;

      html += `
        <div class="booth-stat-card">
          <div class="booth-stat-header" data-booth-id="${booth.booth_id}">
            <div class="booth-stat-main">
              <div class="booth-stat-name">${escapeHTML(booth.booth_name)}</div>
              <div class="booth-stat-revenue">${formatNumber(booth.revenue_czk)} Kč</div>
            </div>
            <div class="booth-stat-details">
              <span>Platby: ${formatNumber(booth.payment_count)}</span>
              <span>Transakce: ${formatNumber(booth.transaction_count)}</span>
            </div>
          </div>
          ${hasProducts ? `
            <div class="booth-products" id="booth-products-${booth.booth_id}" style="display: none;">
              <table class="booth-products-table">
                <thead>
                  <tr>
                    <th>Produkt</th>
                    <th>Prodáno kusů</th>
                    <th>Tržby</th>
                    <th>Průměrná cena</th>
                  </tr>
                </thead>
                <tbody>
                  ${products.map(p => `
                    <tr>
                      <td>${escapeHTML(p.product_name)}</td>
                      <td>${formatNumber(p.total_quantity)}</td>
                      <td>${formatNumber(p.total_revenue_czk)} Kč</td>
                      <td>${formatNumber(Math.round(p.avg_price_czk))} Kč</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            </div>
          ` : ''}
        </div>
      `;
    });
  }

  // Pokladny
  if (cashierBooths.length > 0) {
    html += '<h4>Pokladny</h4>';
    cashierBooths.forEach(booth => {
      html += `
        <div class="booth-stat-card">
          <div class="booth-stat-header">
            <div class="booth-stat-main">
              <div class="booth-stat-name">${escapeHTML(booth.booth_name)}</div>
            </div>
            <div class="booth-stat-details">
              <span>Vklady: ${formatNumber(booth.deposits_czk)} Kč</span>
              <span>Výběry: ${formatNumber(booth.withdrawals_czk)} Kč</span>
              <span>Transakce: ${formatNumber(booth.transaction_count)}</span>
            </div>
          </div>
        </div>
      `;
    });
  }

  html += '</div>';
  return html;
}


/**
 * Vykreslí statistiky produktů.
 */
function renderProductsStatistics() {
  const products = statsData.product_statistics.sort((a, b) => b.total_revenue_czk - a.total_revenue_czk);

  if (products.length === 0) return '';

  let html = `
    <div class="stats-products">
      <h3>Produkty</h3>
      <table class="products-stats-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Produkt</th>
            <th>Prodáno kusů</th>
            <th>Tržby</th>
            <th>Průměrná cena</th>
          </tr>
        </thead>
        <tbody>
          ${products.slice(0, 20).map((p, idx) => `
            <tr>
              <td>${idx + 1}</td>
              <td>${escapeHTML(p.product_name)}</td>
              <td>${formatNumber(p.total_quantity)}</td>
              <td>${formatNumber(p.total_revenue_czk)} Kč</td>
              <td>${formatNumber(Math.round(p.avg_price_czk))} Kč</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;

  return html;
}

/**
* Přepne zobrazení produktů u stánku.
* @param {string|number} boothId - ID stánku
*/
function toggleBoothProducts(boothId) {
  const productsDiv = document.getElementById(`booth-products-${boothId}`);
  if (!productsDiv) return;

  const isVisible = productsDiv.style.display !== 'none';
  productsDiv.style.display = isVisible ? 'none' : 'block';
};

// GRAFY
function renderRevenueTimelineChart() {
  const ctx = document.getElementById('revenue-timeline-chart');
  if (!ctx) return;

  if (charts.revenueTimeline) {
    charts.revenueTimeline.destroy();
  }

  const data = statsData.hourly_statistics;

  charts.revenueTimeline = new Chart(ctx, {
    type: 'line',
    data: {
      labels: data.map(d => new Date(d.hour).toLocaleString('cs-CZ', {
        day: '2-digit',
        month: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
      })),
      datasets: [
        {
          label: 'Tržby (Kč)',
          data: data.map(d => d.revenue_czk),
          borderColor: 'rgb(0, 120, 212)',
          backgroundColor: 'rgba(0, 120, 212, 0.1)',
          tension: 0.3,
          fill: true
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          display: false
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: {
            callback: function (value) {
              return value.toLocaleString('cs-CZ') + ' Kč';
            }
          }
        }
      }
    }
  });
}
