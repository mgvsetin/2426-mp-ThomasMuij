import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { formatDateTimeISOToDisplay } from "../general/date_utils.js";
import { directTo, markSelectedRow, selectRow, unselectRow } from "../general/table_utils.js";


const card = document.querySelector('#card');

// cache of fetched data
let _data = { eventId: null, event: null, booths: [], employees: [], products: [] };
fetchEventData();


loadPage({
  tableHeader: true,
  header: true,
  sidebar: true,
  boothsTable: true,
  employeesTable: true,
  productsTable: true
});


document.addEventListener('click', (event) => {
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
            <label>Název</label>
            <input id="booth-name" type="text"/>
          </div>
          <div class="form-row">
            <label>Typ</label>
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
        form.set('event_id', _data.eventId);
        const res = await fetch('/api/booths/create', { method: 'POST', body: form });
        if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
        closeModal(); fetchEventData();
      } catch (e) { alert('Nelze vytvořit stánek: ' + e.message); }
    });
    return;
  }

  // open graphs, probably just add the graphs to the page itself (maybe under something like show graphs)
  if (event.target.matches('#open-graphs')) {
    // either navigate to a dedicated graphs page or open overlay
    // We'll navigate to /events/<id>/graphs (implement server-side) as requested
    window.location.href = `/events/${encodeURIComponent(_data.eventId)}/graphs`;
    return;
  }

  // Edit / Delete Event
  if (event.target.matches('#edit-event')) {
    const ev = _data.event; if (!ev) return;
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
            <label>Název</label>
            <input id="event-name-input" type="text" value="${escapeHTML(ev.name || '')}"/>
          </div>
          <div class="form-row">
            <label>Začátek</label>
            <input id="event-start-input" type="datetime-local" value="${ev.start_at ? new Date(ev.start_at).toISOString().slice(0, 16) : ''}"/>
          </div>
          <div class="form-row">
            <label>Konec</label>
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
        const form = new FormData(); form.set('id', _data.eventId); form.set('name', name);
        if (start) form.set('start-at', new Date(start).toISOString());
        if (end) form.set('end-at', new Date(end).toISOString());
        const res = await fetch('/api/events/edit', { method: 'POST', body: form });
        if (res.status === 401) { const j = await res.json(); window.location.href = j.redirect_url; return; }
        if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
        closeModal(); fetchEventData();
      } catch (e) { alert('Nelze upravit akci: ' + e.message); }
    });
    return;
  }

  // Add product and add employee/manager buttons (open small modals)
  if (event.target.matches('#add-product')) {
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
            <label>Produkt (existující ID)</label>
            <input id="prod-id" type="text" placeholder="UUID produktu (pokud nové, vytvořte produkt jinde)"/>
          </div>
          <div class="form-row">
            <label>Cena (Kč)</label>
            <input id="prod-price" type="number"/>
          </div>
          <div class="form-row">
            <label>Přiřadit stánky (volitelné)</label>
            <select id="prod-booths" multiple size="6">${_data.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('')}</select>
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
        const form = new FormData(); form.set('product_id', productId); form.set('event_id', _data.eventId); form.set('price', price); form.set('booth_ids', JSON.stringify(booths));
        const res = await fetch('/api/product_event_prices/create', { method: 'POST', body: form });
        if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
        closeModal(); fetchEventData();
      } catch (e) { alert('Nelze přidat produkt: ' + e.message); }
    });
    return;
  }

  // add manager
  if (event.target.matches('#add-manager')) {
    openAssignEmployeeModal(true)
    return;
  }

  // add employee
  if (event.target.matches('#add-employee')) {
    openAssignEmployeeModal(false)
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
    openEditBoothModal(row);
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
    const id = editEmp.dataset.id; const emp = _data.employees.find(x => x.id === id); if (!emp) return;
    // simple modal to change role or booths assignment (UI only)
    const availableBooths = _data.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('');
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
              <label>Uživatel</label>
              <input type="text" value="${escapeHTML(emp.username)}" disabled/>
            </div>
            <div class="form-row">
              <label>Přiřazené stánky (více pro Ctrl/Shift)</label>
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
        const form = new FormData(); form.set('employee_id', id); form.set('event_id', _data.eventId); form.set('booth_ids', JSON.stringify(selected));
        const res = await fetch('/api/employee_event_booth_roles/update_for_employee', { method: 'POST', body: form });
        if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
        closeModal(); fetchEventData();
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
  //     form.set('event_id', _data.eventId);
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
    const id = editP.dataset.id; const p = _data.products.find(x => x.id === id); if (!p) return; const availableBooths = _data.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join(''); const html = `
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
              <label>Název</label>
              <input id="prod-name" type="text" value="${escapeHTML(p.name)}"/>
            </div>
            <div class="form-row">
              <label>Cena (Kč)</label>
              <input id="prod-price" type="number" value="${escapeHTML(String(p.price || ''))}"/>
            </div>
            <div class="form-row">
              <label>Přiřadit stánky</label>
              <select id="prod-booths" multiple size="6">${availableBooths}</select>
            </div>
            <div class="modal-actions">
              <button id="cancel" class="btn btn-ghost">Zrušit</button>
              <button id="save" class="btn btn-primary">Uložit</button>
            </div>
          </form>
        `; const modal = openModal(html); modal.querySelector('#close-modal').addEventListener('click', closeModal); modal.querySelector('#cancel').addEventListener('click', closeModal); const sel = modal.querySelector('#prod-booths'); const assigned = (p.booths || []).map(b => b.booth_id); for (const opt of sel.options) { if (assigned.includes(opt.value)) opt.selected = true; } modal.querySelector('#save').addEventListener('click', async () => { const name = modal.querySelector('#prod-name').value.trim(); const price = modal.querySelector('#prod-price').value; const booths = Array.from(sel.selectedOptions).map(o => o.value); if (!name || !price) { alert('Vyplňte název a cenu'); return; } try { const form = new FormData(); form.set('product_id', id); form.set('name', name); form.set('price', price); form.set('booth_ids', JSON.stringify(booths)); const res = await fetch('/api/product_event_prices/update_for_product', { method: 'POST', body: form }); if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); } closeModal(); fetchEventData(); } catch (e) { alert('Nelze upravit produkt: ' + e.message); } }); return;
  }

  // const delP = event.target.closest('.delete-product');
  // if (delP) {
  //   const id = delP.dataset.id;
  //   if (!confirm('Odebrat tento produkt z akce?')) return;
  //   try {
  //     const form = new FormData();
  //     form.set('product_id', id);
  //     form.set('event_id', _data.eventId);
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
//     const form = new FormData(); form.set('id', _data.eventId);
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
    const query = searchBar.value.trim().toLowerCase();
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
  employeesTable = false,
  productsTable = false } = {}) {
  if (!_data) await fetchEventData();
  const toLoad = [];
  if (tableHeader) toLoad.push(renderEvent());
  if (header) toLoad.push(renderHeader());
  if (sidebar) toLoad.push(renderSidebar());
  if (boothsTable) toLoad.push(renderBooths());
  if (employeesTable) toLoad.push(renderEmployees());
  if (productsTable) toLoad.push(renderProducts());
  await Promise.all(toLoad);
}


function getEventIdFromPath() {
  // filter(Boolean) odstraňuje falsy hodnoty jako ""
  const parts = window.location.pathname.split('/').filter(Boolean);
  // mělo by být ['events','<id>','manager']
  if (parts[0] === 'events' && parts.length >= 2) {
    _data.eventId = parts[1];
    return parts[1];
  }
  return null;
}


async function fetchEventData() {
  console.log('make this return a promise (for repeated calls), add way to clear the _data')

  if (!_data.eventId) getEventIdFromPath();

  try {
    if (!_data.eventId) {
      throw new Error('no_event_id');
    }

    const res = await fetch(`/api/events/${encodeURIComponent(_data.eventId)}`);

    if (res.status === 401) {
      const json = await res.json();
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

    _data.event = resData.event;
    _data.booths = resData.booths || [];
    _data.employees = resData.employees || [];
    _data.products = resData.products || [];
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
  }
}


function isSearchedFor(ev, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const id = String(ev.id || '').toLowerCase();
  const name = String(ev.name || '').toLowerCase();
  const startAt = formatDateTimeISOToDisplay(ev.start_at || '').toLowerCase();
  const endAt = formatDateTimeISOToDisplay(ev.end_at || '').toLowerCase();
  const created_at = formatDateTimeISOToDisplay(ev.created_at || '').toLowerCase();

  const searchable = `${id} ${name} ${startAt} ${endAt} ${created_at}`;

  for (const q of queries) {
    if (!q.includes('=')) {
      if (!searchable.includes(q)) return false;
    } else {
      // key=value (id=..., name=..., start_at=..., end_at=...)
      const [k, v] = q.split('=');
      if (['id', 'identifier'].includes(k)) {
        if (!id.includes(v)) return false;
      } else if (['name', 'akce', 'nazev', 'název'].includes(k)) {
        if (!name.includes(v)) return false;
      } else if (['start_at', 'začátek', 'zacatek'].includes(k)) {
        if (!startAt.includes(v)) return false;
      } else if (['end_at', 'konec'].includes(k)) {
        if (!endAt.includes(v)) return false;
      } else if (['created_at', 'vytvořena', 'vytvorena'].includes(k)) {
        if (!created_at.includes(v)) return false;
      } else {
        if (!searchable.includes(q)) return false;
      }
    }
  }
  return true;
}


function findBoothNameById(id) {
  const b = _data.booths.find(x => x.id === id);
  return b ? b.name : id;
}


function renderEvent() {
  const ev = _data.event;
  if (!ev) return;
  document.getElementById('event-name').textContent = ev.name || '-';
  const start = formatDateTimeISOToDisplay(ev.start_at);
  const end = formatDateTimeISOToDisplay(ev.end_at);
  document.getElementById('event-datetime').textContent = start === '-' && end === '-' ? '-' : `${start} - ${end}`;
  document.getElementById('event-id').textContent = `(${ev.id})`;
  document.getElementById('event-created-by').textContent = ev.created_by || '-';
  document.getElementById('event-created-at').textContent = formatDateTimeISOToDisplay(ev.created_at);
}


function renderBooths() {
  const tbody = document.querySelector('#booths-table tbody');
  tbody.innerHTML = '';
  if (!_data.booths || !_data.booths.length) {
    tbody.innerHTML = `<tr><td class="muted" colspan="5">Žádné stánky.</td></tr>`; return;
  }

  _data.booths.forEach((b, i) => {
    const tr = document.createElement('tr');
    tr.id = b.id;
    tr.innerHTML = `
          <td>${i + 1}</td>
          <td class="event-name">${escapeHTML(b.name)}</td>
          <td>${escapeHTML(b.booth_type)}</td>
          <td class="muted">${escapeHTML(b.id)}</td>
          <td class="actions">
            <button class="icon-btn edit edit-booth" title="Upravit">✏️</button>
            <button class="icon-btn delete delete-booth" title="Smazat">🗑️</button>
          </td>
        `;
    tbody.appendChild(tr);
  });

  markSelectedRow(card);
}

function renderEmployees() {
  const managersBody = document.querySelector('#managers-table tbody');
  const employeesBody = document.querySelector('#employees-table tbody');
  managersBody.innerHTML = '';
  employeesBody.innerHTML = '';

  if (!_data.employees || !_data.employees.length) {
    managersBody.innerHTML = `<tr><td class="muted" colspan="5">Žádní manažeři.</td></tr>`;
    employeesBody.innerHTML = `<tr><td class="muted" colspan="5">Žádní zaměstnanci.</td></tr>`;
    return;
  }

  // employees array: {id, username, email, booths: [{booth_id, role}, ...]}
  const managers = [];
  const others = [];

  for (const emp of _data.employees) {
    // filter booths for this event: booth ids that exist in _data.booths
    const boothsForEvent = (emp.booths || []).filter(b => _data.booths.some(x => x.id === b.booth_id));
    const hasManagerRole = boothsForEvent.length === 0; // boothsForEvent.some(b => b.role === 'event_manager');
    const assignedBooths = boothsForEvent.filter(b => b.booth_id).map(b => ({ id: b.booth_id, name: findBoothNameById(b.booth_id), role: b.role }));

    const row = { id: emp.id, username: emp.username, email: emp.email, booths: assignedBooths, role: hasManagerRole ? 'event_manager' : (assignedBooths[0] ? assignedBooths[0].role : '-') };
    if (hasManagerRole) managers.push(row); else others.push(row);
  }

  if (managers.length === 0) { employeesBody.innerHTML = `<tr><td class="muted" colspan="5">Žádní manažeři.</td></tr>`; }
  managers.forEach((manager, idx) => {
    const tr = document.createElement('tr');
    tr.id = manager.id;
    tr.innerHTML = `
          <td>${idx + 1}</td>
          <td>${escapeHTML(manager.username)} <div class="muted" style="font-size:12px">(${escapeHTML(manager.id)})</div></td>
          <td class="muted">${escapeHTML(manager.email)}</td>
          <td>-</td>
          <td class="actions">
            <button class="icon-btn edit edit-employee" data-id="${manager.id}" title="Upravit">✏️</button>
            <button class="icon-btn delete delete-employee" data-id="${manager.id}" title="Odebrat">🗑️</button>
          </td>
        `;
    employeesBody.appendChild(tr);
  });

  if (others.length === 0) { employeesBody.innerHTML = `<tr><td class="muted" colspan="5">Žádní zaměstnanci.</td></tr>`; }
  others.forEach((employee, idx) => {
    const boothsStr = employee.booths.map(b => `<span data-direct-to="${b.id}">${escapeHTML(b.name)}</span>`).join(', ') || '-';
    const tr = document.createElement('tr');
    tr.id = employee.id;
    tr.innerHTML = `
          <td>${idx + 1}</td>
          <td>${escapeHTML(employee.username)} <div class="muted" style="font-size:12px">(${escapeHTML(employee.id)})</div></td>
          <td class="muted">${escapeHTML(employee.email)}</td>
          <td>${boothsStr}</td>
          <td class="actions">
            <button class="icon-btn edit edit-employee" data-id="${employee.id}" title="Upravit">✏️</button>
            <button class="icon-btn delete delete-employee" data-id="${employee.id}" title="Odebrat">🗑️</button>
          </td>
        `;
    employeesBody.appendChild(tr);
  });

  markSelectedRow(card);
}

function renderProducts() {
  const tbody = document.querySelector('#products-table tbody');
  tbody.innerHTML = '';
  if (!_data.products || !_data.products.length) { tbody.innerHTML = `<tr><td class="muted" colspan="5">Žádné produkty nebo ceny.</td></tr>`; return; }

  _data.products.forEach((p, i) => {
    const booths = (p.booths || []).map(b => `<span data-direct-to="${b.booth_id}">${findBoothNameById(b.booth_id)}</span>`).filter(Boolean).join(', ') || '-';
    const tr = document.createElement('tr');
    tr.id = p.id;
    tr.innerHTML = `
          <td>${i + 1}</td>
          <td>${escapeHTML(p.name)}</td>
          <td>${escapeHTML(String(p.price || '-'))}</td>
          <td>${booths}</td>
          <td class="actions">
            <button class="icon-btn edit edit-product" data-id="${p.id}" title="Upravit">✏️</button>
            <button class="icon-btn delete delete-product" data-id="${p.id}" title="Odebrat">🗑️</button>
          </td>
        `;
    tbody.appendChild(tr);
  });

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


function openAssignEmployeeModal(asManager) {
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
            <label>Employee ID</label>
            <input id="emp-id" type="text" placeholder="UUID zaměstnance"/>
          </div>
          ${asManager ? '' :
      `<div class="form-row">
              <label>Stánek (pokud ne manažer)</label>
              <select id="emp-booth">
                <option value="">-- vyberte --</option>
                ${_data.booths.map(b => `<option value="${b.id}">${escapeHTML(b.name)}</option>`).join('')}'
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
      const form = new FormData(); form.set('employee_id', empId); form.set('event_id', _data.eventId); if (boothId) form.set('booth_id', boothId);
      const res = await fetch('/api/employee_event_booth_roles/create', { method: 'POST', body: form });
      if (res.status === 401) { const j = await res.json(); window.location.href = j.redirect_url; return; }
      if (!res.ok) { const j = await res.json().catch(() => ({ error: 'Chyba' })); throw new Error(j.error || 'Chyba'); }
      closeModal(); fetchEventData();
    } catch (e) { alert('Nelze přiřadit zaměstnance: ' + e.message); }
  });
}


function openEditBoothModal(row) {
  const id = row.id;
  const booth = _data.booths.find(booth => booth.id === id);
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
        <label>Název</label>
        <input id="booth-name" type="text" value="${escapeHTML(booth.name)}"/>
      </div>
      <div class="form-row">
        <label>Typ</label>
        <select id="booth-type">
          <option value="seller" ${booth.booth_type === 'seller' ? 'selected' : ''}>seller</option>
          <option value="cashier" ${booth.booth_type === 'cashier' ? 'selected' : ''}>cashier</option>
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
      closeModal(); fetchEventData();
    } catch (e) { alert('Nelze upravit stánek: ' + e.message); }
  });
}