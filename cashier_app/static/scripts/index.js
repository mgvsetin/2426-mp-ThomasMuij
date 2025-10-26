const productSide = document.querySelector('#product-side');
const logoutButton = document.querySelector('#logout-button');

productSide.addEventListener('submit', async (event) => {
  const eventForm = event.target.closest('#event-selector-form');
  if (eventForm && productSide.contains(eventForm)) {
    event.preventDefault();
    const formData = new FormData(eventForm);
    pickEvent(formData);
  }


  const boothForm = event.target.closest('#booth-selector-form');
  if (boothForm && productSide.contains(boothForm)) {
    event.preventDefault();
    const formData = new FormData(boothForm);
    pickBooth(formData);
  }
})


productSide.addEventListener('click', async (event) => {
  const returnButton = event.target.closest('#return-to-event-picker-button');
  if (returnButton && productSide.contains(returnButton)) {
    renderEventPicker();
  }
})

const newActionButton = document.querySelector('#choose-new-event-button');
newActionButton.addEventListener('click', () => {
  renderEventPicker();
})

pickBoothEventIfNecessary();

async function pickBoothEventIfNecessary() {
  try {
    const response = await fetch('/session/booth-is-registered');

    if (!response.ok) {
      throw 'bad_response';
    }

    const boothIsRegistered = await response.json();

    if (!boothIsRegistered) {
      renderEventPicker();
      // submit -> renderBoothPicker() -> submit -> renderProducts;
      return;
    } else {
      // renderProducts();
      return;
    }
  } catch (error) {
    console.log(error);
    renderEventPicker();
    return;
  }
}


function makeEventBoothOverlay() {
  const existing = productSide.querySelector(':scope > .event-booth-selector-centerer');
  if (existing) productSide.removeChild(existing);

  const overlay = document.createElement('div')
  overlay.className = 'event-booth-selector-centerer';

  // productSide.classList.add('disable-children');

  productSide.appendChild(overlay);

  return overlay;
}


function removeEventBoothOverlay() {
  const overlay = document.querySelector('.event-booth-selector-centerer');

  if (!overlay) {
    return;
  }

  // productSide.classList.remove('disable-children');

  if (overlay && overlay.parentElement) overlay.parentElement.removeChild(overlay);
}


async function renderEventPicker() {
  try {
  const response = await fetch('/events/get-active-for-employee');

  const data = await response.json();

  if (response.status === 401) {
    window.location.href = data.redirect_url;
  }

  if (!response.ok) {
    throw 'unexpected_error'
  }

  const overlay = makeEventBoothOverlay();

  let html_event_options = ''
  if (data) {
    data.forEach((event) => {
      html_event_options += `
        <option value="${event.id}">
          ${event.name}
        </option>`
    })
  }

  overlay.innerHTML = `
  <div id="event-selector-form-container">
    <form id="event-selector-form" method="post">
      <label for="event-selector" id="event-selector-label">Vyberte akci</label>
      <select id="event-selector" name="event">
        ${html_event_options}
      </select>
      <input type="submit" value="Vybrat" id="submit-event-choice">
    </form>
    <div class='event-submit-error-message'></div>
  </div>`;

  } catch (error) {
    const overlay = makeEventBoothOverlay();
    overlay.innerHTML = `
    <div id="event-selector-form-container">
      <div id="event-error-message">
        Nepovedlo se načíst akce. Zkuste to prosím později.
      </div>
    </div>`;
    }
}


async function pickEvent(formData) {
  try {
    const response = await fetch('/events/select', {
      method: 'POST',
      body: formData
    });

    data = await response.json();

    if (response.status === 401) {
      window.location.href = data.redirect_url
    }

    if (response.status === 403 && data.error === 'employee_not_linked_to_event') {
      window.location.href = data.redirect_url
    }

    if ((response.status === 400 && data.error === 'invalid_event_id')
      ||(response.status === 404 && data.error === 'event_not_found_or_inactive')
      ||(response.status === 403 && data.error === 'employee_not_linked_to_event')) {
      throw 'bad_event';
    }

    if (!response.ok) {
      throw 'unknown_error';
    }

  } catch(error) {
    const errorMessage = document.querySelector('.event-submit-error-message');
    if (error === 'bad_event') {
      errorMessage.innerHTML = 'Něco se nepovedlo. Zkuste načíst stránku a vybrat akci ještě jednou.';
    } else {
      errorMessage.innerHTML = 'Něco se nepovedlo. Zkuste to prosím později.';
    }
    errorMessage.classList.add('display-block');

    return;
  }

  renderBoothPicker();
}


async function pickBooth(formData) {
  try {
    const response = await fetch('/events/booths/select', {
      method: 'POST',
      body: formData
    });

    data = await response.json();

    if (response.status === 401) {
      window.location.href = data.redirect_url;
    }

    if (response.status === 400 && data.error === 'no_selected_event') {
      renderEventPicker();
      return;
    }

    if ((response.status === 400 && data.error === 'invalid_booth_id')
      ||(response.status === 404 && data.error === 'booth_not_found')
      ||(response.status === 403 && data.error === 'employee_not_linked_to_event')) {
      throw 'bad_booth';
    }

    if (!response.ok) {
      throw 'unknown_error';
    }

  } catch(error) {
    const errorMessage = document.querySelector('.booth-submit-error-message');
    console.log(error)
    if (error === 'bad_booth') {
      errorMessage.innerHTML = 'Něco se nepovedlo. Zkuste vybrat akci nebo stánek ještě jednou.';
    } else {
      errorMessage.innerHTML = 'Něco se nepovedlo. Zkuste to prosím později.';
    }
    errorMessage.classList.add('display-block');

    return;
  }

  removeEventBoothOverlay();
  // renderProducts();
}


async function renderBoothPicker() {
  try {
  const response = await fetch('/events/booths/get-for-employee');

  const data = await response.json();

  if (response.status === 401) {
    window.location.href = data.redirect_url;
  }

  if (response.status === 400 && response.error === 'no_selected_event') {
    renderEventPicker();
    return;
  }

  if (!response.ok) {
    throw 'unexpected_error';
  }

  const overlay = makeEventBoothOverlay();

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
      <form id="booth-selector-form" method="post">
        <label for="booth-selector" id="booth-selector-label">Vyberte stánek</label>
        <select id="booth-selector" name="booth">
          ${html_booth_options}
        </select>
        <input type="submit" value="Vybrat" id="submit-booth-choice">
      </form>
      <button id="return-to-event-picker-button">
        Zpět
      </button>
      <div class="booth-submit-error-message"></div>
    </div>`;

  } catch (error) {
    const overlay = makeEventBoothOverlay();
    overlay.innerHTML = `
      <div id="booth-selector-form-container">
        <div id="booth-error-message">
          Nepovedlo se načíst stánky. Zkuste to prosím později.
        </div>
      </div>`;
    }
}
