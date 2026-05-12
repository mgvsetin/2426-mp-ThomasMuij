import {
  formatDateTimeISOToDisplay,
  isValidDate,
  formatForDatetimeLocalInput,
} from '../../cashier_app/static/scripts/general/date_utils.js';

// ---------------------------------------------------------------------------
// formatDateTimeISOToDisplay
// ---------------------------------------------------------------------------

describe('formatDateTimeISOToDisplay', () => {
  test('returns dash for null', () => {
    expect(formatDateTimeISOToDisplay(null)).toBe('-');
  });

  test('returns dash for undefined', () => {
    expect(formatDateTimeISOToDisplay(undefined)).toBe('-');
  });

  test('returns dash for empty string', () => {
    expect(formatDateTimeISOToDisplay('')).toBe('-');
  });

  test('returns formatted string for valid ISO', () => {
    const result = formatDateTimeISOToDisplay('2025-06-15T14:30:00Z');
    // Result depends on locale; just verify it's a non-empty string (not '-')
    expect(result).not.toBe('-');
    expect(typeof result).toBe('string');
    expect(result.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// isValidDate
// ---------------------------------------------------------------------------

describe('isValidDate', () => {
  test('valid Date object', () => {
    expect(isValidDate(new Date('2025-01-15'))).toBe(true);
  });

  test('invalid Date (NaN)', () => {
    expect(isValidDate(new Date('invalid'))).toBe(false);
  });

  test('non-Date object', () => {
    expect(isValidDate('2025-01-15')).toBe(false);
  });

  test('null is not a valid date', () => {
    expect(isValidDate(null)).toBe(false);
  });

  test('number is not a valid date', () => {
    expect(isValidDate(12345)).toBe(false);
  });

  test('Date.now() timestamp is not a Date', () => {
    expect(isValidDate(Date.now())).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// formatForDatetimeLocalInput
// ---------------------------------------------------------------------------

describe('formatForDatetimeLocalInput', () => {
  test('formats Date object', () => {
    const d = new Date(2025, 5, 15, 14, 30); // June 15, 2025 14:30 (local)
    const result = formatForDatetimeLocalInput(d);
    expect(result).toBe('2025-06-15T14:30');
  });

  test('pads single digits', () => {
    const d = new Date(2025, 0, 5, 9, 5); // Jan 5, 2025 09:05
    const result = formatForDatetimeLocalInput(d);
    expect(result).toBe('2025-01-05T09:05');
  });

  test('handles ISO string input', () => {
    const result = formatForDatetimeLocalInput('2025-06-15T14:30:00');
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
  });

  test('midnight', () => {
    const d = new Date(2025, 0, 1, 0, 0);
    const result = formatForDatetimeLocalInput(d);
    expect(result).toBe('2025-01-01T00:00');
  });

  test('end of day', () => {
    const d = new Date(2025, 11, 31, 23, 59);
    const result = formatForDatetimeLocalInput(d);
    expect(result).toBe('2025-12-31T23:59');
  });
});
