import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker, unselectEventBooth, selectingEvent } from "./event_booth.js";
import { renderProducts, renderSelectableCategories, saveSelectedCategory } from "./products.js";
import { order } from "./order.js";
import { renderSummary } from "./summary.js";

const header = document.querySelector('#header');
const searchBar = header.querySelector('#product-search-bar')
const accountDropdown = header.querySelector('#account-dropdown')
const sessionInfoEl = accountDropdown.querySelector('#session-info')
const sidebar = document.querySelector('#sidebar');
const orderEl = document.querySelector('#order');
const productSide = orderEl.querySelector('#product-side');
const summarySide = orderEl.querySelector('#summary-side');

let listenersMade = false;

renderProducts();
renderSummary();
renderSelectableCategories();
renderSessionInfo();
makeEventListeners();
searchBar.value = new URL(window.location).searchParams.get('search_query') || '';


function makeEventListeners() {
  if (listenersMade) {
    throw new Error('Listeners should only be created once');
  }
  listenersMade = true;

  document.addEventListener('click', async (event) => {
    if (!(event.target.matches('#account-button, #account-icon')
      || (event.target.closest('#account-dropdown') && !event.target.closest('button, a')))) {
      // kliknutí jinam než na dropdown nebo ikonu uživatele
      // nebo na <button>/<a> v něm
      accountDropdown.removeAttribute('opened');
    }

    if (!event.target.closest('#sidebar') && !event.target.matches('#open-sidebar-button, #open-sidebar-icon')) {
      // kliknutí jinam než na sidebar nebo otevírání sidebar
      sidebar.removeAttribute('opened');
    }

    if (event.target.matches('#logout-link')) {
      // musí se zavolat před await
      // jestli bude potřeba await tak se prní
      // musí zavolat preventDefault()
      order.reset();
      saveSelectedCategory(null);
      // sessionStorage.clear();
      return;
    }

    if (event.target.matches('#open-sidebar-button, #open-sidebar-icon')) {
      sidebar.setAttribute('opened', '');
      return;
    }

    const searchButton = event.target.closest('#search-button');
    if (searchButton && header.contains(searchButton)) {
      addSearchParam();
      return;
    }

    if (event.target.matches('#account-button, #account-icon')) {
      accountDropdown.toggleAttribute('opened');
      return;
    }

    if (event.target.matches('#close-sidebar-button, #close-sidebar-icon')) {
      sidebar.removeAttribute('opened');
      return;
    }

    if (event.target.matches('.selectable-category')) {
      const categoryButton = event.target;
      if (categoryButton.classList.contains('selected')) {
        saveSelectedCategory(null);
        renderSelectableCategories();
        renderProducts();
        return;
      }

      saveSelectedCategory(categoryButton.dataset.category)
      renderSelectableCategories();
      renderProducts();
      return;
    }

    if (event.target.matches('.plus-button, .summary-plus-button')) {
      const plusButton = event.target;
      const productId = plusButton.dataset.productId;
      order.updateQuantity(productId, 1);
      renderProducts();
      renderSummary();
      return;
    }

    if (event.target.matches('.minus-button, .summary-minus-button')) {
      const minusButton = event.target;
      const productId = minusButton.dataset.productId;
      order.updateQuantity(productId, -1);
      renderProducts();
      renderSummary();
      return;
    }

    const removeItemButton = event.target.closest('.remove-item-button');
    if (removeItemButton && summarySide.contains(removeItemButton)) {
      const productId = removeItemButton.dataset.productId;
      order.setQuantity(productId, 0);
      renderProducts();
      renderSummary();
      return;
    }

    const returnButton = event.target.closest('#return-to-event-picker-button');
    if (returnButton && productSide.contains(returnButton)) {
      renderEventPicker();
      return;
    }

    if (event.target.matches('#choose-new-event-button')) {
      if (selectingEvent) {
        return;
      }
      await unselectEventBooth();
      await Promise.all([
        renderSelectableCategories(),
        renderProducts(),
        renderSummary(),
        renderSessionInfo()
      ]);
      return;
    }
  })

  document.addEventListener('keydown', (event) => {
    if (event.code === 'Enter' && event.target.matches('#product-search-bar')) {
      addSearchParam();
      return;
    }

    if (event.code === 'Enter' && event.target.matches('.productQuantity, .summary-productQuantity')) {
      const quantityInput = event.target;
      const newQuantity = Number(quantityInput.value.replace(/\s/g,''));
      const productId = quantityInput.dataset.productId;
      const currentQuantity = order.getQuantity(productId);

      if (Number.isNaN(newQuantity)) {
        quantityInput.value = currentQuantity;
        return;
      }

      if (newQuantity === currentQuantity) {
        return;
      }

      order.setQuantity(productId, newQuantity);
      renderProducts();
      renderSummary();
      return;
    }
  })

  productSide.addEventListener('submit', async (event) => {
    const eventForm = event.target.closest('#event-selector-form');
    if (eventForm && productSide.contains(eventForm)) {
      event.preventDefault();
      const formData = new FormData(eventForm);

      const ok = await pickEvent(formData);

      if (ok) {
        renderBoothPicker();
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
        renderSelectableCategories();
        renderSessionInfo();
      }
      return;
    }
  })

  orderEl.addEventListener('focusout', (event) => {
    if (event.target.matches('.productQuantity, .summary-productQuantity')) {
      const quantityInput = event.target;
      const productId = quantityInput.dataset.productId;
      const currentQuantity = order.getQuantity(productId);

      quantityInput.value = currentQuantity;
      return;
    }
  })
}


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


async function getSessionInfo() {
  try {
    const response = await fetch('/api/session/');

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

    const data = await response.json();

    return data

  } catch (error) {
    return false;
  }
}


export async function renderSessionInfo() {
  const sessionInfo = await getSessionInfo();

  if (!sessionInfo) {
    return;
  }

  let sessionInfoHTML = '';

  try { sessionInfoHTML += `<div id="username">${sessionInfo.employee.username}</div>`; } catch {}
  try { sessionInfoHTML += `<div id="event">${sessionInfo.event.name}</div>`; } catch {}
  try { sessionInfoHTML += `<div id="booth">${sessionInfo.booth.name}</div>`; } catch {}

  sessionInfoEl.innerHTML = sessionInfoHTML;
}