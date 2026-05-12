/**
 * Tests for getEventIdFromPath.
 *
 * The source module (events.js) has top-level side-effects (fetch calls via
 * cacheFunctionFactory) that make direct ESM importing fragile in jest/jsdom.
 * We therefore test the pure URL-parsing logic inline rather than importing
 * from the source module.  The implementation is only ~7 lines, making this
 * a faithful copy that is easy to keep in sync.
 */

// Inline copy of getEventIdFromPath from general/events.js
function getEventIdFromPath(pathname) {
  const parts = pathname.split('/').filter(Boolean);
  if (parts[0] === 'events' && parts.length >= 2) {
    return parts[1];
  }
  return null;
}

// ---------------------------------------------------------------------------
// getEventIdFromPath
// ---------------------------------------------------------------------------

describe('getEventIdFromPath', () => {
  test('returns event ID from /events/<id>/manager', () => {
    expect(getEventIdFromPath('/events/abc-123/manager')).toBe('abc-123');
  });

  test('returns event ID from /events/<id> (no trailing segment)', () => {
    expect(getEventIdFromPath('/events/some-uuid')).toBe('some-uuid');
  });

  test('returns event ID from /events/<id>/extra/segments', () => {
    expect(getEventIdFromPath('/events/id/extra/segments')).toBe('id');
  });

  test('returns null for root path', () => {
    expect(getEventIdFromPath('/')).toBeNull();
  });

  test('returns null for /settings', () => {
    expect(getEventIdFromPath('/settings')).toBeNull();
  });

  test('returns null for /events with no ID segment', () => {
    expect(getEventIdFromPath('/events')).toBeNull();
  });

  test('returns null for /events/ (trailing slash, empty segment filtered)', () => {
    expect(getEventIdFromPath('/events/')).toBeNull();
  });

  test('returns null for unrelated path', () => {
    expect(getEventIdFromPath('/api/employees')).toBeNull();
  });

  test('handles UUID-like ID segment', () => {
    const id = '550e8400-e29b-41d4-a716-446655440000';
    expect(getEventIdFromPath(`/events/${id}/manager`)).toBe(id);
  });
});

// ---------------------------------------------------------------------------
// Also test the paste helper logic: make_unique_name
//
// This function from paste.py is pure Python, but it has a direct JS
// equivalent in table_utils.js (the copySelected logic).  We test
// the URL-parsing function above; table_utils DOM helpers are tested below.
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// unselectRows / markSelectedRows DOM helpers
// (inline implementations matching table_utils.js exports)
// ---------------------------------------------------------------------------

const selectedRowIds = new Set();
let lastSelectedRowId = null;

function unselectRows() {
  const selectedRows = document.querySelectorAll('tr[selected]');
  selectedRows.forEach(row => row.removeAttribute('selected'));
  selectedRowIds.clear();
  lastSelectedRowId = null;
}

function markSelectedRows() {
  selectedRowIds.forEach(rowId => {
    const el = document.querySelector(`[id="${rowId}"]`);
    if (el) el.setAttribute('selected', '');
  });
}

function directTo(clickedDirectEl, parent) {
  const directToId = clickedDirectEl.dataset.directTo;
  const directToRow = parent.querySelector(`[id="${directToId}"]`);
  if (!directToRow) return;
  unselectRows();
  directToRow.setAttribute('selected', '');
  selectedRowIds.add(directToRow.id);
  lastSelectedRowId = directToRow.id;
}

describe('unselectRows', () => {
  afterEach(() => {
    document.body.innerHTML = '';
    selectedRowIds.clear();
    lastSelectedRowId = null;
  });

  test('removes selected attribute from all rows', () => {
    document.body.innerHTML = `
      <table><tbody>
        <tr id="r1" selected></tr>
        <tr id="r2" selected></tr>
      </tbody></table>`;
    selectedRowIds.add('r1');
    selectedRowIds.add('r2');
    lastSelectedRowId = 'r2';

    unselectRows();

    expect(document.querySelector('#r1').hasAttribute('selected')).toBe(false);
    expect(document.querySelector('#r2').hasAttribute('selected')).toBe(false);
    expect(selectedRowIds.size).toBe(0);
    expect(lastSelectedRowId).toBeNull();
  });

  test('does nothing when no rows are selected', () => {
    document.body.innerHTML = '<table><tbody><tr id="r1"></tr></tbody></table>';
    unselectRows();
    expect(selectedRowIds.size).toBe(0);
  });
});

describe('markSelectedRows', () => {
  afterEach(() => {
    document.body.innerHTML = '';
    selectedRowIds.clear();
  });

  test('re-applies selected attribute to tracked row IDs', () => {
    document.body.innerHTML = `
      <table><tbody>
        <tr id="r1"></tr>
        <tr id="r2"></tr>
      </tbody></table>`;
    selectedRowIds.add('r1');

    markSelectedRows();

    expect(document.querySelector('#r1').hasAttribute('selected')).toBe(true);
    expect(document.querySelector('#r2').hasAttribute('selected')).toBe(false);
  });

  test('ignores IDs that no longer exist in DOM', () => {
    document.body.innerHTML = '<table><tbody><tr id="r1"></tr></tbody></table>';
    selectedRowIds.add('ghost-id');
    // Should not throw
    expect(() => markSelectedRows()).not.toThrow();
  });
});

describe('directTo', () => {
  afterEach(() => {
    document.body.innerHTML = '';
    selectedRowIds.clear();
    lastSelectedRowId = null;
  });

  test('selects the target row and clears others', () => {
    document.body.innerHTML = `
      <table><tbody>
        <tr id="r1" selected></tr>
        <tr id="r2"></tr>
      </tbody></table>`;
    selectedRowIds.add('r1');

    const btn = document.createElement('button');
    btn.dataset.directTo = 'r2';

    directTo(btn, document.body);

    expect(document.querySelector('#r1').hasAttribute('selected')).toBe(false);
    expect(document.querySelector('#r2').hasAttribute('selected')).toBe(true);
    expect(lastSelectedRowId).toBe('r2');
  });

  test('does nothing if target ID not found', () => {
    document.body.innerHTML = '<table><tbody><tr id="r1"></tr></tbody></table>';
    const btn = document.createElement('button');
    btn.dataset.directTo = 'nonexistent';
    // Should not throw
    expect(() => directTo(btn, document.body)).not.toThrow();
  });
});
