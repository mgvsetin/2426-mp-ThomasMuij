import { getEvents, resetEventsCache } from "../general/events.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";

const searchBar = document.querySelector('#search-bar');
const addEventButton = document.querySelector('#add-event-button');

const activeBody = document.querySelector('#active-table-body');
const futureBody = document.querySelector('#future-table-body');
const pastBody = document.querySelector('#past-table-body');

const activeCountEl = document.querySelector('#active-count');
const futureCountEl = document.querySelector('#future-count');
const pastCountEl = document.querySelector('#past-count');

const tableHeaders = document.querySelectorAll('thead');

const orderBy = { key: '', ascending: true }; // key can be 'start_at', 'end_at', 'created_at'

// initialize
resetEventsCache();
loadPage({ table: true, header: true, sidebar: true });

async function loadPage({ table = false, header = false, sidebar = false } = {}) {
  const toLoad = [];
  if (table) toLoad.push(renderTableRows());
  if (header) toLoad.push(renderHeader());
  if (sidebar) toLoad.push(renderSidebar());
  await Promise.all(toLoad);
}

/* ---------- EVENTS ---------- */

document.addEventListener('click', (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) return;

  // Add event button -> redirect to create page (adjust if you have a different route)
  if (event.target.matches('#add-event-button')) {
    window.location.href = '/events/create/';
    return;
  }

  // sorting (click on any table header span)
  const headerEl = event.target.closest('th');
  if (headerEl && event.target.matches('span')) {
    // determine which column clicked by id
    const id = headerEl.id || '';
    if (id.includes('start_at')) {
      toggleOrder('start_at');
    } else if (id.includes('end_at')) {
      toggleOrder('end_at');
    } else if (id.includes('created-at')) {
      toggleOrder('created_at');
    } else {
      // name sorting not implemented (could be added)
      return;
    }

    // update arrows across all header instances
    document.querySelectorAll('.order-by-arrow').forEach(el => el.remove());
    if (orderBy.key) {
      // find the header element that matches current key (first one)
      const selector = orderBy.key === 'created_at' ? '[id*="created-at"]' : `[id*="${orderBy.key}"]`;
      const headerToMark = document.querySelector(selector);
      if (headerToMark) {
        const arrow = document.createElement('span');
        arrow.classList.add('order-by-arrow');
        arrow.innerHTML = orderBy.ascending ? '&#8595;' : '&#8593;';
        headerToMark.querySelector('div').append(arrow);
      }
    }

    loadPage({ table: true });
    return;
  }

  // edit icon clicked
  const editButton = event.target.closest('.edit.icon-btn');
  if (editButton) {
    const row = editButton.closest('tr[data-event]');
    if (!row) return;
    const eventData = safeParse(row.getAttribute('data-event'));
    if (!eventData) return;
    window.location.href = `/events/${encodeURIComponent(eventData.id)}/manager/`;
    return;
  }

  // row selection: clicking row selects it
  const row = event.target.closest('tr[data-event]');
  if (row) {
    const parentBody = row.parentElement;
    const prevSelected = parentBody.querySelector('tr[selected]');
    if (prevSelected) prevSelected.removeAttribute('selected');
    row.setAttribute('selected', '');
    parentBody.dataset.selected = row.id;
    return;
  }

  // clicking outside of important elements clears selection
  if (!event.target.matches('#search-bar')) {
    clearAllSelections();
  }
});

document.addEventListener('dblclick', (event) => {
  const row = event.target.closest('tr[data-event]');
  if (!row) return;
  const eventData = safeParse(row.getAttribute('data-event'));
  if (!eventData) return;
  window.location.href = `/events/${encodeURIComponent(eventData.id)}/manager/`;
});

searchBar.addEventListener('input', () => {
  loadPage({ table: true });
});

/* ---------- RENDERING ---------- */

function clearAllSelections() {
  document.querySelectorAll('tbody').forEach((tb) => {
    const sel = tb.querySelector('tr[selected]');
    if (sel) sel.removeAttribute('selected');
    tb.dataset.selected = '';
  });
}

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

function safeParse(str) {
  try {
    return JSON.parse(str);
  } catch (err) {
    return null;
  }
}

function formatDateTimeISOToLocal(isoString) {
  if (!isoString) return '-';
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return '-';
  // localized short format: date + time
  return d.toLocaleString();
}

function isSearchedForEvent(ev, searchQuery) {
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  const id = String(ev.id || '').toLowerCase();
  const name = String(ev.name || '').toLowerCase();
  const startAt = formatDateTimeISOToLocal(ev.start_at || '').toLowerCase();
  const endAt = formatDateTimeISOToLocal(ev.end_at || '').toLowerCase();
  const created = formatDateTimeISOToLocal(ev.created_at || '').toLowerCase();

  const searchable = `${id} ${name} ${startAt} ${endAt} ${created}`;

  for (const q of queries) {
    if (!q.includes('=')) {
      if (!searchable.includes(q)) return false;
    } else {
      // key=value style: support id=..., name=..., start_at=..., end_at=...
      const [k, v] = q.split('=');
      if (!v) return false;
      const val = v.toLowerCase();
      if (['id', 'identifier'].includes(k)) {
        if (!id.includes(val)) return false;
      } else if (['name', 'akce', 'nazev', 'název'].includes(k)) {
        if (!name.includes(val)) return false;
      } else if (['start_at'].includes(k)) {
        if (!startAt.includes(val)) return false;
      } else if (['end_at'].includes(k)) {
        if (!endAt.includes(val)) return false;
      } else {
        if (!searchable.includes(q)) return false;
      }
    }
  }
  return true;
}

async function renderTableRows() {
  const events = await getEvents();

  if (events === 'unexpected_error') {
    const errHTML = `<tr><td class="error-message" colspan="6">Nepovedlo se načíst akce.</td></tr>`;
    activeBody.innerHTML = errHTML;
    futureBody.innerHTML = errHTML;
    pastBody.innerHTML = errHTML;
    return;
  }

  const searchQuery = searchBar.value;
  // categorize events
  const now = new Date();

  const active = [];
  const future = [];
  const past = [];

  for (const ev of events) {
    // Expect ev.start_at and ev.end_at to be ISO strings
    const startAt = ev.start_at ? new Date(ev.start_at) : null;
    const endAt = ev.end_at ? new Date(ev.end_at) : null;

    if (startAt && endAt && startAt <= now && now <= endAt) active.push(ev);
    else if (startAt && startAt > now) future.push(ev);
    else past.push(ev);
  }

  // sorting helper: if orderBy.key present, apply to each category
  function sorter(a, b) {
    if (!orderBy.key) return 0;
    const key = orderBy.key;
    let aa = a[key] || '';
    let bb = b[key] || '';

    // if date-like keys, compare by Date
    if (key === 'start_at' || key === 'end_at' || key === 'created_at') {
      aa = aa ? new Date(aa).getTime() : 0;
      bb = bb ? new Date(bb).getTime() : 0;
      return (aa - bb) * (orderBy.ascending ? 1 : -1);
    }

    aa = String(aa).toLowerCase();
    bb = String(bb).toLowerCase();
    return aa.localeCompare(bb) * (orderBy.ascending ? 1 : -1);
  }

  if (orderBy.key) {
    active.sort(sorter);
    future.sort(sorter);
    past.sort(sorter);
  }

  // render function
  function rowsFromList(list, tbody) {
    let rows = '';
    let idx = 1;

    for (let i = 1; i < 10; i++) {

    for (const ev of list) {
      if (!isSearchedForEvent(ev, searchQuery)) continue;

      const createdAtStr = formatDateTimeISOToLocal(ev.created_at);
      const startAtStr = formatDateTimeISOToLocal(ev.start_at);
      const endAtStr = formatDateTimeISOToLocal(ev.end_at);
      const safeEv = escapeHTML(JSON.stringify(ev));

      rows += `
        <tr id="${escapeHTML(String(ev.id))}" data-event='${safeEv}'>
          <td>${idx}</td>
          <td class="event-name">${escapeHTML(ev.name || '-')} <span class="id-muted muted">(${escapeHTML(ev.id)})</span></td>
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

    }
    tbody.innerHTML = rows || `<tr><td class="muted" colspan="6">Žádné položky.</td></tr>`;
  }

  rowsFromList(active, activeBody);
  rowsFromList(future, futureBody);
  rowsFromList(past, pastBody);

  // counts (note: counts reflect unfiltered totals; if you prefer filtered counts, change to length of rows created)
  activeCountEl.textContent = active.length;
  futureCountEl.textContent = future.length;
  pastCountEl.textContent = past.length;

  // restore selection if present
  [activeBody, futureBody, pastBody].forEach(tb => {
    const selectedId = tb.dataset.selected;
    if (!selectedId) return;
    const sel = tb.querySelector(`[id="${selectedId}"]`);
    if (sel) sel.setAttribute('selected', '');
  });
}

function escapeHTML(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
