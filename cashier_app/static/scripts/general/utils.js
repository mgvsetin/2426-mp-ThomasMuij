export function mod(a, n) {
  if (n === 0) throw new RangeError("modulo by zero");

  // js % funguje jinak pro záporná čísla -> tento vzorec to spraví
  return ((a % n) + n) % n;
}


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


export function isUUID(str) {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(str);
}


export function isPlainObject(value) {
  if (value === null || typeof value !== 'object') return false;
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}