import { handleUnauthorizedRedirect } from '../general/api_utils.js';
import { cacheFunctionFactory } from '../general/cache_factory.js';
import { formatDateTimeISOToDisplay } from '../general/date_utils.js';
import { headerClickListeners, renderHeader } from '../general/header.js';
import { escapeHTML } from '../general/html_display_utils.js';
import { clearModalErrors, closeModal, openModal } from '../general/modals_forms.js';
import { renderSidebar, sidebarClickListeners } from '../general/sidebar.js';
import { handleRowSelection, markSelectedRows, unselectRows } from '../general/table_utils.js';


const tableBody = document.querySelector('#deleted-events-table-body');
const tableHeader = document.querySelector('table thead');
const eventsSearchBar = document.querySelector('.search-bar');

const orderBy = { key: '', ascending: true };

const [fetchDeletedEvents, resetDeletedEventsCache] = cacheFunctionFactory(async () => {
  const response = await fetch('/api/events/deleted');

  await handleUnauthorizedRedirect(response);

  const resData = await response.json();

  if (!response.ok) {
    throw new Error(resData.error || 'unknown_error');
  }

  return resData.events;
})

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
    if (headerEl.id === 'name-header') {
      toggleOrder('name');
    } else if (headerEl.id === 'start-at-header') {
      toggleOrder('start_at');
    } else if (headerEl.id === 'end-at-header') {
      toggleOrder('end_at');
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

    loadPage({table: true});
    return;
  }

  const forceBtn = event.target.closest('#force-event-restore')
  if (forceBtn) {
    forceBtn.disabled = true;
    const form = document.querySelector('#restore-event-form');
    if (!form) return;
    const formData = new FormData(form);
    formData.append('force', 'true');
    const response = await restoreEvent(formData);
    if (response === true) {
      closeModal();
      resetDeletedEventsCache();
      loadPage({table: true});
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
  const restoreForm = event.target.closest('#restore-event-form');
  if (restoreForm) {
    event.preventDefault();
    const submitButton = restoreForm.querySelector('button[type=submit]');
    submitButton.disabled = true;

    clearModalErrors();

    const formData = new FormData(restoreForm);

    const response = await restoreEvent(formData);

    submitButton.disabled = false;

    if (response === true) {
      closeModal();
      resetDeletedEventsCache();
      loadPage({table: true});
      return;
    }

    showRestoreErrors(response.error);
    return;
  }
});


eventsSearchBar.addEventListener('input', () => {
  loadPage({table: true});
});


document.addEventListener('keydown', (event) => {
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


function eventIsSearchedFor(event) {
  const searchQuery = eventsSearchBar.value.toLowerCase().trim();
  if (!searchQuery) return true;
  const queries = searchQuery.toLowerCase().trim().split(/\s+/);
  // const id = String(ev.id || '').toLowerCase();
  const name = String(event.name || '').toLowerCase();
  const startAt = formatDateTimeISOToDisplay(event.start_at || '').toLowerCase();
  const endAt = formatDateTimeISOToDisplay(event.end_at || '').toLowerCase();
  const deleted_at = formatDateTimeISOToDisplay(event.deleted_at || '').toLowerCase();

  const searchable = `${name} ${startAt} ${endAt} ${deleted_at}`;

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
      } else if (['deleted_at', 'smazána', 'smazana'].includes(k)) {
        if (!deleted_at.includes(v)) return false;
      } else {
        if (!searchable.includes(q)) return false;
      }
    }
  }
  return true;
}


async function renderTable() {
  const events = await fetchDeletedEvents().catch(() => {
    tableBody.innerHTML = '<tr><td colspan="6" class="error-message">Nepovedlo se načíst smazané akce.</td></tr>';
  });
  if (!events) return;

  const sorter = (a, b) => {
    if (!orderBy.key) return 0;
    const key = orderBy.key;
    let aa = a[key] || '';
    let bb = b[key] || '';

    if (key === 'deleted_at' || key === 'start_at' || key === 'end_at') {
      aa = aa ? new Date(aa).getTime() : Infinity;
      bb = bb ? new Date(bb).getTime() : 0;
      return (aa - bb) * (orderBy.ascending ? 1 : -1);
    }

    aa = String(aa).toLowerCase();
    bb = String(bb).toLowerCase();
    return aa.localeCompare(bb) * (orderBy.ascending ? 1 : -1);
  };

  const sorted = events.toSorted(sorter);
  let rows = '';
  let idx = 0;

  sorted.forEach(event => {
    if (!eventIsSearchedFor(event)) return;
    idx++;
    rows += `
      <tr id="${event.id}">
        <td>${idx}</td>
        <td>${escapeHTML(event.name)}</td>
        <td class="deleted-at muted">${escapeHTML(event.start_at ? formatDateTimeISOToDisplay(event.start_at) : '-')}</td>
        <td class="deleted-at muted">${escapeHTML(event.end_at ? formatDateTimeISOToDisplay(event.end_at) : '-')}</td>
        <td class="deleted-at muted">${escapeHTML(formatDateTimeISOToDisplay(event.deleted_at))}</td>
        <td class="actions">
          <button class="icon-btn restore" title="Obnovit akci">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M3 3v5h5" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  tableBody.innerHTML = rows || '<tr><td colspan="6" class="empty-message">Žádné smazané akce.</td></tr>';

  markSelectedRows(tableBody);
}


async function openRestoreModal(eventId) {
  const events = await fetchDeletedEvents().catch(() => { });
  if (!events) return;
  const event = events.find(event => event.id === eventId);
  if (!event) return;

  const html = `
    <header>
      <h2>Obnovit akci</h2>
    </header>
    <form id="restore-event-form">
      <input type="hidden" name="event-id" value="${event.id}" />
      <div class="form-row">
        <div>Opravdu chcete obnovit akci "${escapeHTML(event.name)}"?</div>
      </div>
      <div class="form-row">
        <div class="muted">Propojovací tabulky, role zaměstnanců a obrázky produktů nebudou obnoveny.</div>
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
    case 'invalid_event_id':
      setErr(generalError, 'ID akce není správné.');
      return;
    case 'event_not_found':
      setErr(generalError, 'Akce nebyla nalezena.');
      return;
    case 'event_name_taken': {
      if (!generalError) return;

      generalError.innerHTML = `
        <div>Nelze obnovit: akce se stejným názvem už existuje.</div>
        <button id="force-event-restore" type="button" class="btn btn-primary">Vynutit obnovení</button>
        <div class="muted">Změní název akce tak, aby byl unikátní</div>
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

  setErr(generalError, errorStr);
}


async function restoreEvent(formData) {
  try {
    const response = await fetch('/api/events/restore', {
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
