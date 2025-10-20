const order = document.querySelector('#order');
const logoutButton = document.querySelector('#logout-button')

order.addEventListener('submit', async (event) => {
  const form = event.target.closest('#event-selector-form');
  if (form && order.contains(form)) {
    event.preventDefault();
    const formData = new FormData(form);
    const selectedEventId = formData.get('event');
    console.log(selectedEventId)
    // send it to the backend, continue to the booths
  }
})

loadPage();

async function loadPage() {
  try {
    const response = await fetch('/session/booth-is-registered');

    if (!response.ok) {
      throw 'response not ok';
    }

    const boothIsRegistered = await response.json();

    if (boothIsRegistered) {
      await renderOrder();
    } else {
      await pickEvent();
      // await pickBooth()
    }
  } catch (error) {
    // finish
    console.log(error)
  }
}


async function pickEvent() {
  try {
  const response = await fetch('/events/get-active-for-employee');

  const data = await response.json();

  if (response.status === 401) {
    window.location.href = data.redirect_url;
  }

  let html_event_options = ''
  if (data) {
    data.forEach((event) => {
      html_event_options += `
        <option value="${event.id}">
          ${event.name}
        </option>`
    })
  }

  order.innerHTML = `
  <div id="event-selector-centerer">
    <div id="event-selector-form-container">
      <form id="event-selector-form" action="/events/get-active-for-employee" method="post">
        <label for="event-selector" id="event-selector-label">Vyberte akci</label>
        <select id="event-selector" name="event">
          ${html_event_options}
        </select>
        <input type="submit" value="Vybrat" id="submit-event-choice">
      </form>
    </div>
  </div>`;

  } catch (error) {
    order.innerHTML = `
    <div id="event-selector-centerer">
      <div id="event-selector-form-container">
        <div id="event-error-message">
          Nepovedlo se načíst akce. Zkuste to prosím později.
        </div>
      </div>
    </div>`;
    }
}


async function renderOrder() {
  response = await fetch('')
}