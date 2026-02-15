import { cloneData } from '../../cashier_app/static/scripts/general/cache.js';

describe('cloneData', () => {
  test('returns null for null', () => {
    expect(cloneData(null)).toBeNull();
  });

  test('returns undefined for undefined', () => {
    expect(cloneData(undefined)).toBeUndefined();
  });

  test('returns 0 for 0', () => {
    expect(cloneData(0)).toBe(0);
  });

  test('returns empty string for empty string', () => {
    expect(cloneData('')).toBe('');
  });

  test('returns false for false', () => {
    expect(cloneData(false)).toBe(false);
  });

  test('clones an object deeply', () => {
    const original = { a: 1, b: { c: 2 } };
    const cloned = cloneData(original);
    expect(cloned).toEqual(original);
    expect(cloned).not.toBe(original);
    expect(cloned.b).not.toBe(original.b);
  });

  test('clones an array deeply', () => {
    const original = [1, [2, 3], { a: 4 }];
    const cloned = cloneData(original);
    expect(cloned).toEqual(original);
    expect(cloned).not.toBe(original);
    expect(cloned[1]).not.toBe(original[1]);
    expect(cloned[2]).not.toBe(original[2]);
  });

  test('mutation of clone does not affect original', () => {
    const original = { a: 1, b: { c: 2 } };
    const cloned = cloneData(original);
    cloned.b.c = 99;
    expect(original.b.c).toBe(2);
  });

  test('clones primitives directly', () => {
    expect(cloneData(42)).toBe(42);
    expect(cloneData('hello')).toBe('hello');
    expect(cloneData(true)).toBe(true);
  });
});
