import {
  openModal,
  closeModal,
  clearModalErrors,
} from '../../cashier_app/static/scripts/general/modals_forms.js';

describe('openModal', () => {

  afterEach(() => {
    // Clean up after each test
    document.body.innerHTML = '';
    document.body.className = '';
  });

  test('creates overlay element', () => {
    openModal('<p>Hello</p>', false);
    const overlay = document.querySelector('.overlay');
    expect(overlay).not.toBeNull();
  });

  test('contains modal content', () => {
    openModal('<p>Test Content</p>', false);
    const modal = document.querySelector('.modal');
    expect(modal).not.toBeNull();
    expect(modal.innerHTML).toContain('Test Content');
  });

  test('contains close button', () => {
    openModal('<p>Content</p>', false);
    const closeBtn = document.querySelector('.close-modal');
    expect(closeBtn).not.toBeNull();
  });

  test('adds no-scroll class to body', () => {
    openModal('<p>Content</p>', false);
    expect(document.body.classList.contains('no-scroll')).toBe(true);
  });

  test('removes previous overlay if exists', () => {
    openModal('<p>First</p>', false);
    openModal('<p>Second</p>', false);
    const overlays = document.querySelectorAll('.overlay');
    expect(overlays.length).toBe(1);
    expect(overlays[0].innerHTML).toContain('Second');
  });

  test('returns the overlay element', () => {
    const overlay = openModal('<p>Content</p>', false);
    expect(overlay).toBeInstanceOf(HTMLElement);
    expect(overlay.className).toBe('overlay');
  });
});

describe('closeModal', () => {

  afterEach(() => {
    document.body.innerHTML = '';
    document.body.className = '';
  });

  test('removes overlay from DOM', () => {
    openModal('<p>Content</p>', false);
    closeModal();
    expect(document.querySelector('.overlay')).toBeNull();
  });

  test('removes no-scroll class from body', () => {
    openModal('<p>Content</p>', false);
    closeModal();
    expect(document.body.classList.contains('no-scroll')).toBe(false);
  });

  test('does nothing if no overlay exists', () => {
    // Should not throw
    closeModal();
    expect(document.querySelector('.overlay')).toBeNull();
  });
});

describe('clearModalErrors', () => {

  afterEach(() => {
    document.body.innerHTML = '';
  });

  test('clears error elements', () => {
    document.body.innerHTML = `
      <div class="form-error show-form-error">Error 1</div>
      <div class="form-error show-form-error">Error 2</div>
    `;
    clearModalErrors();
    const errors = document.querySelectorAll('.form-error');
    errors.forEach(e => {
      expect(e.innerHTML).toBe('');
      expect(e.classList.contains('show-form-error')).toBe(false);
    });
  });

  test('does nothing if no error elements', () => {
    document.body.innerHTML = '<p>No errors</p>';
    // Should not throw
    clearModalErrors();
  });
});
