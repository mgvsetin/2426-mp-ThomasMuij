import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { formatDateTimeISOToDisplay, formatForDatetimeLocalInput, isValidDate } from "../general/date_utils.js";
import { directTo, markSelectedRow, selectRow, unselectRow } from "../general/table_utils.js";
import { cloneData } from "../general/cache.js";


const card = document.querySelector('#card');

const boothsSearchBar = document.querySelector('#booths-search-bar');
const managersSearchBar = document.querySelector('#managers-search-bar');
const employeesSearchBar = document.querySelector('#employees-search-bar');
const productsSearchBar = document.querySelector('#products-search-bar');
const categoriesSearchBar = document.querySelector('#categories-search-bar');

const boothsTableBody = document.querySelector('#booths-table tbody');
const managersTableBody = document.querySelector('#managers-table tbody');
const employeesTableBody = document.querySelector('#employees-table tbody');
const productsTableBody = document.querySelector('#products-table tbody');
const categoriesTableBody = document.querySelector('#categories-table tbody');

const orderBy = {
  booths: { key: '', ascending: true },
  managers: { key: '', ascending: true },
  employees: { key: '', ascending: true },
  products: { key: '', ascending: true },
  categories: { key: '', ascending: true }
};

let _getEventDataPromise = null;
const cache_time_ms = 60 * 1000; // 1 minuta
const eventId = getEventIdFromPath();
// cache of fetched data
const _eventDataCache = {
  data: null,
  expiry: 0
};


loadPage({
  eventInfo: true,
  header: true,
  sidebar: true,
  boothsTable: true,
  managersTable: true,
  employeesTable: true,
  productsTable: true,
  categoriesTable: true
});


document.addEventListener('click', async (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) return;

  // open graphs, probably just add the graphs to the page itself (maybe under something like show graphs)
  if (event.target.matches('#open-graphs')) {
    // either navigate to a dedicated graphs page or open overlay
    // We'll navigate to /events/<id>/graphs (implement server-side) as requested
    window.location.href = `/events/${encodeURIComponent(eventId)}/graphs`;
    return;
  }

  // upravit akci
  if (event.target.matches('#edit-event')) {
    await openEditEventModal();
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

  // upravit stánek
  const editBoothBtn = event.target.closest('.edit-booth');
  if (editBoothBtn) {
    const row = editBoothBtn.closest('tr[id]');
    await openEditBoothModal(row);
    return;
  }

  // smazat stánek
  const deleteBoothBtn = event.target.closest('.delete-booth');
  if (deleteBoothBtn) {
    const row = deleteBoothBtn.closest('tr[id]');
    await openDeleteBoothModal(row);
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

  // upravit zaměstnance (vrámci akce)
  const editEmployeeButton = event.target.closest('.edit-employee');
  if (editEmployeeButton) {
    const row = editEmployeeButton.closest('tr[id]');
    await openEditEmployeeModal(row);
    return;
  }

  // odendat zaměstnance z akce
  const removeEmployeeBtn = event.target.closest('.remove-employee');
  if (removeEmployeeBtn) {
    const row = removeEmployeeBtn.closest('tr[id]');
    await openRemoveEmployeeModal(row);
    return;
  }

  // přidat produkt
  if (event.target.matches('#add-product')) {
    await openAddProductModal();
    return;
  }

  // upravit produkt
  const editProductButton = event.target.closest('.edit-product');
  if (editProductButton) {
    const row = editProductButton.closest('tr[id]');
    await openEditProductModal(row);
    return;
  }

  // smazat produkt
  const deleteProductBtn = event.target.closest('.delete-product');
  if (deleteProductBtn) {
    const row = deleteProductBtn.closest('tr[id]');
    await openDeleteProductModal(row);
    return;
  }

  // přidat kategorii
  if (event.target.matches('#add-category')) {
    openAddCategoryModal();
    return;
  }

  // upravit kategorii
  const editCategoryButton = event.target.closest('.edit-category');
  if (editCategoryButton) {
    const row = editCategoryButton.closest('tr[id]');
    openEditCategoryModal(row);
    return;
  }

  // smazat kategorii
  const deleteCategoryBtn = event.target.closest('.delete-category');
  if (deleteCategoryBtn) {
    const row = deleteCategoryBtn.closest('tr[id]');
    openDeleteCategoryModal(row);
    return;
  }


  const closeModalBtn = event.target.closest('.close-modal');
  if (closeModalBtn) {
    closeModal();
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
  const row = event.target.closest('tr');
  if (row) {
    selectRow(row, card);
    return;
  }

  if (event.target.matches('.search-bar')) {
    return;
  }
  // kliknutí na "nic" odvybere řádek
  unselectRow(card);
});


document.addEventListener('dblclick', async (event) => {
  const row = event.target.closest('tr[id]');
  if (row) {
    const parentTable = row.closest('table');

    if (parentTable.id === 'booths-table') {
      await openEditBoothModal(row);
      return;
    } else if (parentTable.id === 'managers-table') {
      await openEditEmployeeModal(row);
      return;
    } else if (parentTable.id === 'employees-table') {
      await openEditEmployeeModal(row);
      return;
    } else if (parentTable.id === 'products-table') {
      await openEditProductModal(row);
      return;
    } else if (parentTable.id === 'categories-table') {
      openEditCategoryModal(row);
      return;
    }
  }
});


document.addEventListener('submit', async (event) => {
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

      if (response.status === 401) {
        const json = await response.json();
        window.location.href = json.redirect_url;
        return;
      }

      const data = await response.json();

      if (response.status === 403 && data.error === 'insufficient_priviliges') {
        showEditEventErrors('insufficient_priviliges');
        saveButton.disabled = false;
        return;
      }

      if (response.status === 404 && data.error === 'event_not_found') {
        showEditEventErrors('event_not_found');
        saveButton.disabled = false;
        return;
      }

      if (response.status === 400) {
        showEditEventErrors(data.error || 'invalid_request', data.detail);
        saveButton.disabled = false;
        return;
      }

      if (!response.ok) {
        showEditEventErrors('unexpected_error');
        saveButton.disabled = false;
        return;
      }

      closeModal();

      resetEventDataCache();
      loadPage({
        eventInfo: true
      });

    } catch (err) {
      showEditEventErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }

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

      if (response.status === 401) {
        const json = await response.json();
        window.location.href = json.redirect_url;
        return;
      }

      const data = await response.json();

      if (response.status === 403 && data.error === 'insufficient_priviliges') {
        showDeleteEventErrors('insufficient_priviliges');
        saveButton.disabled = false;
        return;
      }

      if (response.status === 404 && data.error === 'event_not_found') {
        showDeleteEventErrors('event_not_found');
        saveButton.disabled = false;
        return;
      }

      if (response.status === 400) {
        showDeleteEventErrors(data.error || 'invalid_request', data.detail);
        saveButton.disabled = false;
        return;
      }

      if (!response.ok) {
        showDeleteEventErrors('unexpected_error');
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


  //   return;
  // }

  // // uprav zaměstnance
  // const editFrom = event.target.closest('#edit-form');
  // if (editFrom) {
  //   event.preventDefault();
  //   const saveButton = editFrom.querySelector('#edit-save');
  //   saveButton.disabled = true;

  //   clearEditErrors();

  //   const formData = new FormData(editFrom);

  //   formData.set('username', formData.get('username').trim());
  //   formData.set('email', formData.get('email').trim());

  //   const result = await editEmployee(formData);

  //   saveButton.disabled = false;

  //   if (result === true) {
  //     const overlayEl = document.querySelector('#edit-overlay');
  //     if (overlayEl) overlayEl.remove();
  //     resetEmployeesCache();
  //     loadPage({
  //       table: true,
  //       header: true
  //     });
  //     return;
  //   }

  //   showEditErrors(result);
  //   return;
  // }

  // // odstraň zaměstnance
  // const deleteForm = event.target.closest('#delete-form');
  // if (deleteForm) {
  //   event.preventDefault();
  //   const deleteButton = deleteForm.querySelector('#delete-confirm');
  //   deleteButton.disabled = true;

  //   clearDeleteErrors();

  //   const formData = new FormData(deleteForm);

  //   const result = await deleteEmployee(formData);

  //   deleteButton.disabled = false;

  //   if (result === true) {
  //     const overlayEl = document.querySelector('#delete-overlay');
  //     if (overlayEl) overlayEl.remove();
  //     resetEmployeesCache();
  //     loadPage({
  //       table: true
  //     });
  //     return;
  //   }

  //   showDeleteErrors(result);
  //   return;
  // }
});


// document.getElementById('delete-event').addEventListener('click', async () => {
//   if (!confirm('Smazat tuto akci? (operace je soft-delete)')) return;
//   try {
//     const form = new FormData(); form.set('id', eventId);
//     const res = await fetch('/api/events/delete', { method: 'DELETE', body: form });
//     if (res.status === 401) { const j = await res.json(); window.location.href = j.redirect_url; return; }
//     if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
//     // go back to events list
//     window.location.href = '/events/manager';
//   } catch (e) { alert('Nelze smazat akci: ' + e.message); }
// });

// Delegated actions for booth/edit/delete product/employee


document.addEventListener('input', (event) => {
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
    }
  }
});

// document.getElementById('search-bar').addEventListener('input', (event) => {
//   const query = event.target.value.trim().toLowerCase();
//   document.querySelectorAll('table tbody tr').forEach(tr => {
//     const text = tr.textContent.toLowerCase();
//     tr.style.display = (!query || text.includes(query)) ? '' : 'none';
//   });
// });


async function loadPage({
  eventInfo = false,
  header = false,
  sidebar = false,
  boothsTable = false,
  managersTable = false,
  employeesTable = false,
  productsTable = false,
  categoriesTable = false } = {}) {
  const eventData = await getEventData();
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
  await Promise.all(toLoad);
}


function getEventIdFromPath() {
  // filter(Boolean) odstraňuje falsy hodnoty jako ""
  const parts = window.location.pathname.split('/').filter(Boolean);
  // mělo by být ['events','<id>','manager']
  if (parts[0] === 'events' && parts.length >= 2) {
    return parts[1];
  }
  return null;
}


function resetEventDataCache() {
  _eventDataCache.data = null;
  _eventDataCache.expiry = 0;
}

function getEventData() {
  if (_eventDataCache.data && _eventDataCache.expiry > Date.now()) {
    return Promise.resolve(cloneData(_eventDataCache.data));
  }

  if (_getEventDataPromise) return _getEventDataPromise;

  _getEventDataPromise = (async () => {
    try {
      if (!eventId) {
        throw new Error('no_event_id');
      }

      const res = await fetch(`/api/events/${encodeURIComponent(eventId)}`);

      if (res.status === 401) {
        const json = await res.json();
        _getEventDataPromise = null;
        window.location.href = json.redirect_url;
        return;
      }

      if (res.status === 403) {
        throw new Error('insufficient_priviliges');
      }

      if (res.status === 404) {
        throw new Error('event_not_found');
      }

      if (!res.ok) {
        throw new Error('unexpected_error');
      }

      const resData = await res.json();

      const data = {
        event: resData.event,
        booths: resData.booths,
        employees: resData.employees,
        products: resData.products,
        categories: resData.categories
      };

      data.employees.forEach((emp) => {
        emp.isManager = !emp.booths.length;
      });

      _eventDataCache.data = data;
      _eventDataCache.expiry = Date.now() + cache_time_ms;

      console.log(_eventDataCache.data);

      return cloneData(_eventDataCache.data);

    } catch (err) {
      let errorMessage = '';
      if (err.message === 'no_event_id') {
        errorMessage = 'Nelze určit ID akce z URL.';
      } else if (err.message === 'insufficient_priviliges') {
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
      return null;
    } finally {
      _getEventDataPromise = null;
    }
  })();

  return _getEventDataPromise;
}


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
  }
}


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
    } else if (key === 'price') {
      return (Number(aValue) - Number(bValue)) * (dict.ascending ? 1 : -1);
    } else {
      aValue = String(aValue).toLowerCase();
      bValue = String(bValue).toLowerCase();
    }

    console.log(aValue);
    console.log(bValue);

    return aValue.localeCompare(bValue) * (dict.ascending ? 1 : -1);
  }

  return sorter
}


function boothIsSearchedFor(booth, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  // const id = String(booth.id || '').toLowerCase();
  const name = String(booth.name || '').toLowerCase();
  const type = String(boothTypeToDisplay(booth.booth_type) || '').toLowerCase();

  const searchable = `${name} ${type}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      // key=value (id=... name=... type=...)
      const [searchKeyWord, search] = query.split('=');
      // if (['id', 'identifier'].includes(searchKeyWord)) {
      //   if (!id.includes(search)) return false;
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

function employeeIsSearchedFor(employee, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  // const id = String(employee.id || '').toLowerCase();
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

      // if (['id', 'identifier'].includes(searchKeyWord)) {
      //   if (!id.includes(search)) return false;
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


function productIsSearchedFor(product, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  // const id = String(product.id || '').toLowerCase();
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
      // if (['id', 'identifier'].includes(searchKeyWord)) {
      //   if (!id.includes(search)) return false;
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


function categoryIsSearchedFor(category, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  // const id = String(category.id || '').toLowerCase();
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
      // if (['id', 'identifier'].includes(searchKeyWord)) {
      //   if (!id.includes(search)) return false;
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


function belongingBoothsToDisplay(booths) {
  return booths.map(booth => `<span data-direct-to="${booth.id}">${escapeHTML(booth.name)}</span>`).join(', ') || '-';

  // (product.booths || []).map(booth => `<span data-direct-to="${booth.id}">${booth.name}</span>`).filter(Boolean).join(', ') || '-';
}


function belongingCategoriesToDisplay(categories) {
  return categories.map(category => `<span data-direct-to="${category.id}">${escapeHTML(category.name)}</span>`).join(', ') || '-';

  // (product.categories || []).map(category => `<span data-direct-to="${category.id}">${category.name}</span>`).filter(Boolean).join(', ') || '-';
}


function boothTypeToDisplay(type) {
  if (type === 'cashier') {
    return 'pokladna';
  } else if (type === 'seller') {
    return 'prodej';
  } else {
    return type;
  }
}


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
        <td class="event-name">${escapeHTML(booth.name)}</td>
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
  markSelectedRow(card);
}


function renderManagers(eventData) {
  const searchQuery = managersSearchBar.value;
  // [{id, username, email, booths: [{id, role}, ...]}, ...]
  const managers = eventData.employees.filter(employee => employee.isManager);

  const sorter = sorterFactory(orderBy.managers);
  const sortedManagers = managers.toSorted(sorter);

  let rows = '';

  sortedManagers.forEach((manager, idx) => {
    if (!employeeIsSearchedFor(manager, searchQuery)) return;

    rows += `
      <tr id="${manager.id}">
        <td>${idx + 1}</td>
        <td>${escapeHTML(manager.username)}</td>
        <td>${escapeHTML(manager.email)}</td>
        <td class="actions">
          <button class="icon-btn edit edit-employee" data-id="${manager.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete remove-employee" data-id="${manager.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  managersTableBody.innerHTML = rows || `<tr><td class="muted" colspan="4">Žádní manažeři.</td></tr>`;
  markSelectedRow(card);
}


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
        <td>${escapeHTML(employee.username)}</td>
        <td>${escapeHTML(employee.email)}</td>
        <td>${boothsStr}</td>
        <td class="actions">
          <button class="icon-btn edit edit-employee" data-id="${employee.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete remove-employee" data-id="${employee.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  employeesTableBody.innerHTML = rows || `<tr><td class="muted" colspan="4">Žádní zaměstnanci.</td></tr>`;
  markSelectedRow(card);
}

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
        <div class="image-container">
          <img class="product-image" src="${product.image_path}">
        </div>
      `;
    } else {
      imageHTML = '-';
    }

    rows += `
      <tr id="${product.id}">
        <td>${idx + 1}</td>
        <td>${escapeHTML(product.name)}</td>
        <td>${escapeHTML(String(product.price))}</td>
        <td class="image-cell">${imageHTML}</td>
        <td>${boothsStr}</td>
        <td>${categoriesStr}</td>
        <td class="actions">
          <button class="icon-btn edit edit-product" data-id="${product.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete delete-product" data-id="${product.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  productsTableBody.innerHTML = rows || `<tr><td class="muted" colspan="6">Žádné produkty.</td></tr>`;
  markSelectedRow(card);
}


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
        <td>${escapeHTML(category.name)}</td>
        <td>${boothsStr}</td>
        <td class="actions">
          <button class="icon-btn edit edit-category" data-id="${category.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="icon-btn delete delete-category" data-id="${category.id}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  categoriesTableBody.innerHTML = rows || `<tr><td class="muted" colspan="3">Žádné kategorie.</td></tr>`;
  markSelectedRow(card);
}


function openModal(html) {
  if (document.querySelector('.overlay')) return; // max 1
  const div = document.createElement('div');
  div.className = 'overlay';
  div.innerHTML = `<div class="modal">${html}</div>`;
  document.body.appendChild(div);
  return div;
}

function closeModal() {
  const overlay = document.querySelector('.overlay');
  if (overlay) overlay.remove();
}


async function openEditEventModal() {
  const event = (await getEventData()).event;
  if (!event) return;
  const html = `
        <header>
          <h2>Upravit akci</h2>
          <button class="close-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
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
            <button type="submit" class="save-form btn btn-primary">Uložit</button>
          </div>
        </form>
      `;

  openModal(html);
}


async function openDeleteEventModal() {
  const event = (await getEventData()).event;
  if (!event) return;
  const html = `
        <header>
          <h2 class="delete-form-text">Smazat akci</h2>
          <button class="close-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
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
}


function openAddBoothModal() {
  const html = `
        <header>
          <h2>Přidat stánek</h2>
          <button class="close-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <form id="add-booth-form">
          <div class="form-row">
            <label for="booth-name">Název</label>
            <input id="booth-name" type="text"/>
          </div>
          <div class="form-row">
            <label for="booth-type">Typ</label>
            <select id="booth-type">
              <option value="seller">seller</option>
              <option value="cashier">cashier</option></select>
            </div>
          <div class="modal-actions">
            <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
            <button type="submit" class="save-form btn btn-primary">Vytvořit</button>
          </div>
        </form>
      `;
  const modal = openModal(html);
  modal.querySelector('#save').addEventListener('click', async () => {
    const name = modal.querySelector('#booth-name').value.trim();
    const type = modal.querySelector('#booth-type').value;
    if (!name) { alert('Zadejte název'); return; }
    // call API to create booth (endpoint may vary - adjust to your backend)
    try {
      const form = new FormData();
      form.set('name', name);
      form.set('booth_type', type);
      form.set('event_id', eventId);
      const res = await fetch('/api/booths/create', { method: 'POST', body: form });
      if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
      closeModal();
      resetEventDataCache();
    } catch (e) { alert('Nelze vytvořit stánek: ' + e.message); }
  });
}


async function openEditBoothModal(row) {
  const id = row.id;
  const booth = (await getEventData()).booths.find(booth => booth.id === id);
  if (!booth) return;

  const html = `
    <header>
      <h2>Upravit stánek</h2>
      <button class="close-modal cross-close">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </header>
    <form id="edit-booth-form">
      <div class="form-row">
        <label for="booth-name">Název</label>
        <input id="booth-name" type="text" value="${escapeHTML(booth.name)}"/>
      </div>
      <div class="form-row">
        <label for="booth-type">Typ</label>
        <select id="booth-type">
          <option value="seller" ${booth.booth_type === 'seller' ? 'selected' : ''}>${boothTypeToDisplay('seller')}</option>
          <option value="cashier" ${booth.booth_type === 'cashier' ? 'selected' : ''}>${boothTypeToDisplay('cashier')}</option>
        </select>
      </div>
      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
  const modal = openModal(html);
  modal.querySelector('#save').addEventListener('click', async () => {
    const name = modal.querySelector('#booth-name').value.trim();
    const type = modal.querySelector('#booth-type').value;
    if (!name) { alert('Název je povinný'); return; }
    try {
      const form = new FormData(); form.set('id', id); form.set('name', name); form.set('booth_type', type);
      const res = await fetch('/api/booths/edit', { method: 'POST', body: form });
      if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
      closeModal();
      resetEventDataCache();
    } catch (e) { alert('Nelze upravit stánek: ' + e.message); }
  });
}


async function openDeleteBoothModal(row) {
  const id = row.id;
  if (!confirm('Opravdu chcete smazat stánek?')) return;
  try {
    const form = new FormData();
    form.set('id', id);

    const res = await fetch('/api/booths/delete', { method: 'DELETE', body: form });

    if (!res.ok) {
      const j = await res.json().catch(() => ({ error: 'Chyba' }));
      throw new Error(j.error || 'Chyba');
    }

    resetEventDataCache();
  } catch (error) {
    alert('Nelze smazat stánek: ' + error.message);
  }
}


async function openAssignEmployeeModal(assignManager) {
  const booths = (await getEventData()).booths;
  const html = `
        <header>
          <h2>${assignManager ? 'Přiřadit manažera' : 'Přiřadit zaměstnance'}</h2>
          <button class="close-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <form id="assign-employee-form">
          <div class="form-row">
            <label for="emp-id">Employee ID</label>
            <input id="emp-id" type="text" placeholder="UUID zaměstnance"/>
          </div>
          ${assignManager ? '' : `
            <div class="form-row">
              <label for="emp-booth">Stánek (pokud ne manažer)</label>
              <select id="emp-booth">
                <option value="">-- vyberte --</option>
                ${booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('')}'
              </select>
            </div>'`}
          <div class="modal-actions">
            <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
            <button type="submit" class="save-form btn btn-primary">Přiřadit</button>
          </div>
        </form>
      `;
  const modal = openModal(html);
  modal.querySelector('#save').addEventListener('click', async () => {
    const empId = modal.querySelector('#emp-id').value.trim();
    const boothId = assignManager ? null : (modal.querySelector('#emp-booth').value || null);
    if (!empId) { alert('Zadejte ID zaměstnance'); return; }
    try {
      const form = new FormData();
      form.set('employee_id', empId);
      form.set('event_id', eventId);
      if (boothId) form.set('booth_id', boothId);
      const res = await fetch('/api/employee_event_booth_roles/create', { method: 'POST', body: form });
      if (res.status === 401) {
        const j = await res.json();
        window.location.href = j.redirect_url;
        return;
      }
      if (!res.ok) {
        const j = await res.json().catch(() => ({ error: 'Chyba' }));
        throw new Error(j.error || 'Chyba');
      }
      closeModal()
      resetEventDataCache();
    } catch (e) { alert('Nelze přiřadit zaměstnance: ' + e.message); }
  });
}


async function openEditEmployeeModal(row) {
  const id = row.id;
  const eventData = await getEventData();
  const emp = eventData.employees.find(employee => employee.id === id);
  if (!emp) return;
  // simple modal to change role or booths assignment (UI only)
  const availableBooths = eventData.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('');
  const html = `
          <header>
            <h2>Upravit zaměstnance</h2>
            <button class="close-modal cross-close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </header>
          <form id="edit-employee-form">
            <div class="form-row">
              <label for="emp-username">Uživatel</label>
              <input id="emp-username" type="text" value="${escapeHTML(emp.username)}" disabled/>
            </div>
            <div class="form-row">
              <label for="employee-booths">Přiřazené stánky (více pro Ctrl/Shift)</label>
              <select id="employee-booths" multiple size="6">${availableBooths}</select>
            </div>
            <div class="modal-actions">
              <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
              <button type="submit" class="save-form btn btn-primary">Uložit</button>
            </div>
          </form>
        `;
  const modal = openModal(html);
  // preselect current booths
  const sel = modal.querySelector('#employee-booths');
  const assigned = (emp.booths || []).map(b => b.id);
  for (const opt of sel.options) { if (assigned.includes(opt.value)) opt.selected = true; }

  modal.querySelector('#save').addEventListener('click', async () => {
    const selected = Array.from(sel.selectedOptions).map(o => o.value);
    try {
      // API shape: create role rows for each selected booth or remove others. Implement via backend endpoints.
      const form = new FormData();
      form.set('employee_id', id);
      form.set('event_id', eventId);
      form.set('booth_ids', JSON.stringify(selected));
      const res = await fetch('/api/employee_event_booth_roles/update_for_employee', { method: 'POST', body: form });
      if (!res.ok) {
        const j = await res.json().catch(() => ({ error: 'Chyba' }));
        throw new Error(j.error || 'Chyba');
      }
      closeModal();
      resetEventDataCache();
    } catch (e) { alert('Nelze upravit zaměstnance: ' + e.message); }
  });
}


async function openRemoveEmployeeModal(row) {
  const id = row.id;
  if (!confirm('Odebrat přiřazení zaměstnance?')) return;
  try {
    const form = new FormData();
    form.set('employee_id', id);
    form.set('event_id', eventId);

    const res = await fetch('/api/employee_event_booth_roles/delete_for_employee',
      { method: 'DELETE', body: form }
    );
    if (!res.ok) {
      const j = await res.json().catch(() => ({ error: 'Chyba' }));
      throw new Error(j.error || 'Chyba');
    }

    resetEventDataCache();
  } catch (error) {
    alert('Nelze odebrat zaměstnance: ' + error.message);
  }
  return;
}


async function openAddProductModal() {
  const eventBooths = (await getEventData()).booths
  const html = `
        <header>
          <h2>Přidat produkt / cenu pro akci</h2>
          <button class="close-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <form id="add-product-form">
          <div class="form-row">
            <label for="prod-id">Produkt (existující ID)</label>
            <input id="prod-id" type="text" placeholder="UUID produktu (pokud nové, vytvořte produkt jinde)"/>
          </div>
          <div class="form-row">
            <label for="prod-price">Cena (Kč)</label>
            <input id="prod-price" type="number"/>
          </div>
          <div class="form-row">
            <label for="prod-booths">Přiřadit stánky (volitelné)</label>
            <select id="prod-booths" multiple size="6">${eventBooths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('')}</select>
          </div>
          <div class="modal-actions">
            <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
            <button type="submit" class="save-form btn btn-primary">Vytvořit</button>
          </div>
        </form>
      `;
  const modal = openModal(html);
  modal.querySelector('#save').addEventListener('click', async () => {
    const productId = modal.querySelector('#prod-id').value.trim(); const price = modal.querySelector('#prod-price').value; const booths = Array.from(modal.querySelector('#prod-booths').selectedOptions).map(o => o.value);
    if (!productId || !price) { alert('Vyplňte id produktu a cenu'); return; }
    try {
      const form = new FormData();
      form.set('product_id', productId);
      form.set('event_id', eventId);
      form.set('price', price);
      form.set('booth_ids', JSON.stringify(booths));
      const res = await fetch('/api/product_event_prices/create', { method: 'POST', body: form });
      if (!res.ok) {
        const j = await res.json().catch(() => ({ error: 'Chyba' }));
        throw new Error(j.error || 'Chyba');
      }
      closeModal();
      resetEventDataCache();
    } catch (e) { alert('Nelze přidat produkt: ' + e.message); }
  });
}


async function openEditProductModal(row) {
  const id = row.id;
  const eventData = await getEventData();
  const products = eventData.products.find(x => x.id === id);
  if (!products) return;
  const availableBooths = eventData.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('');
  const html = `
          <header>
            <h2>Upravit produkt</h2>
            <button class="close-modal cross-close">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </header>
          <form id="edit-product-form">
            <div class="form-row">
              <label for="prod-name">Název</label>
              <input id="prod-name" type="text" value="${escapeHTML(products.name)}"/>
            </div>
            <div class="form-row">
              <label for="prod-price">Cena (Kč)</label>
              <input id="prod-price" type="number" value="${escapeHTML(String(products.price))}"/>
            </div>
            <div class="form-row">
              <label for="prod-booths">Přiřadit stánky</label>
              <select id="prod-booths" multiple size="6">${availableBooths}</select>
            </div>
            <div class="modal-actions">
              <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
              <button type="submit" class="save-form btn btn-primary">Uložit</button>
            </div>
          </form>
        `;
  const modal = openModal(html);
  const sel = modal.querySelector('#prod-booths');
  const assigned = (products.booths || []).map(b => b.id);
  for (const opt of sel.options) {
    if (assigned.includes(opt.value)) opt.selected = true;
  }
  modal.querySelector('#save').addEventListener('click', async () => {
    const name = modal.querySelector('#prod-name').value.trim();
    const price = modal.querySelector('#prod-price').value;
    const booths = Array.from(sel.selectedOptions).map(o => o.value);
    if (!name || !price) {
      alert('Vyplňte název a cenu');
      return;
    }
    try {
      const form = new FormData();
      form.set('product_id', id);
      form.set('name', name);
      form.set('price', price);
      form.set('booth_ids', JSON.stringify(booths));
      const res = await fetch('/api/product_event_prices/update_for_product', { method: 'POST', body: form });
      if (!res.ok) {
        const j = await res.json().catch(() => ({ error: 'Chyba' }));
        throw new Error(j.error || 'Chyba');
      }
      closeModal();
      resetEventDataCache();
    } catch (e) {
      alert('Nelze upravit produkt: ' + e.message);
    }
  });
  return;
}


async function openDeleteProductModal(row) {
  const id = row.id;
  if (!confirm('Odebrat tento produkt z akce?')) return;
  try {
    const form = new FormData();
    form.set('product_id', id);
    form.set('event_id', eventId);
    const res = await fetch('/api/product_event_prices/delete_for_product', { method: 'DELETE', body: form });
    if (!res.ok) {
      const j = await res.json().catch(() => ({ error: 'Chyba' }));
      throw new Error(j.error || 'Chyba');
    }
    resetEventDataCache();
  } catch (error) {
    alert('Nelze odebrat produkt: ' + error.message);
  }
}


function openAddCategoryModal() {

}


function openEditCategoryModal(row) {

}


function openDeleteCategoryModal(row) {

}


function clearModalErrors() {
  const els = document.querySelectorAll('.form-error');
  els.forEach(e => {
    e.innerHTML = '';
    e.classList.remove('show-form-error');
  });
}


function showEditEventErrors(error, detail) {
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
    case 'insufficient_priviliges':
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
    case 'db_integrity_error':
      if (detail.includes('unique_index_events_name_active')) {
        setErr(nameError, 'Název už má jiná akce.');
      } else {
        setErr(generalError, 'Něco se nepovedlo.');
        return;
      }
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
    setErr(nameError, `Název musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a: ${allowedChars}`);
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

  setErr(generalError, errorStr);
}


function showDeleteEventErrors(error, detail) {
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
    case 'insufficient_priviliges':
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

  setErr(generalError, errorStr);
}