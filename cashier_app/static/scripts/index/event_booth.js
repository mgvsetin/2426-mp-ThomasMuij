/**
 * @file Výběr akce a stánku pro pokladní aplikaci.
 */
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

/**
 * Vytvoří kontejner pro event nebo booth selector, aby se zarvonal na střed.
 * @param {HTMLElement} container - Kontejner, do kterého se vloží
 * @returns {HTMLElement} Vytvořený kontejner
 */
function makeEventBoothSelectorContainer(container) {
  const existing = document.querySelector('#event-booth-selector-container');
  existing?.remove();

  const eventBoothSelectorContainer = document.createElement('div')
  eventBoothSelectorContainer.id = 'event-booth-selector-container';

  // container.classList.add('disable-children');

  container.appendChild(eventBoothSelectorContainer);

  return eventBoothSelectorContainer;
}


/**
 * Odstraní překryvnou vrstvu (overlay) pro výběr akce nebo stánku.
 */
function removeEventBoothSelectorContainer() {
  const container = document.querySelector('#event-booth-selector-container');
  container?.remove();
}


/**
 * Vykreslí formulář pro výběr akce. Načte dostupné akce ze serveru a zobrazí je uživateli.
 * V případě chyby zobrazí chybovou hlášku.
 * @returns {Promise<void>}
 */
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
    const container = makeEventBoothSelectorContainer(pageContainer);
    container.innerHTML = `
    <div id="event-selector-form-container">
      <div id="event-error-message">
        Nepovedlo se načíst akce. Zkuste to prosím později.
      </div>
    </div>`;
    return;
  }

  const container = makeEventBoothSelectorContainer(pageContainer);

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

  container.innerHTML = `
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
  const submit = container.querySelector('#submit-event-choice');
  setTimeout(() => {
    try { submit.disabled = false; } catch { } // už bylo odendáno
  }, 150);
}


/**
 * Odešle výběr akce na server a zpracuje odpověď.
 * Zobrazí chybové hlášky podle typu chyby.
 * @param {FormData} formData - Data z formuláře s vybranou akcí
 * @returns {Promise<boolean>} Vrací true při úspěchu, jinak false
 */
export async function selectEvent(formData) {
  try {
    const response = await fetch('/api/employees/me/events/select', {
      method: 'PUT',
      body: formData
    });

    await handleUnauthorizedRedirect(response);

    const data = await response.json();

    if (response.status === 400 && data.error === 'missing_event_id') {
      throw new Error('missing_event_id')
    }

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
    if (error.message === 'missing_event_id') {
      errorMessageEl.innerHTML = 'Není vybraná žádná akce.'
    } else if (error.message === 'bad_event') {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste načíst stránku a vybrat akci ještě jednou.';
    } else {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste to prosím později.';
    }
    errorMessageEl.classList.add('display-block');
    return false;
  }
  selectingEvent = false;
  removeEventBoothSelectorContainer();
  return true;
}


/**
 * Vykreslí formulář pro výběr stánku. Načte dostupné stánky ze serveru a zobrazí je uživateli.
 * V případě chyby zobrazí chybovou hlášku nebo vyvolá výběr akce.
 * @returns {Promise<void>}
 */
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
    const container = makeEventBoothSelectorContainer();
    container.innerHTML = `
      <div id="booth-selector-form-container">
        <div id="booth-error-message">
          Nepovedlo se načíst stánky. Zkuste to prosím později.
        </div>
      </div>`;
    return;
  }

  const container = makeEventBoothSelectorContainer(pageContainer);

  let html_booth_options = ''
  if (data) {
    data.forEach((booth) => {
      html_booth_options += `
          <option value="${booth.id}">
            ${booth.name}
          </option>`
    })
  }

  container.innerHTML = `
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
  const submit = container.querySelector('#submit-booth-choice');
  const returnButton = container.querySelector('#return-to-event-picker-button');
  setTimeout(() => {
    try { submit.disabled = false; } catch { } // už bylo odendáno
    try { returnButton.disabled = false; } catch { } // už bylo odendáno
  }, 150);
}


/**
 * Odešle výběr stánku na server a zpracuje odpověď.
 * Zobrazí chybové hlášky podle typu chyby.
 * @param {FormData} formData - Data z formuláře s vybraným stánkem
 * @returns {Promise<string|null>} Vrací typ stánku při úspěchu, jinak null
 */
export async function selectBooth(formData) {
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

    if (response.status === 400 && data.error === 'missing_booth_id') {
      throw new Error('missing_booth_id')
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

    if (error.message === 'missing_booth_id') {
      errorMessageEl.innerHTML = 'Není vybraný žádný stánek.';
    } else if (error.message === 'bad_booth') {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste vybrat akci nebo stánek ještě jednou.';
    } else {
      errorMessageEl.innerHTML = 'Něco se nepovedlo. Zkuste to prosím později.';
    }
    errorMessageEl.classList.add('display-block');

    return null;
  }
  removeEventBoothSelectorContainer();
  return booth_type;
}


/**
 * Zruší výběr akce a stánku, resetuje stav aplikace a vymaže související data.
 * @returns {Promise<void>}
 */
export async function unselectEventBooth() {
  order.reset();
  const response = await fetch('/api/employees/me/events/remove', {
    method: 'DELETE'
  });

  if (!response.ok) {
    throw new UnexpectedError();
  }

  await Promise.all([
    resetWalletsCache(),
    resetProductsCache(),
    removeReadCard(),
    unselectUserForUpdate(),
    saveSelectedCategory(null)
  ]);

}


/**
 * Zruší výběr stánku, resetuje stav aplikace a vymaže související data.
 * @returns {Promise<void>}
 */
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
