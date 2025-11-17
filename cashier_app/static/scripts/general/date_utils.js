export function formatDateTimeISOToDisplay(isoString) {
  if (!isoString) return '-'
  const d = new Date(isoString);
  return d.toLocaleString('cs-CZ');

  // udělá podle preferencí uživatele:
  // return d.toLocaleString();

  // return `${addZero(d.getDate())}/${addZero(d.getMonth() + 1)}/${d.getFullYear()}, ${addZero(d.getHours())}:${addZero(d.getMinutes())}:${addZero(d.getSeconds())}`
}


export function isValidDate(d) {
  return d instanceof Date && !Number.isNaN(d.getTime());
}