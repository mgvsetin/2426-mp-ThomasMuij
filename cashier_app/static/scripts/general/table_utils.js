export function selectRow(row, parent) {
  const prevSelected = parent.querySelector('tr[selected]');
  if (prevSelected) prevSelected.removeAttribute('selected');
  row.setAttribute('selected', '');
  // i když zde není použito, je pořád důležité pro rerender tabulky (při vyhledávání)
  parent.dataset.selected = row.id;
}


export function unselectRow(parent) {
  const selected = parent.querySelector('tr[selected]');
  if (selected) selected.removeAttribute('selected');
  parent.dataset.selected = '';
}


export function markSelectedRow(parent) {
  const selectedId = parent.dataset.selected;
  if (!selectedId) return;
  const selected = parent.querySelector(`[id="${selectedId}"]`);
  if (selected) selected.setAttribute('selected', '');
}


export function directTo(clickedDirectEl, parent) {
  const directToId = clickedDirectEl.dataset.directTo;
  const directToRow = parent.querySelector(`[id="${directToId}"]`);
  if (!directToRow) return;
  selectRow(directToRow, parent);
  directToRow.scrollIntoView({ behavior: "smooth", block: "center" });
}
