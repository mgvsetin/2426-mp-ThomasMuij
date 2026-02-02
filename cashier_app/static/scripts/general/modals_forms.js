export function openModal(html, focusFirstInput=true) {
  document.querySelector('.overlay')?.remove();
  const overlay = document.createElement('div');
  overlay.className = 'overlay';
  overlay.innerHTML = `
    <div class="modal">
      <button class="close-modal cross-close">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
      ${html}
    </div>`;
  document.body.appendChild(overlay);
  document.body.classList.add('no-scroll');

  if (focusFirstInput) {
    // timeout, aby při otevření přes enter nedošlo k submit hned po otevření
    setTimeout(() => {
      overlay.querySelector('input:not([type="hidden"], [disabled], [readonly])')?.focus();
    }, 0);
  }

  return overlay;
}

export function closeModal() {
  document.querySelector('.overlay')?.remove();
  document.body.classList.remove('no-scroll');
}


export function clearModalErrors() {
  const els = document.querySelectorAll('.form-error');
  els.forEach(e => {
    e.innerHTML = '';
    e.classList.remove('show-form-error');
  });
}
