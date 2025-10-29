import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker } from "./event_booth.js";
import { renderProducts } from "./products.js";
import { order } from "./order.js";

const productSide = document.querySelector('#product-side');

productSide.addEventListener('submit', async (event) => {
  // use matches() for the others?
  const eventForm = event.target.closest('#event-selector-form');
  if (eventForm && productSide.contains(eventForm)) {
    event.preventDefault();
    const formData = new FormData(eventForm);

    const ok = await pickEvent(formData);

    if (ok) {
      renderBoothPicker(productSide);
    }
    return;
  }


  const boothForm = event.target.closest('#booth-selector-form');
  if (boothForm && productSide.contains(boothForm)) {
    event.preventDefault();
    const formData = new FormData(boothForm);
    const ok = await pickBooth(formData);

    if (ok) {
      renderProducts();
    }
    return;
  }
})


productSide.addEventListener('click', async (event) => {
  const returnButton = event.target.closest('#return-to-event-picker-button');
  if (returnButton && productSide.contains(returnButton)) {
    renderEventPicker(productSide);
    return;
  }

  const plusButton = event.target.closest('.plus-button')

})

const newActionButton = document.querySelector('#choose-new-event-button');
newActionButton.addEventListener('click', () => {
  // make sure this removes the event and booth to prevent having different booth/event (make sure to validate on backend too)
  // make sure the zpět removes the booths/events too
  renderEventPicker(productSide);
  return;
})


renderProducts();


