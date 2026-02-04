// export async function eventAndBoothIsPicked() {
//   try {
//     const response = await fetch('/api/session/booth-is-registered');
//     const boothIsRegistered = await response.json();

import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { UnexpectedError } from "../general/errors.js";
import { removeReadCard } from "./cards.js";
import { order } from "./order.js";
import { resetProductsCache, saveSelectedCategory } from "./products.js";
import { unselectUserForUpdate } from "./users.js";
import { resetWalletsCache } from "./wallets.js";


//     if (!response.ok) {
//       throw new Error('unexpected_error');
//     }

//     return boothIsRegistered;

//   } catch (error) {
//     return undefined;
//   }
// }

const pageContainer = document.querySelector('#page-container');

export let selectingEvent = false;

function makeEventBoothOverlay(container) {
  const existing = document.querySelector('.overlay');
  if (existing) container.removeChild(existing);

  const overlay = document.createElement('div')
  overlay.className = 'overlay';

  // container.classList.add('disable-children');

  container.appendChild(overlay);

  return overlay;
}


function removeEventBoothOverlay() {
  const overlay = document.querySelector('.overlay');

  if (!overlay) {
    return;
  }

  if (overlay.parentElement) {
    // productSide.classList.remove('disable-children');
  }

  if (overlay && overlay.parentElement) overlay.parentElement.removeChild(overlay);
}


export async function renderEventPicker() {
  let data;
  try {
    const response = await fetch('/api/employees/me/events/active');

    await handleUnauthorizedRedirect(response);

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

    data = await response.json();

  } catch (error) {
    const overlay = makeEventBoothOverlay(pageContainer);
    overlay.innerHTML = `
    <div id="event-selector-form-container">
      <div id="event-error-message">
        Nepovedlo se načíst akce. Zkuste to prosím později.
      </div>
    </div>`;
    return;
  }

  const overlay = makeEventBoothOverlay(pageContainer);

  let html_event_options = ''
  if (data) {
    data.forEach((event) => {
      html_event_options += `
        <option value="${event.id}">
          ${event.name}
        </option>`
    })

    selectingEvent = true;
  }

  overlay.innerHTML = `
  <div id="event-selector-form-container">
    <form id="event-selector-form">
      <label for="event-selector" id="event-selector-label">Vyberte akci</label>
      <select id="event-selector" name="event">
        ${html_event_options}
      </select>
      <input type="submit" value="Vybrat" id="submit-event-choice" disabled>
    </form>
    <div class='event-submit-error-message'></div>
  </div>`;

  // proti nechtěnému stisknutí:
  const submit = overlay.querySelector('#submit-event-choice');
  setTimeout(() => {
    try { submit.disabled = false; } catch { } // už bylo odendáno
  }, 150);
}


export async function pickEvent(formData) {
  try {
    const response = await fetch('/api/employees/me/events/select', {
      method: 'PUT',
      body: formData
    });

    await handleUnauthorizedRedirect(response);

    const data = await response.json();

    if ((response.status === 400 && data.error === 'invalid_event_id')
      || (response.status === 404 && data.error === 'event_not_found_or_inactive')
      || (response.status === 403 && data.error === 'employee_not_linked_to_event')) {
      throw new Error('bad_event');
    }

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

  } catch (error) {
    const errorMessageEl = document.querySelector('.event-submit-error-message');
    if (error.message === 'bad_event') {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste načíst stránku a vybrat akci ještě jednou.';
    } else {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste to prosím později.';
    }
    errorMessageEl.classList.add('display-block');
    return false;
  }
  selectingEvent = false;
  removeEventBoothOverlay();
  return true;
}


export async function renderBoothPicker() {
  let data;
  try {
    const response = await fetch('/api/employees/me/events/booths/active');

    await handleUnauthorizedRedirect(response);
  
    data = await response.json();

    if (response.status === 400 && data.error === 'no_selected_event') {
      throw new Error('no_selected_event');
    }

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

  } catch (error) {
    if (error.message === 'no_selected_event') {
      renderEventPicker();
      return;
    }
    const overlay = makeEventBoothOverlay();
    overlay.innerHTML = `
      <div id="booth-selector-form-container">
        <div id="booth-error-message">
          Nepovedlo se načíst stánky. Zkuste to prosím později.
        </div>
      </div>`;
    return;
  }

  const overlay = makeEventBoothOverlay(pageContainer);

  let html_booth_options = ''
  if (data) {
    data.forEach((booth) => {
      html_booth_options += `
          <option value="${booth.id}">
            ${booth.name}
          </option>`
    })
  }

  overlay.innerHTML = `
      <div id="booth-selector-form-container">
        <form id="booth-selector-form">
          <label for="booth-selector" id="booth-selector-label">Vyberte stánek</label>
          <select id="booth-selector" name="booth">
            ${html_booth_options}
          </select>
          <input type="submit" value="Vybrat" id="submit-booth-choice" disabled>
        </form>
        <button id="return-to-event-picker-button" disabled>
          Zpět
        </button>
        <div class="booth-submit-error-message"></div>
      </div>`;

  // proti nechtěnému stisknutí:
  const submit = overlay.querySelector('#submit-booth-choice');
  const returnButton = overlay.querySelector('#return-to-event-picker-button');
  setTimeout(() => {
    try { submit.disabled = false; } catch { } // už bylo odendáno
    try { returnButton.disabled = false; } catch { } // už bylo odendáno
  }, 150);
}


export async function pickBooth(formData) {
  let booth_type = null;
  try {
    const response = await fetch('/api/employees/me/events/booths/select', {
      method: 'PUT',
      body: formData
    });

    await handleUnauthorizedRedirect(response);

    const data = await response.json();

    if (response.status === 400 && data.error === 'no_selected_event') {
      throw new Error('no_selected_event');
    }

    if ((response.status === 400 && data.error === 'invalid_booth_id')
      || (response.status === 404 && data.error === 'booth_not_found')
      || (response.status === 400 && data.error === 'employee_not_linked_to_event')
      || (response.status === 400 && data.error === 'employee_not_linked_to_booth')) {
      throw new Error('bad_booth');
    }

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

    try {
      booth_type = data.booth_type;
    } catch {
      throw new Error('unexpected_error');
    }

  } catch (error) {
    if (error.message === 'no_selected_event') {
      renderEventPicker();
      return null;
    }
    const errorMessageEl = document.querySelector('.booth-submit-error-message');
    if (error.message === 'bad_booth') {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste vybrat akci nebo stánek ještě jednou.';
    } else {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste to prosím později.';
    }
    errorMessageEl.classList.add('display-block');

    return null;
  }
  removeEventBoothOverlay();
  return booth_type;
}


export async function unselectEventBooth() {
  order.reset();
  try {
    const response = await fetch('/api/employees/me/events/remove', {
      method: 'DELETE'
    });

    if (!response.ok) {
      throw new UnexpectedError();
    }

  } catch (error) {

  }

  await Promise.all([
    resetWalletsCache(),
    resetProductsCache(),
    removeReadCard(),
    unselectUserForUpdate(),
    saveSelectedCategory(null)
  ]);

}


export async function unselectBooth() {
  order.reset();
  try {
    const response = await fetch('/api/employees/me/events/booths/remove', {
      method: 'DELETE'
    });

    if (!response.ok) {
      throw new UnexpectedError();
    }

  } catch (error) {

  }

  await Promise.all([
    resetWalletsCache(),
    resetProductsCache(),
    removeReadCard(),
    unselectUserForUpdate(),
    saveSelectedCategory(null)
  ]);

}
