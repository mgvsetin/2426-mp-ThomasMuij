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


export function formatForDatetimeLocalInput(date) {
  if (typeof date !== Date) {
    date = new Date(date);
  }

  const format = (n) => String(n).padStart(2, '0');

  const Y = date.getFullYear();
  const M = format(date.getMonth() + 1);
  const D = format(date.getDate());
  const h = format(date.getHours());
  const m = format(date.getMinutes());

  return `${Y}-${M}-${D}T${h}:${m}`;
}
