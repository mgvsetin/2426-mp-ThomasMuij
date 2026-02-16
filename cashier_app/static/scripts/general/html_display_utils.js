/**
 * @file Pomocné funkce pro zobrazení a zpracování HTML.
 */

/**
 * Escapuje speciální znaky v textu pro bezpečné zobrazení v HTML.
 * @param {string} str - Vstupní text.
 * @returns {string} Upravený text vhodný pro HTML.
 */
export function escapeHTML(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}


/**
 * Bezpečně zparsuje JSON řetězec, při chybě vrací null.
 * @param {string} str - Vstupní JSON řetězec.
 * @returns {any|null} Výsledek parsování nebo null při chybě.
 */
export function safeParse(str) {
  try {
    return JSON.parse(str);
  } catch (err) {
    return null;
  }
}