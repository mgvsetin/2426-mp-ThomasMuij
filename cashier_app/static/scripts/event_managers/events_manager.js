import { formatDateTimeISOToDisplay, isValidDate } from "../general/date_utils.js";
import { getEvents, resetEventsCache } from "../general/events.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { escapeHTML, safeParse } from "../general/html_display_utils.js";
import { getSessionInfo } from "../general/session.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { handleCopyPasteOnKeydown, handleRowSelection, markSelectedRows, unselectRows } from "../general/table_utils.js";

const searchBar = document.querySelector('#search-bar');
const addEventButton = document.querySelector('#add-event-button');

const card = document.querySelector('#card');

const activeBody = document.querySelector('#active-table-body');
const futureBody = document.querySelector('#future-table-body');
const pastBody = document.querySelector('#past-table-body');

const activeCountEl = document.querySelector('#active-count');
const futureCountEl = document.querySelector('#future-count');
const pastCountEl = document.querySelector('#past-count');

const tableHeaders = document.querySelectorAll('thead');

const orderBy = { key: '', ascending: true }; // key: 'start_at', 'end_at', 'created_at'


async function addAddEventButton() {
  const sessionInfo = await getSessionInfo().catch(() => { });
  if (!sessionInfo) return;
  if (!sessionInfo.employee.is_admin) return;
  addEventButton.classList.add('show');
}
addAddEventButton();


resetEventsCache();
loadPage({
  table: true,
  header: true,
  sidebar: true
});

async function loadPage({
  table = false,
  header = false,
  sidebar = false } = {}) {
  const toLoad = [];
  if (table) toLoad.push(renderTableRows());
  if (header) toLoad.push(renderHeader());
  if (sidebar) toLoad.push(renderSidebar());
  await Promise.all(toLoad);
}


document.addEventListener('click', (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) return;

  if (event.target.matches('#add-event-button')) {
    openAddEventOverlay();
    return;
  }

  // klinutí na span v záhlaví
  // nastavuje řazení
  const headerEl = event.target.closest('th');
  if (headerEl && event.target.matches('span')) {
    const id = headerEl.id || '';
    // includes protože některé mají -future a -past
    if (id.includes('name-header')) {
      toggleOrder('name');
    } else if (id.includes('start-at-header')) {
      toggleOrder('start_at');
    } else if (id.includes('end-at-header')) {
      toggleOrder('end_at');
    } else if (id.includes('created-at-header')) {
      toggleOrder('created_at');
    } else {
      return;
    }

    document.querySelectorAll('.order-by-arrow').forEach(el => el.remove());
    if (orderBy.key) {
      // nastavuje šipky v záhlaví (pro aktivní, bodoucí i minulé)
      const selector = `[id*="${id.split('-header')[0]}-header"]`
      const headersToMark = document.querySelectorAll(selector);
      headersToMark.forEach(headerToMark => {
        const arrow = document.createElement('span');
        arrow.classList.add('order-by-arrow');
        arrow.innerHTML = orderBy.ascending ? '&#8595;' : '&#8593;';
        headerToMark.querySelector('div').appendChild(arrow);
      })
    }

    loadPage({
      table: true
    });
    return;
  }

  // kliknutí na úpravu akce --> /events/id akce/manager/
  const editButton = event.target.closest('.edit.icon-btn');
  if (editButton) {
    const row = editButton.closest('tr[data-event]');
    if (!row) return;
    const eventData = safeParse(row.getAttribute('data-event'));
    if (!eventData) return;
    window.location.href = `/events/${encodeURIComponent(eventData.id)}/manager`;
    return;
  }

  // kliknutí na řádek ho vybere
  const row = event.target.closest('tr[id]');
  if (row) {
    handleRowSelection(event);
    return;
  }

  // zrušit vytváření akce
  if (event.target.closest('#add-event-cancel') || event.target.closest('#add-event-modal-close')) {
    const overlay = document.querySelector('#add-event-overlay');
    if (overlay) overlay.remove();
    return;
  }

  if (event.target.matches('#search-bar')) {
    return;
  }
  // kliknutí na "nic" odvybere řádek
  unselectRows();
});

document.addEventListener('dblclick', (event) => {
  const row = event.target.closest('tr[data-event]');
  if (!row) return;
  const eventData = safeParse(row.getAttribute('data-event'));
  if (!eventData) return;
  window.location.href = `/events/${encodeURIComponent(eventData.id)}/manager`;
});


searchBar.addEventListener('input', () => {
  loadPage({ table: true });
});


document.addEventListener('submit', async (event) => {
  const addForm = event.target.closest('#add-event-form');
  if (addForm) {
    event.preventDefault();
    const saveButton = addForm.querySelector('#add-event-save');
    saveButton.disabled = true;

    clearAddEventErrors();

    const formData = new FormData(addForm);

    const startAtStr = formData.get('start-at');
    const endAtStr = formData.get('end-at');

    const startAt = new Date(startAtStr);
    const endAt = new Date(endAtStr);

    if (startAtStr && !isValidDate(startAt)) {
      showAddEventErrors('invalid_start_at');
      saveButton.disabled = false;
      return;
    }
    if (endAtStr && !isValidDate(endAt)) {
      showAddEventErrors('invalid_end_at');
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

    try {
      const response = await fetch('/api/events/create', {
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
        showAddEventErrors('insufficient_priviliges');
        saveButton.disabled = false;
        return;
      }

      if (response.status === 400) {
        showAddEventErrors(data.error || 'invalid_request', data.detail);
        saveButton.disabled = false;
        return;
      }

      if (!response.ok) {
        showAddEventErrors('unexpected_error');
        saveButton.disabled = false;
        return;
      }

      const overlay = document.querySelector('#add-event-overlay');
      if (overlay) overlay.remove();

      resetEventsCache();
      loadPage({
        table: true
      });

    } catch (err) {
      showAddEventErrors('unexpected_error');
    } finally {
      saveButton.disabled = false;
    }
    return;
  }
});


document.addEventListener('keydown', (event) => {
  handleRowSelection(event);
  handleCopyPasteOnKeydown(event, 'events_manager').then((result) => {
    if (['paste', 'undo-paste', 'redo-paste'].includes(result)) {
      resetEventsCache();
      loadPage({
        table: true
      });
    }
  });

  if (event.key === 'Enter') {
    const selectedRows = document.querySelectorAll('tr[data-event][selected]');
    if (selectedRows.length === 1) {
      const row = selectedRows[0];
      const eventData = safeParse(row.getAttribute('data-event'));
      if (!eventData) return;
      window.location.href = `/events/${encodeURIComponent(eventData.id)}/manager`;
    }
  }

  if (event.key === 'Escape') {
    const overlay = document.querySelector('.overlay')
    if (overlay) {
      overlay.remove();
      return;
    }
  }
});


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


function isSearchedForEvent(ev, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  // const id = String(ev.id || '').toLowerCase();
  const name = String(ev.name || '').toLowerCase();
  const startAt = formatDateTimeISOToDisplay(ev.start_at || '').toLowerCase();
  const endAt = formatDateTimeISOToDisplay(ev.end_at || '').toLowerCase();
  const created_at = formatDateTimeISOToDisplay(ev.created_at || '').toLowerCase();

  const searchable = `${name} ${startAt} ${endAt} ${created_at}`;

  for (const q of queries) {
    if (!q.includes('=')) {
      if (!searchable.includes(q)) return false;
    } else {
      // key=value ( name=... start_at=... end_at=...)
      const [k, v] = q.split('=');
      // if (['id', 'identifier'].includes(k)) {
      //   if (!id.includes(v)) return false;
      if (['name', 'akce', 'nazev', 'název'].includes(k)) {
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


function sorter(a, b) {
  if (!orderBy.key) return 0;
  const key = orderBy.key;
  let aa = a[key] || '';
  let bb = b[key] || '';

  if (key === 'start_at' || key === 'end_at' || key === 'created_at') {
    aa = aa ? new Date(aa).getTime() : Infinity;
    bb = bb ? new Date(bb).getTime() : 0;
    return (aa - bb) * (orderBy.ascending ? 1 : -1);
  }

  aa = String(aa).toLowerCase();
  bb = String(bb).toLowerCase();
  return aa.localeCompare(bb) * (orderBy.ascending ? 1 : -1);
}


function renderRowsFromList(list, tbody) {
  const searchQuery = searchBar.value;
  let rows = '';
  let idx = 1;

  for (const ev of list) {
    if (!isSearchedForEvent(ev, searchQuery)) continue;

    const createdAtStr = formatDateTimeISOToDisplay(ev.created_at);
    const startAtStr = formatDateTimeISOToDisplay(ev.start_at);
    const endAtStr = formatDateTimeISOToDisplay(ev.end_at);
    const safeEv = escapeHTML(JSON.stringify(ev));

    rows += `
        <tr id="${escapeHTML(String(ev.id))}" data-event='${safeEv}'>
          <td>${idx}</td>
          <td class="event-name">${escapeHTML(ev.name || '-')} <!-- <span class="id-muted muted">(${escapeHTML(ev.id)})</span> --> </td>
          <td class="datetime">${startAtStr}</td>
          <td class="datetime">${endAtStr}</td>
          <td class="created-at muted">${createdAtStr}</td>
          <td class="actions">
            <button class="icon-btn edit" title="Otevřít správu">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
                <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
              </svg>
            </button>
          </td>
        </tr>
      `;
    idx += 1;
  }

  tbody.innerHTML = rows || `<tr><td class="muted" colspan="6">Žádné položky.</td></tr>`;
}


async function renderTableRows() {
  const events = await getEvents().catch(() => {
    const errHTML = `<tr><td class="error-message" colspan="6">Nepovedlo se načíst akce.</td></tr>`;
    activeBody.innerHTML = errHTML;
    futureBody.innerHTML = errHTML;
    pastBody.innerHTML = errHTML;
  });
  if (!events) return;

  // rozděl akce
  const now = new Date();

  const active = [];
  const future = [];
  const past = [];

  for (const ev of events) {
    const startAt = ev.start_at ? new Date(ev.start_at) : null;
    const endAt = ev.end_at ? new Date(ev.end_at) : null;

    // není začátek, ani konec -> budoucí
    if (startAt === null && endAt === null) future.push(ev);

    // Jen konec -> podle toho jestli už byl (budoucí nebo minulá)
    else if (startAt === null && endAt !== null) {
      endAt >= now ? future.push(ev) : past.push(ev);
    }

    // Jen začátek -> podle toho jestli už byl (aktivní nebo budoucí)
    else if (endAt === null && startAt !== null) {
      startAt <= now ? active.push(ev) : future.push(ev);
    }

    // Začátek i konec:
    // Začátek ještě nebyl -> budoucí
    // Konec už byl -> minulá
    // jinak -> aktivní (start <= now <= end)
    else if (now < startAt) future.push(ev);
    else if (now > endAt) past.push(ev);
    else active.push(ev);
  }

  if (orderBy.key) {
    active.sort(sorter);
    future.sort(sorter);
    past.sort(sorter);
  }


  renderRowsFromList(active, activeBody);
  renderRowsFromList(future, futureBody);
  renderRowsFromList(past, pastBody);

  activeCountEl.textContent = active.length;
  futureCountEl.textContent = future.length;
  pastCountEl.textContent = past.length;

  markSelectedRows(card);
}


function openAddEventOverlay() {
  if (document.querySelector('#add-event-overlay')) {
    const el = document.querySelector('#add-event-name');
    if (el) el.focus();
    return;
  }

  const overlayHTML = `
    <div id="add-event-overlay" class="overlay">
      <div id="add-event-modal" class="modal">
        <header id="add-event-modal-header">
          <h2 id="add-event-overlay-title">Přidat akci</h2>
          <button id="add-event-modal-close" type="button" aria-label="Zavřít">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>

        <form id="add-event-form">
          <div class="form-row">
            <label for="add-event-name">Název akce</label>
            <input id="add-event-name" name="name" type="text" placeholder="Název akce" required />
            <div id="name-add-error" class="add-error"></div>
          </div>

          <div class="form-row">
            <label for="add-event-start-at">Začátek</label>
            <input id="add-event-start-at" name="start-at" type="datetime-local" />
            <div id="start-add-error" class="add-error"></div>
          </div>

          <div class="form-row">
            <label for="add-event-end-at">Konec</label>
            <input id="add-event-end-at" name="end-at" type="datetime-local" />
            <div id="end-add-error" class="add-error"></div>
          </div>

          <div class="form-row">
            <div id="general-add-event-error" class="add-error"></div>
          </div>

          <div id="add-event-form-actions">
            <button type="button" id="add-event-cancel">Zrušit</button>
            <button type="submit" id="add-event-save">Vytvořit</button>
          </div>
        </form>
      </div>
    </div>
  `;

  document.body.insertAdjacentHTML('beforeend', overlayHTML);

  const focusEl = document.querySelector('#add-event-name');
  if (focusEl) focusEl.focus();
}


function clearAddEventErrors() {
  const els = document.querySelectorAll('#add-event-form .add-error, #add-event-form .general-add-error');
  els.forEach(e => {
    e.innerHTML = '';
    e.classList.remove('show-add-error');
  });
}


function showAddEventErrors(error, detail) {
  const nameError = document.querySelector('#name-add-error');
  const startAtError = document.querySelector('#start-add-error');
  const endAtError = document.querySelector('#end-add-error');
  const generalError = document.querySelector('#general-add-event-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-add-error');
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
      setErr(generalError, 'Nemáte oprávnění vytvořit akci.');
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
    // case 'invalid_end_at_date':
    //   setErr(endAtError, 'Konec nemůže být nastaven do minulosti.');
    //   return;
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

  setErr(generalError, errorStr);
}
