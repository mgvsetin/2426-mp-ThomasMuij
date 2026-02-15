import {
  escapeHTML,
  safeParse,
} from '../../cashier_app/static/scripts/general/html_display_utils.js';

// ---------------------------------------------------------------------------
// escapeHTML
// ---------------------------------------------------------------------------

describe('escapeHTML', () => {
  test('escapes ampersand', () => {
    expect(escapeHTML('a&b')).toBe('a&amp;b');
  });

  test('escapes less-than', () => {
    expect(escapeHTML('a<b')).toBe('a&lt;b');
  });

  test('escapes greater-than', () => {
    expect(escapeHTML('a>b')).toBe('a&gt;b');
  });

  test('escapes double quotes', () => {
    expect(escapeHTML('a"b')).toBe('a&quot;b');
  });

  test('escapes single quotes', () => {
    expect(escapeHTML("a'b")).toBe('a&#39;b');
  });

  test('escapes all at once', () => {
    expect(escapeHTML('<script>alert("xss")&</script>')).toBe(
      '&lt;script&gt;alert(&quot;xss&quot;)&amp;&lt;/script&gt;'
    );
  });

  test('returns empty string for empty input', () => {
    expect(escapeHTML('')).toBe('');
  });

  test('does not escape normal text', () => {
    expect(escapeHTML('Hello World')).toBe('Hello World');
  });

  test('handles numbers', () => {
    expect(escapeHTML(42)).toBe('42');
  });

  test('handles null', () => {
    expect(escapeHTML(null)).toBe('null');
  });
});

// ---------------------------------------------------------------------------
// safeParse
// ---------------------------------------------------------------------------

describe('safeParse', () => {
  test('parses valid JSON object', () => {
    expect(safeParse('{"a":1}')).toEqual({ a: 1 });
  });

  test('parses valid JSON array', () => {
    expect(safeParse('[1,2,3]')).toEqual([1, 2, 3]);
  });

  test('parses JSON string', () => {
    expect(safeParse('"hello"')).toBe('hello');
  });

  test('parses JSON number', () => {
    expect(safeParse('42')).toBe(42);
  });

  test('parses JSON boolean', () => {
    expect(safeParse('true')).toBe(true);
  });

  test('parses JSON null', () => {
    expect(safeParse('null')).toBeNull();
  });

  test('returns null for invalid JSON', () => {
    expect(safeParse('not json')).toBeNull();
  });

  test('returns null for empty string', () => {
    expect(safeParse('')).toBeNull();
  });

  test('returns null for undefined', () => {
    expect(safeParse(undefined)).toBeNull();
  });
});
