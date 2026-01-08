import { ForbiddenError, UnauthorizedRedirectError, UnexpectedError } from "./errors.js";
import { isPlainObject, isTypingInEditable, isUUID, mod } from "./utils.js";

const selectedRowIds = new Set(); // pro markSelectedRows
let lastSelectedRowId;
let currentlyPasting = false;
let copyPasteMesContainer;

export function handleRowSelection(event) {
  if (event.type === 'keydown' && event.key === 'Escape') {
    unselectRows();
    return;
  }

  if (event.type === 'keydown' && !(['ArrowUp', 'ArrowDown'].includes(event.key))) {
    return;
  }

  let targetRow;
  if (event.type === 'click') {
    targetRow = event.target.closest('tr[id]');
    if (!targetRow) return;
  }

  const rows = document.querySelectorAll('tr[id]');
  if (!rows.length) return;

  let lastSelectedRowIdx;

  if (lastSelectedRowId) {
    for (let i = 0; i < rows.length; i++) {
      const selectedRow = rows[i];
      if (selectedRow.id === lastSelectedRowId) {
        lastSelectedRowIdx = i;
        break;
      }
    }
  }

  if (event.type === 'keydown') {
    event.preventDefault();

    let indexDirection;
    let idxBeforeNext = lastSelectedRowIdx;

    if (event.key === 'ArrowDown') {
      indexDirection = 1;
      if (idxBeforeNext !== 0 && !idxBeforeNext) idxBeforeNext = -1;
    }
    if (event.key === 'ArrowUp') {
      indexDirection = -1;
      if (idxBeforeNext !== 0 && !idxBeforeNext) idxBeforeNext = rows.length;
    }

    targetRow = rows[mod(idxBeforeNext + indexDirection, rows.length)];
  }

  if (!event.ctrlKey) {
    unselectRows();
  }

  if (event.shiftKey && (lastSelectedRowIdx || lastSelectedRowIdx === 0)) {
    let targetRowIdx;
    for (let i = 0; i < rows.length; i++) {
      const selectedRow = rows[i];
      if (selectedRow === targetRow) {
        targetRowIdx = i;
        break;
      }
    }

    let start = lastSelectedRowIdx;
    let end = targetRowIdx;
    if (start > end) {
      [start, end] = [end, start];
    }
    end += 1
    for (const row of (new Array(...rows)).slice(start, end)) {
      row.setAttribute('selected', '');
      selectedRowIds.add(row.id);
    }
  } else {
    if (event.type === 'click' && event.ctrlKey && targetRow.hasAttribute('selected')) {
      targetRow.removeAttribute('selected');
      selectedRowIds.delete(targetRow.id);
    } else {
      targetRow.setAttribute('selected', '');
      selectedRowIds.add(targetRow.id);
    }
  }
  lastSelectedRowId = targetRow.id;
  if (event.type === 'keydown') targetRow.scrollIntoView({ behavior: 'instant', block: 'center' });
}


export function unselectRows() {
  const selectedRows = document.querySelectorAll('tr[selected]');
  selectedRows.forEach(row => {
    row.removeAttribute('selected');
  });
  selectedRowIds.clear();
  lastSelectedRowId = null;
}


export function markSelectedRows() {
  selectedRowIds.forEach(rowId => {
    const selected = document.querySelector(`[id="${rowId}"]`);
    if (selected) selected.setAttribute('selected', '');
  })
}


export function directTo(clickedDirectEl, parent) {
  const directToId = clickedDirectEl.dataset.directTo;
  const directToRow = parent.querySelector(`[id="${directToId}"]`);
  if (!directToRow) return;
  unselectRows();
  directToRow.setAttribute('selected', '');
  selectedRowIds.add(directToRow.id);
  lastSelectedRowId = directToRow.id;
  directToRow.scrollIntoView({ behavior: "smooth", block: "center" });
}


function makeCopyPasteMessage(message) {
  if (!copyPasteMesContainer) {
    copyPasteMesContainer = document.createElement('div');
    copyPasteMesContainer.classList.add('copy-paste-message-container');
    document.body.appendChild(copyPasteMesContainer);
  }
  const copyPasteMessage = document.createElement('div');
  copyPasteMessage.classList.add('copy-paste-message');
  copyPasteMessage.innerText = message;
  copyPasteMesContainer.appendChild(copyPasteMessage);
  setTimeout(() => {
    copyPasteMessage.classList.add('fade');
    setTimeout(() => {
      copyPasteMessage.remove();
    }, 800);
  }, 2500);
}


async function copySelected() {
  const selectedRows = document.querySelectorAll('tr[selected]');
  const selected = {
    eventIds: [],
    boothIds: [],
    productIds: [],
    categoryIds: [],
    managerIds: [],
    employeesToAssignToTargetBooths: [],
    employeeIds: []
  };
  for (const row of selectedRows) {
    const table = row.closest('table');
    if (!table) continue;
    const tableContents = table.getAttribute('table-contents');

    if (tableContents === 'events') {
      selected.eventIds.push(row.id);
    } else if (tableContents === 'booths') {
      selected.boothIds.push(row.id);
    } else if (tableContents === 'products') {
      selected.productIds.push(row.id);
    } else if (tableContents === 'categories') {
      selected.categoryIds.push(row.id);
    } else if (tableContents === 'managers') {
      selected.managerIds.push(row.id);
    } else if (tableContents === 'employees') {
      selected.employeesToAssignToTargetBooths.push(row.id);
    } else if (tableContents === 'all-employees') {
      selected.employeeIds.push(row.id);
    } else {
      continue;
    }
  }

  localStorage.setItem('copied', JSON.stringify(selected));
}


async function pasteCopied(calledWithin) {
  const data = {};
  try {
    data.dataToCopy = JSON.parse(localStorage.getItem('copied')) ||
    {
      eventIds: [],
      boothIds: [],
      productIds: [],
      categoryIds: [],
      managerIds: [],
      employeesToAssignToTargetBooths: [],
      employeeIds: []
    };
  } catch {
    makeCopyPasteMessage('Něco se nepovedlo. Zkuste data znovu zkopírovat.');
    localStorage.removeItem('copied');
    return;
  }

  if (!isPlainObject(data.dataToCopy)
    || !Array.isArray(data.dataToCopy.eventIds)
    || !Array.isArray(data.dataToCopy.boothIds)
    || !Array.isArray(data.dataToCopy.productIds)
    || !Array.isArray(data.dataToCopy.categoryIds)
    || !Array.isArray(data.dataToCopy.managerIds)
    || !Array.isArray(data.dataToCopy.employeesToAssignToTargetBooths)
    || !Array.isArray(data.dataToCopy.employeeIds)) {
    makeCopyPasteMessage('Něco se nepovedlo. Zkuste data znovu zkopírovat.');
    localStorage.removeItem('copied');
    return;
  }

  if (data.dataToCopy.eventIds.length === 0
    && data.dataToCopy.boothIds.length === 0
    && data.dataToCopy.productIds.length === 0
    && data.dataToCopy.categoryIds.length === 0
    && data.dataToCopy.managerIds.length === 0
    && data.dataToCopy.employeesToAssignToTargetBooths.length === 0
    && data.dataToCopy.employeeIds.length === 0) {
    makeCopyPasteMessage('Nemáte nic zkopírováno.');
    return;
  }

  const selectedRows = document.querySelectorAll('tr[selected]');
  const targets = {
    eventIds: [],
    boothIds: []
  };
  for (const row of selectedRows) {
    const table = row.closest('table');
    if (!table) continue;
    const tableContents = table.getAttribute('table-contents');

    if (tableContents === 'events') {
      targets.eventIds.push(row.id);
    } else if (tableContents === 'booths') {
      targets.boothIds.push(row.id);
    } else {
      continue;
    }
  }

  if (targets.eventIds.length !== 0
    || targets.boothIds.length !== 0) {
    data.targets = targets;
  } else if (calledWithin === 'employees_manager') {
    data.targets = 'newEmployees';
  } else if (calledWithin === 'events_manager') {
    data.targets = 'newEvents';
  } else if (isUUID(calledWithin)) {
    data.targets = {
      eventIds: [calledWithin],
      boothIds: []
    };
  } else {
    makeCopyPasteMessage('Sem nelze vkládat zkopírované data.');
    return;
  }

  try {
    const response = await fetch('/api/paste', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json; charset=utf-8'
      },
      body: JSON.stringify(data)
    });

    if (response.status === 401) {
      const json = await response.json();
      window.location.href = json.redirect_url;
      throw new UnauthorizedRedirectError(json.redirect_url);
    }

    const resData = await response.json();

    console.log(resData);

    if (response.status === 403 && resData.error === 'insufficient_priviliges') {
      throw new ForbiddenError();
    }

    if (!response.ok) {
      throw new UnexpectedError();
    }
  } catch (error) {
    console.log(error);
  }
}


async function undoPaste() {
  const isConfirmed = await new Promise((resolve) => {
    if (document.querySelector('.unpaste-confirmation-modal')) resolve(false);

    const unpasteConfirmationContainer = document.createElement('div');
    unpasteConfirmationContainer.classList.add('unpaste-confirmation-container');
    unpasteConfirmationContainer.innerHTML = `
      <div class="unpaste-confirmation-modal">
        <header>
          <h2>Chcete opravdu vrátit poslední vložení?</h2>
          <button class="close-unpaste-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <div>Změny provedené po vložení nejdou automaticky obnovit.</div>
        <div class="upaste-confirmation-actions">
          <button class="cancel-unpaste">Ne</button>
          <button class="confirm-unpaste">Ano</button>
        </div>
      </div>
    `;
    document.body.appendChild(unpasteConfirmationContainer);

    unpasteConfirmationContainer.addEventListener('click', (event) => {
      if (event.target.matches('.cancel-unpaste')) {
        unpasteConfirmationContainer?.remove();
        resolve(false);
        return;
      }

      if (event.target.matches('.confirm-unpaste')) {
        unpasteConfirmationContainer?.remove();
        resolve(true);
        return;
      }

      const closeBut = event.target.closest('.close-unpaste-modal');
      if (closeBut) {
        unpasteConfirmationContainer?.remove();
        closeBut.closest('.unpaste-confirmation-container')?.remove();
        resolve(false);
        return;
      }
    });

    unpasteConfirmationContainer.addEventListener('keydown', (event) => {
      const ctrlPressed = event.ctrlKey || event.metaKey;
      if (!ctrlPressed) {
        return;
      }

      const key = (event.key || '').toLowerCase();

      if (isTypingInEditable()) {
        return;
      }

      if (key === 'z') {
        unpasteConfirmationContainer?.remove();
        resolve(true);
        return;
      }
    });
  });

  if (!isConfirmed) return;


  try {
    const response = await fetch('/api/paste/undo', { method: 'POST' });

    if (response.status === 401) {
      const json = await response.json();
      window.location.href = json.redirect_url;
      throw new UnauthorizedRedirectError(json.redirect_url);
    }

    const resData = await response.json();

    if (!response.ok) {
      throw new UnexpectedError();
    }
  } catch (error) {
    console.log(error);
  }
}


async function redoPaste() {
  try {
    const response = await fetch('/api/paste/redo', { method: 'POST' });

    if (response.status === 401) {
      const json = await response.json();
      window.location.href = json.redirect_url;
      throw new UnauthorizedRedirectError(json.redirect_url);
    }

    const resData = await response.json();

    console.log(resData);

    if (response.status === 403 && resData.error === 'insufficient_priviliges') {
      throw new ForbiddenError();
    }

    if (!response.ok) {
      throw new UnexpectedError();
    }

  } catch (error) {
    console.log(error);
  }
}


async function handleCopyPasteOnKeydownFunc(event, calledWithin) {
  const ctrlPressed = event.ctrlKey || event.metaKey;
  if (!ctrlPressed) {
    return;
  }

  const key = (event.key || '').toLowerCase();
  if (!['c', 'v', 'z', 'y'].includes(key)) {
    return;
  };

  if (isTypingInEditable()) {
    return;
  }

  if (key === 'c') {
    copySelected();
    return 'copy';
  } else if (key === 'v') {
    if (calledWithin === 'employees_manager') {
      await pasteCopied('employees_manager');
      return 'paste-employees';
    } else if (calledWithin === 'events_manager') {
      await pasteCopied('events_manager');
      return 'paste';
    } else if (isUUID(calledWithin)) {
      await pasteCopied(calledWithin);
      return 'paste';
    } else {
      return;
    }
  } else if (key === 'z') {
    await undoPaste();
    return 'undo-paste';
  } else if (key === 'y') {
    await redoPaste();
    return 'redo-paste';
  }
}

export async function handleCopyPasteOnKeydown(event, calledWithin) {
  if (currentlyPasting) return 'currentlyPasting';
  currentlyPasting = true;
  const result = await handleCopyPasteOnKeydownFunc(event, calledWithin);
  currentlyPasting = false;
  return result;
}