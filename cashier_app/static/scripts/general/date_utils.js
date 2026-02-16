/**
 * @file Pomocné funkce pro práci s datem a časem.
 */

/**
 * Převede ISO řetězec data a času na zobrazitelný formát podle české lokalizace.
 * @param {string} isoString - Datum a čas ve formátu ISO.
 * @returns {string} Datum a čas ve formátu vhodném pro zobrazení.
 */
export function formatDateTimeISOToDisplay(isoString) {
  if (!isoString) return '-'
  const d = new Date(isoString);
  return d.toLocaleString('cs-CZ');

  // udělá podle preferencí uživatele:
  // return d.toLocaleString();

  // return `${addZero(d.getDate())}/${addZero(d.getMonth() + 1)}/${d.getFullYear()}, ${addZero(d.getHours())}:${addZero(d.getMinutes())}:${addZero(d.getSeconds())}`
}


/**
 * Ověří, zda je zadaná hodnota platný objekt Date.
 * @param {any} d - Hodnota k ověření.
 * @returns {boolean} True pokud je platné datum, jinak false.
 */
export function isValidDate(d) {
  return d instanceof Date && !Number.isNaN(d.getTime());
}


/**
 * Převede datum na formát vhodný pro HTML input typu datetime-local.
 * @param {Date|string|number} date - Datum jako objekt Date nebo převoditelný řetězec/číslo.
 * @returns {string} Datum ve formátu "YYYY-MM-DDThh:mm".
 */
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
