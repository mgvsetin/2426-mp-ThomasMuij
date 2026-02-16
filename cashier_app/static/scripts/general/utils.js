/**
 * @file Obecné pomocné funkce (modulo, detekce editovatelných polí, UUID apod.).
 */

/**
 * Opravená operace modulo (správně i pro záporná čísla).
 * @param {number} a - Dělenec.
 * @param {number} n - Dělitel.
 * @returns {number} Výsledek operace modulo.
 */
export function mod(a, n) {
  if (n === 0) throw new RangeError("modulo by zero");

  // js % funguje jinak pro záporná čísla -> tento vzorec to spraví
  return ((a % n) + n) % n;
}


/**
 * Zjistí, zda uživatel právě píše v editovatelném poli (input, textarea, contenteditable).
 * @returns {boolean} True pokud je fokus v editovatelném poli.
 */
export function isTypingInEditable() {
  const el = document.activeElement;
  if (!el) return false;

  const tag = el.tagName;
  if (tag === 'TEXTAREA') return true;

  if (tag === 'INPUT') {
    const textTypes = ['text', 'search', 'password', 'email', 'tel', 'url', 'number'];
    return textTypes.includes((el.type || '').toLowerCase());
  }

  if (el.isContentEditable) return true;

  return false;
}


/**
 * Ověří, zda je řetězec ve formátu UUID.
 * @param {string} str - Řetězec k ověření.
 * @returns {boolean} True pokud je platné UUID.
 */
export function isUUID(str) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);
}


/**
 * Ověří, zda je hodnota obyčejný objekt (plain object).
 * @param {any} value - Hodnota k ověření.
 * @returns {boolean} True pokud je obyčejný objekt.
 */
export function isPlainObject(value) {
  if (value === null || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}