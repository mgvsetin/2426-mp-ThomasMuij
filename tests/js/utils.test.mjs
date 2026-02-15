import { mod, isUUID, isPlainObject, isTypingInEditable } from '../../cashier_app/static/scripts/general/utils.js';

// ---------------------------------------------------------------------------
// mod
// ---------------------------------------------------------------------------

describe('mod', () => {
  test('positive modulo', () => {
    expect(mod(5, 3)).toBe(2);
  });

  test('zero modulo', () => {
    expect(mod(0, 5)).toBe(0);
  });

  test('negative number gives positive result', () => {
    // In JS: -1 % 3 === -1, but mod(-1, 3) should be 2
    expect(mod(-1, 3)).toBe(2);
  });

  test('negative number wrap around', () => {
    expect(mod(-5, 3)).toBe(1);
  });

  test('large negative', () => {
    expect(mod(-10, 4)).toBe(2);
  });

  test('same value as modulus', () => {
    expect(mod(3, 3)).toBe(0);
  });

  test('modulo by zero throws', () => {
    expect(() => mod(5, 0)).toThrow(RangeError);
  });

  test('modulo with 1', () => {
    expect(mod(7, 1)).toBe(0);
    expect(mod(-7, 1)).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// isUUID
// ---------------------------------------------------------------------------

describe('isUUID', () => {
  test('valid UUID lowercase', () => {
    expect(isUUID('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
  });

  test('valid UUID uppercase', () => {
    expect(isUUID('550E8400-E29B-41D4-A716-446655440000')).toBe(true);
  });

  test('valid UUID mixed case', () => {
    expect(isUUID('550e8400-E29B-41d4-a716-446655440000')).toBe(true);
  });

  test('empty string', () => {
    expect(isUUID('')).toBe(false);
  });

  test('random string', () => {
    expect(isUUID('not-a-uuid')).toBe(false);
  });

  test('UUID without dashes', () => {
    expect(isUUID('550e8400e29b41d4a716446655440000')).toBe(false);
  });

  test('too short', () => {
    expect(isUUID('550e8400-e29b-41d4-a716')).toBe(false);
  });

  test('too long', () => {
    expect(isUUID('550e8400-e29b-41d4-a716-446655440000-extra')).toBe(false);
  });

  test('invalid characters', () => {
    expect(isUUID('550e8400-e29b-41d4-a716-44665544000g')).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isPlainObject
// ---------------------------------------------------------------------------

describe('isPlainObject', () => {
  test('plain object literal', () => {
    expect(isPlainObject({})).toBe(true);
  });

  test('object with properties', () => {
    expect(isPlainObject({ a: 1, b: 2 })).toBe(true);
  });

  test('null returns false', () => {
    expect(isPlainObject(null)).toBe(false);
  });

  test('undefined returns false', () => {
    expect(isPlainObject(undefined)).toBe(false);
  });

  test('array returns false', () => {
    expect(isPlainObject([1, 2, 3])).toBe(false);
  });

  test('string returns false', () => {
    expect(isPlainObject('hello')).toBe(false);
  });

  test('number returns false', () => {
    expect(isPlainObject(42)).toBe(false);
  });

  test('Date returns false', () => {
    expect(isPlainObject(new Date())).toBe(false);
  });

  test('Object.create(null) returns true', () => {
    expect(isPlainObject(Object.create(null))).toBe(true);
  });

  test('class instance returns false', () => {
    class Foo {}
    expect(isPlainObject(new Foo())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// isTypingInEditable
// ---------------------------------------------------------------------------

describe('isTypingInEditable', () => {
  test('returns false when no active element', () => {
    // jsdom default: document.activeElement is document.body
    expect(isTypingInEditable()).toBe(false);
  });

  test('returns true for textarea', () => {
    const textarea = document.createElement('textarea');
    document.body.appendChild(textarea);
    textarea.focus();
    expect(isTypingInEditable()).toBe(true);
    document.body.removeChild(textarea);
  });

  test('returns true for text input', () => {
    const input = document.createElement('input');
    input.type = 'text';
    document.body.appendChild(input);
    input.focus();
    expect(isTypingInEditable()).toBe(true);
    document.body.removeChild(input);
  });

  test('returns true for password input', () => {
    const input = document.createElement('input');
    input.type = 'password';
    document.body.appendChild(input);
    input.focus();
    expect(isTypingInEditable()).toBe(true);
    document.body.removeChild(input);
  });

  test('returns true for email input', () => {
    const input = document.createElement('input');
    input.type = 'email';
    document.body.appendChild(input);
    input.focus();
    expect(isTypingInEditable()).toBe(true);
    document.body.removeChild(input);
  });

  test('returns false for checkbox input', () => {
    const input = document.createElement('input');
    input.type = 'checkbox';
    document.body.appendChild(input);
    input.focus();
    expect(isTypingInEditable()).toBe(false);
    document.body.removeChild(input);
  });

  test('returns false for button', () => {
    const btn = document.createElement('button');
    document.body.appendChild(btn);
    btn.focus();
    expect(isTypingInEditable()).toBe(false);
    document.body.removeChild(btn);
  });

  // Skipped: jsdom does not fully support contentEditable focus behaviour,
  // so isContentEditable returns false even after div.focus().
  test.skip('returns true for contentEditable (jsdom limitation)', () => {
    const div = document.createElement('div');
    div.contentEditable = 'true';
    document.body.appendChild(div);
    div.focus();
    expect(isTypingInEditable()).toBe(true);
    document.body.removeChild(div);
  });
});
