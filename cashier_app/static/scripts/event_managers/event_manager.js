import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { formatDateTimeISOToDisplay } from "../general/date_utils.js";
import { directTo, markSelectedRow, selectRow, unselectRow } from "../general/table_utils.js";


const card = document.querySelector('#card');

const boothsSearchBar = document.querySelector('#booths-search-bar');
const managersSearchBar = document.querySelector('#managers-search-bar');
const employeesSearchBar = document.querySelector('#employees-search-bar');
const productsSearchBar = document.querySelector('#products-search-bar');

const boothsTableBody = document.querySelector('#booths-table tbody');
const managersTableBody = document.querySelector('#managers-table tbody');
const employeesTableBody = document.querySelector('#employees-table tbody');
const productsTableBody = document.querySelector('#products-table tbody');

let _getEventDataPromise = null;
const cache_time_ms = 60 * 1000; // 1 minuta
const eventId = getEventIdFromPath();
// cache of fetched data
const _eventDataCache = {
  data: null,
  expiry: 0
};


loadPage({
  tableHeader: true,
  header: true,
  sidebar: true,
  boothsTable: true,
  managersTable: true,
  employeesTable: true,
  productsTable: true
});


document.addEventListener('click', async (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) return;

  // Add Booth
  if (event.target.matches('#add-booth')) {
    const html = `
        <header>
          <h2>Přidat stánek</h2>
          <button id="close-modal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <form id="edit-booth-form">
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
            <button id="cancel" class="btn btn-ghost">Zrušit</button>
            <button id="save" class="btn btn-primary">Vytvořit</button>
          </div>
        </form>
      `;
    const modal = openModal(html);
    modal.querySelector('#close-modal').addEventListener('click', closeModal);
    modal.querySelector('#cancel').addEventListener('click', closeModal);
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
    return;
  }

  // open graphs, probably just add the graphs to the page itself (maybe under something like show graphs)
  if (event.target.matches('#open-graphs')) {
    // either navigate to a dedicated graphs page or open overlay
    // We'll navigate to /events/<id>/graphs (implement server-side) as requested
    window.location.href = `/events/${encodeURIComponent(eventId)}/graphs`;
    return;
  }

  // Edit / Delete Event
  if (event.target.matches('#edit-event')) {
    const ev = (await getEventData()).event; if (!ev) return;
    const html = `
        <header>
          <h2>Upravit akci</h2>
          <button id="close-modal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <form id="edit-booth-form">
          <div class="form-row">
            <label for="event-name-input">Název</label>
            <input id="event-name-input" type="text" value="${escapeHTML(ev.name || '')}"/>
          </div>
          <div class="form-row">
            <label for="event-start-input">Začátek</label>
            <input id="event-start-input" type="datetime-local" value="${ev.start_at ? new Date(ev.start_at).toISOString().slice(0, 16) : ''}"/>
          </div>
          <div class="form-row">
            <label for="event-end-input">Konec</label>
            <input id="event-end-input" type="datetime-local" value="${ev.end_at ? new Date(ev.end_at).toISOString().slice(0, 16) : ''}"/>
          </div>
          <div class="modal-actions">
            <button id="cancel" class="btn btn-ghost">Zrušit</button>
            <button id="save" class="btn btn-primary">Uložit</button>
          </div>
        </form>
      `;
    const modal = openModal(html);
    modal.querySelector('#close-modal').addEventListener('click', closeModal);
    modal.querySelector('#cancel').addEventListener('click', closeModal);
    modal.querySelector('#save').addEventListener('click', async () => {
      const name = modal.querySelector('#event-name-input').value.trim();
      const start = modal.querySelector('#event-start-input').value;
      const end = modal.querySelector('#event-end-input').value;
      if (!name) { alert('Název je povinný'); return; }
      try {
        const form = new FormData(); form.set('id', eventId); form.set('name', name);
        if (start) form.set('start-at', new Date(start).toISOString());
        if (end) form.set('end-at', new Date(end).toISOString());
        const res = await fetch('/api/events/edit', { method: 'POST', body: form });
        if (res.status === 401) { const j = await res.json(); window.location.href = j.redirect_url; return; }
        if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
        closeModal();
        resetEventDataCache();
      } catch (e) { alert('Nelze upravit akci: ' + e.message); }
    });
    return;
  }

  // Add product and add employee/manager buttons (open small modals)
  if (event.target.matches('#add-product')) {
    const eventBooths = (await getEventData()).booths
    const html = `
        <header>
          <h2>Přidat produkt / cenu pro akci</h2>
          <button id="close-modal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <form id="edit-booth-form">
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
            <button id="cancel" class="btn btn-ghost">Zrušit</button>
            <button id="save" class="btn btn-primary">Vytvořit</button>
          </div>
        </form>
      `;
    const modal = openModal(html);
    modal.querySelector('#close-modal').addEventListener('click', closeModal);
    modal.querySelector('#cancel').addEventListener('click', closeModal);
    modal.querySelector('#save').addEventListener('click', async () => {
      const productId = modal.querySelector('#prod-id').value.trim(); const price = modal.querySelector('#prod-price').value; const booths = Array.from(modal.querySelector('#prod-booths').selectedOptions).map(o => o.value);
      if (!productId || !price) { alert('Vyplňte id produktu a cenu'); return; }
      try {
        const form = new FormData(); form.set('product_id', productId); form.set('event_id', eventId); form.set('price', price); form.set('booth_ids', JSON.stringify(booths));
        const res = await fetch('/api/product_event_prices/create', { method: 'POST', body: form });
        if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
        closeModal();
        resetEventDataCache();
      } catch (e) { alert('Nelze přidat produkt: ' + e.message); }
    });
    return;
  }

  // add manager
  if (event.target.matches('#add-manager')) {
    await openAssignEmployeeModal(true)
    return;
  }

  // add employee
  if (event.target.matches('#add-employee')) {
    await openAssignEmployeeModal(false)
    return;
  }

  // // úprava zaměstnance
  // const editButton = event.target.closest('.edit.icon-btn');
  // if (editButton) {
  //   const row = editButton.closest('tr[data-employee]');
  //   openEditOverlay(row);
  //   return;
  // }

  const editBoothBtn = event.target.closest('.edit-booth');
  if (editBoothBtn) {
    const row = editBoothBtn.closest('tr[id]');
    await openEditBoothModal(row);
    return;
  }

  // const delB = event.target.closest('.delete-booth');
  // if (delB) {
  //   const id = delB.dataset.id; if (!confirm('Opravit stánku? Smazat stánek?')) return; // typo preserved? change to Czech wording
  //   try {
  //     const form = new FormData(); form.set('id', id);
  //     const res = await fetch('/api/booths/delete', { method: 'DELETE', body: form });
  //     if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
  //     fetchEvent();
  //   } catch (e) { alert('Nelze smazat stánek: ' + e.message); }
  //   return;
  // }

  const editEmp = event.target.closest('.edit-employee');
  if (editEmp) {
    const id = editEmp.dataset.id;
    const eventData = await getEventData();
    const emp = eventData.employees.find(employee => employee.id === id); if (!emp) return;
    // simple modal to change role or booths assignment (UI only)
    const availableBooths = eventData.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('');
    const html = `
          <header>
            <h2>Upravit zaměstnance</h2>
            <button id="close-modal">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </header>
          <form id="edit-booth-form">
            <div class="form-row">
              <label for="emp-username">Uživatel</label>
              <input id="emp-username" type="text" value="${escapeHTML(emp.username)}" disabled/>
            </div>
            <div class="form-row">
              <label for="employee-booths">Přiřazené stánky (více pro Ctrl/Shift)</label>
              <select id="employee-booths" multiple size="6">${availableBooths}</select>
            </div>
            <div class="modal-actions">
              <button id="cancel" class="btn btn-ghost">Zrušit</button>
              <button id="save" class="btn btn-primary">Uložit</button>
            </div>
          </form>
        `;
    const modal = openModal(html);
    modal.querySelector('#close-modal').addEventListener('click', closeModal);
    modal.querySelector('#cancel').addEventListener('click', closeModal);
    // preselect current booths
    const sel = modal.querySelector('#employee-booths');
    const assigned = (emp.booths || []).map(b => b.booth_id);
    for (const opt of sel.options) { if (assigned.includes(opt.value)) opt.selected = true; }

    modal.querySelector('#save').addEventListener('click', async () => {
      const selected = Array.from(sel.selectedOptions).map(o => o.value);
      try {
        // API shape: create role rows for each selected booth or remove others. Implement via backend endpoints.
        const form = new FormData(); form.set('employee_id', id); form.set('event_id', eventId); form.set('booth_ids', JSON.stringify(selected));
        const res = await fetch('/api/employee_event_booth_roles/update_for_employee', { method: 'POST', body: form });
        if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
        closeModal();
        resetEventDataCache();
      } catch (e) { alert('Nelze upravit zaměstnance: ' + e.message); }
    });
    return;
  }

  // const delEmp = event.target.closest('.delete-employee');
  // if (delEmp) {
  //   const id = delEmp.dataset.id;
  //   if (!confirm('Odebrat přiřazení zaměstnance?')) return;
  //   try {
  //     const form = new FormData();
  //     form.set('employee_id', id);
  //     form.set('event_id', eventId);
  //     const res = await fetch(
  //       '/api/employee_event_booth_roles/delete_for_employee',
  //       { method: 'DELETE', body: form }
  //     );
  //     if (!res.ok) {
  //       const j = await res.json().catch(() => ({ error: 'Chyba' }));
  //       throw new Error(j.error || 'Chyba');
  //     }
  //     fetchEvent();
  //   } catch (e) { alert('Nelze odebrat zaměstnance: ' + e.message); }
  //   return;
  // }

  const editP = event.target.closest('.edit-product');
  if (editP) {
    const id = editP.dataset.id;
    const eventData = await getEventData();
    const products = eventData.products.find(x => x.id === id);
    if (!products) return;
    const availableBooths = eventData.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('');
    const html = `
          <header>
            <h2>Upravit produkt</h2>
            <button id="close-modal">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
            </button>
          </header>
          <form id="edit-booth-form">
            <div class="form-row">
              <label for="prod-name">Název</label>
              <input id="prod-name" type="text" value="${escapeHTML(products.name)}"/>
            </div>
            <div class="form-row">
              <label for="prod-price">Cena (Kč)</label>
              <input id="prod-price" type="number" value="${escapeHTML(String(products.price || ''))}"/>
            </div>
            <div class="form-row">
              <label for="prod-booths">Přiřadit stánky</label>
              <select id="prod-booths" multiple size="6">${availableBooths}</select>
            </div>
            <div class="modal-actions">
              <button id="cancel" class="btn btn-ghost">Zrušit</button>
              <button id="save" class="btn btn-primary">Uložit</button>
            </div>
          </form>
        `;
    const modal = openModal(html);
    modal.querySelector('#close-modal').addEventListener('click', closeModal);
    modal.querySelector('#cancel').addEventListener('click', closeModal);
    const sel = modal.querySelector('#prod-booths');
    const assigned = (products.booths || []).map(b => b.booth_id);
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

  // const delP = event.target.closest('.delete-product');
  // if (delP) {
  //   const id = delP.dataset.id;
  //   if (!confirm('Odebrat tento produkt z akce?')) return;
  //   try {
  //     const form = new FormData();
  //     form.set('product_id', id);
  //     form.set('event_id', eventId);
  //     const res = await fetch('/api/product_event_prices/delete_for_product', { method: 'DELETE', body: form });
  //     if (!res.ok) {
  //       const j = await res.json().catch(() => ({ error: 'Chyba' }));
  //       throw new Error(j.error || 'Chyba');
  //     }
  //     fetchEvent();
  //   } catch (e) {
  //     alert('Nelze odebrat produkt: ' + e.message);
  //   }
  //   return;
  // }


  // kliknutí na id
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



// document.addEventListener('submit', async (event) => {
//   const addForm = event.target.closest('#add-event-form');
//   if (addForm) {
//     event.preventDefault();
//     const saveButton = addForm.querySelector('#add-event-save');
//     saveButton.disabled = true;

//     clearAddEventErrors();

//     const formData = new FormData(addForm);

//     const startAtStr = formData.get('start-at');
//     const endAtStr = formData.get('end-at');

//     const startAt = new Date(startAtStr);
//     const endAt = new Date(endAtStr);

//     if (startAtStr && !isValidDate(startAt)) {
//       showAddEventErrors('invalid_start_at');
//       saveButton.disabled = false;
//       return;
//     }
//     if (endAtStr && !isValidDate(endAt)) {
//       showAddEventErrors('invalid_end_at');
//       saveButton.disabled = false;
//       return;
//     }

//     if (startAtStr) {
//       const startAtIsoUtc = startAt.toISOString();
//       formData.set('start-at', startAtIsoUtc);
//     }

//     if (endAtStr) {
//       const endAtIsoUtc = endAt.toISOString();
//       formData.set('end-at', endAtIsoUtc);
//     }

//     formData.set('name', formData.get('name').trim());

//     try {
//       const response = await fetch('/api/events/create', {
//         method: 'post',
//         body: formData
//       });

//       if (response.status === 401) {
//         const json = await response.json();
//         window.location.href = json.redirect_url;
//         return;
//       }

//       const data = await response.json();

//       if (response.status === 403 && data.error === 'insufficient_priviliges') {
//         showAddEventErrors('insufficient_priviliges');
//         saveButton.disabled = false;
//         return;
//       }

//       if (response.status === 400) {
//         showAddEventErrors(data.error || 'invalid_request', data.detail);
//         saveButton.disabled = false;
//         return;
//       }

//       if (!response.ok) {
//         showAddEventErrors('unexpected_error');
//         saveButton.disabled = false;
//         return;
//       }

//       const overlay = document.querySelector('#add-event-overlay');
//       if (overlay) overlay.remove();

//       resetEventsCache();
//       loadPage({
//         table: true
//       });

//     } catch (err) {
//       showAddEventErrors('unexpected_error');
//     } finally {
//       saveButton.disabled = false;
//     }
//     return;
//   }

//   // uprav zaměstnance
//   const editFrom = event.target.closest('#edit-form');
//   if (editFrom) {
//     event.preventDefault();
//     const saveButton = editFrom.querySelector('#edit-save');
//     saveButton.disabled = true;

//     clearEditErrors();

//     const formData = new FormData(editFrom);

//     formData.set('username', formData.get('username').trim());
//     formData.set('email', formData.get('email').trim());

//     const result = await editEmployee(formData);

//     saveButton.disabled = false;

//     if (result === true) {
//       const overlayEl = document.querySelector('#edit-overlay');
//       if (overlayEl) overlayEl.remove();
//       resetEmployeesCache();
//       loadPage({
//         table: true,
//         header: true
//       });
//       return;
//     }

//     showEditErrors(result);
//     return;
//   }

//   // odstraň zaměstnance
//   const deleteForm = event.target.closest('#delete-form');
//   if (deleteForm) {
//     event.preventDefault();
//     const deleteButton = deleteForm.querySelector('#delete-confirm');
//     deleteButton.disabled = true;

//     clearDeleteErrors();

//     const formData = new FormData(deleteForm);

//     const result = await deleteEmployee(formData);

//     deleteButton.disabled = false;

//     if (result === true) {
//       const overlayEl = document.querySelector('#delete-overlay');
//       if (overlayEl) overlayEl.remove();
//       resetEmployeesCache();
//       loadPage({
//         table: true
//       });
//       return;
//     }

//     showDeleteErrors(result);
//     return;
//   }
// });


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
  tableHeader = false,
  header = false,
  sidebar = false,
  boothsTable = false,
  managersTable = false,
  employeesTable = false,
  productsTable = false } = {}) {
  const eventData = await getEventData();
  const toLoad = [];
  if (tableHeader) toLoad.push(renderEvent(eventData));
  if (header) toLoad.push(renderHeader());
  if (sidebar) toLoad.push(renderSidebar());
  if (boothsTable) toLoad.push(renderBooths(eventData));
  if (managersTable) toLoad.push(renderManagers(eventData));
  if (employeesTable) toLoad.push(renderEmployees(eventData));
  if (productsTable) toLoad.push(renderProducts(eventData));
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
  _getEventDataPromise = null;
}

function getEventData() {
  if (_eventDataCache.data && _eventDataCache.expiry > Date.now()) {
    return Promise.resolve(_eventDataCache.data);
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

      _eventDataCache.data = {};
      _eventDataCache.data.event = resData.event;
      _eventDataCache.data.booths = resData.booths;
      _eventDataCache.data.employees = resData.employees;
      _eventDataCache.data.products = resData.products;

      // přidává extra info k zaměstnancům
      _eventDataCache.data.employees.forEach((emp) => {
        // filtruje stánky pro tuto akci: id stánků existujících v resData.booths
        const empBoothsForEvent = (emp.booths || []).filter(empBooth => resData.booths.some(eventBooth => eventBooth.id === empBooth.booth_id));
        const isManager = empBoothsForEvent.length === 0;

        // přidává název stánku
        const assignedBooths = empBoothsForEvent.map(booth => ({ id: booth.booth_id, name: findBoothNameById(booth.booth_id, _eventDataCache.data.booths), role: booth.role }));

        // přidává upravené stánky a isManager
        emp.booths = assignedBooths;
        emp.isManager = isManager
      });

      // přidává jméno stánku
      _eventDataCache.data.products.forEach((product) => {
        product.booths.forEach(booth => {
          booth.name = findBoothNameById(booth.booth_id, _eventDataCache.data.booths);
        });
      });

      _eventDataCache.expiry = Date.now() + cache_time_ms;

      console.log(_eventDataCache.data);

      return _eventDataCache.data;

    } catch (err) {
      let errorMessage = '';
      if (err.message === 'no_event_id') {
        errorMessage = 'Nelze určit ID akce z URL.';
      } else if (err.message === 'insufficient_priviliges') {
        errorMessage = 'Nejste admin nebo manažer akce.';
      } else {
        errorMessage = 'Nepovedlo se načíst akci';
      }
      card.insertAdjacentHTML('afterbegin', `
      <div id="load-error-message" class="panel">
        ${escapeHTML(errorMessage)}
      </div>`);

      return null;
    } finally {
      _getEventDataPromise = null;
    }
  })();

  return _getEventDataPromise;
}


function boothIsSearchedFor(booth, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const id = String(booth.id || '').toLowerCase();
  const name = String(booth.name || '').toLowerCase();
  const type = String(boothTypeToDisplay(booth.booth_type) || '').toLowerCase();

  const searchable = `${id} ${name} ${type}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      // key=value (id=... name=... type=...)
      const [searchKeyWord, search] = query.split('=');
      if (['id', 'identifier'].includes(searchKeyWord)) {
        if (!id.includes(search)) return false;
      } else if (['name', 'stánek', 'stanek', 'booth', 'nazev', 'název'].includes(searchKeyWord)) {
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
  const id = String(employee.id || '').toLowerCase();
  const username = String(employee.username || '').toLowerCase();
  const email = String(employee.email || '').toLowerCase();
  let booths = employee.booths.length === 0 ? '-' : '';
  for (const booth of employee.booths) {
    booths += `${booth.name.toLowerCase()}, `;
  }

  const searchable = `${id} ${username} ${email} ${booths}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');

      if (['id', 'identifier'].includes(searchKeyWord)) {
        if (!id.includes(search)) return false;
      } else if (['username',
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
  const id = String(product.id || '').toLowerCase();
  const name = String(product.name || '').toLowerCase();
  const price = String(product.price || '').toLowerCase();
  let categories = product.categories.length === 0 ? '-' : '';
  for (const category of product.categories) {
    categories += `${category.toLowerCase()}, `;
  }
  let booths = product.booths.length === 0 ? '-' : '';
  for (const booth of product.booths) {
    booths += `${booth.name.toLowerCase()} `;
  }

  const searchable = `${id} ${name} ${price} ${categories} ${booths}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');
      if (['id', 'identifier'].includes(searchKeyWord)) {
        if (!id.includes(search)) return false;
      } else if (['name', 'produkt', 'product', 'nazev', 'název'].includes(searchKeyWord)) {
        if (!name.includes(search)) return false;
      } else if (['price', 'cena'].includes(searchKeyWord)) {
        if (!price.includes(search)) return false;
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


function findBoothNameById(id, booths) {
  const booth = booths.find(booth => booth.id === id);
  return booth ? booth.name : id;
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
  document.getElementById('event-datetime').textContent = `${start} - ${end}`;
  document.getElementById('event-created-at').textContent = formatDateTimeISOToDisplay(event.created_at);
}


function renderBooths(eventData) {
  const searchQuery = boothsSearchBar.value;
  const booths = eventData.booths;

  let rows = '';

  booths.forEach((booth, idx) => {
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
  // [{id, username, email, booths: [{booth_id, role}, ...]}, ...]
  const managers = eventData.employees.filter(employee => employee.isManager);

  let rows = '';

  managers.forEach((manager, idx) => {
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
          <button class="icon-btn delete delete-employee" data-id="${manager.id}">
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

  let rows = '';

  employees.forEach((employee, idx) => {
    if (!employeeIsSearchedFor(employee, searchQuery)) return;
    const boothsStr = employee.booths.map(booth => `<span data-direct-to="${booth.id}">${escapeHTML(booth.name)}</span>`).join(', ') || '-';

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
          <button class="icon-btn delete delete-employee" data-id="${employee.id}">
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
  const products = eventData.products;

  let rows = '';

  products.forEach((product, idx) => {
    if (!productIsSearchedFor(product, searchQuery)) return;
    const booths = (product.booths || []).map(booth => `<span data-direct-to="${booth.booth_id}">${booth.name}</span>`).filter(Boolean).join(', ') || '-';
    const categories = (product.categories || []).join(', ') || '-';

    rows += `
      <tr id="${product.id}">
        <td>${idx + 1}</td>
        <td>${escapeHTML(product.name)}</td>
        <td>${escapeHTML(String(product.price || '-'))}</td>
        <td>${booths}</td>
        <td>${categories}</td>
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

  productsTableBody.innerHTML = rows || `<tr><td class="muted" colspan="5">Žádné produkty.</td></tr>`;
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


async function openAssignEmployeeModal(asManager) {
  const booths = (await getEventData()).booths;
  const html = `
        <header>
          <h2>${asManager ? 'Přiřadit manažera' : 'Přiřadit zaměstnance'}</h2>
          <button id="close-modal">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <form id="edit-booth-form">
          <div class="form-row">
            <label for="emp-id">Employee ID</label>
            <input id="emp-id" type="text" placeholder="UUID zaměstnance"/>
          </div>
          ${asManager ? '' :
      `<div class="form-row">
              <label for="emp-booth">Stánek (pokud ne manažer)</label>
              <select id="emp-booth">
                <option value="">-- vyberte --</option>
                ${booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('')}'
              </select>
            </div>'`}
          <div class="modal-actions">
            <button id="cancel" class="btn btn-ghost">Zrušit</button>
            <button id="save" class="btn btn-primary">Přiřadit</button>
          </div>
        </form>
      `;
  const modal = openModal(html);
  modal.querySelector('#close-modal').addEventListener('click', closeModal);
  modal.querySelector('#cancel').addEventListener('click', closeModal);
  modal.querySelector('#save').addEventListener('click', async () => {
    const empId = modal.querySelector('#emp-id').value.trim();
    const boothId = asManager ? null : (modal.querySelector('#emp-booth').value || null);
    if (!empId) { alert('Zadejte ID zaměstnance'); return; }
    try {
      const form = new FormData(); form.set('employee_id', empId); form.set('event_id', eventId); if (boothId) form.set('booth_id', boothId);
      const res = await fetch('/api/employee_event_booth_roles/create', { method: 'POST', body: form });
      if (res.status === 401) { const j = await res.json(); window.location.href = j.redirect_url; return; }
      if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
      closeModal()
      resetEventDataCache();
    } catch (e) { alert('Nelze přiřadit zaměstnance: ' + e.message); }
  });
}


async function openEditBoothModal(row) {
  const id = row.id;
  const booth = (await getEventData()).booths.find(booth => booth.id === id);
  if (!booth) return;

  const html = `
    <header>
      <h2>Upravit stánek</h2>
      <button id="close-modal">
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
        <button id="cancel" class="btn btn-ghost">Zrušit</button>
        <button id="save" class="btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
  const modal = openModal(html);
  modal.querySelector('#close-modal').addEventListener('click', closeModal);
  modal.querySelector('#cancel').addEventListener('click', closeModal);
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