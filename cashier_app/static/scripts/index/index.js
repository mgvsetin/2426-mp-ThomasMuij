import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker } from "./event_booth.js";
import { renderProducts } from "./products.js";
import { Order } from "./order.js";
import { renderSummary } from "./summary.js";

const productSide = document.querySelector('#product-side');
const order = document.querySelector('#order')
const header = document.querySelector('#header');
const searchBar = document.querySelector('#product-search-bar');


renderProducts();
renderSummary();
searchBar.value = new URL(window.location).searchParams.get('search_query') || '';


header.addEventListener('click', async (event) => {
  const order = await Order.getOrder();

  if (event.target.matches('#logout-button')) {
    order.resetAndRemoveFromStorage();
  }
})


productSide.addEventListener('submit', async (event) => {
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
      renderSummary();
    }
    return;
  }
})

searchBar.addEventListener('keydown', (event) => {
  if (event.code === 'Enter') {
    addSearchParam();
    return;
  }
})

order.addEventListener('click', async (event) => {
  const searchButton = event.target.closest('#search-button');
  if (searchButton && productSide.contains(searchButton)) {
    addSearchParam();
    return;
  }

  const returnButton = event.target.closest('#return-to-event-picker-button');
  if (returnButton && productSide.contains(returnButton)) {
    renderEventPicker(productSide);
    // do i need to do more?
    return;
  }

  const order = await Order.getOrder();
  if (event.target.matches('.plus-button, .summary-plus-button')) {
    const plusButton = event.target;
    const productId = plusButton.dataset.productId;
    order.updateQuantity(productId, 1);
    renderProducts(); // make a cache or sum (maybe in the service worker? or maybe not for safety?)
    // or rerender the specific value and not all the products
    renderSummary();
  }

  if (event.target.matches('.minus-button, .summary-minus-button')) {
    const minusButton = event.target;
    const productId = minusButton.dataset.productId;
    order.updateQuantity(productId, -1);
    renderProducts();
    renderSummary();
  }

  if (event.target.matches('#pay-button')) {
    console.log('pay');
  }
})



const newActionButton = document.querySelector('#choose-new-event-button');
newActionButton.addEventListener('click', () => {
  // make sure this removes the event and booth to prevent having different booth/event (make sure to validate on backend too)
  // make sure the zpět removes the booths/events too
  renderEventPicker(productSide);
  return;
})


function addSearchParam() {
  const searchQuery = searchBar.value.toLowerCase().trim();
  const url = new URL(window.location);
  const currentQuery = url.searchParams.get('search_query') || '';

  if (searchQuery === currentQuery) {
    return;
  }

  if (!searchQuery) {
    url.searchParams.delete('search_query');
    window.location.href = url;
    return;
  }

  url.searchParams.set('search_query', searchQuery);
  window.location.href = url;
}