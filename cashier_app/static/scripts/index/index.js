import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker, unselectEventBooth, selectingEvent } from "./event_booth.js";
import { renderProducts, renderSelectableCategories, saveSelectedCategory } from "./products.js";
import { order } from "./order.js";
import { renderSummary } from "./summary.js";
import { renderDropdownSessionInfo } from "../general/header.js";

const header = document.querySelector('#header');
const searchBar = header.querySelector('#product-search-bar')
const accountDropdown = header.querySelector('#account-dropdown')
const sessionInfoEl = accountDropdown.querySelector('#session-info')
const sidebar = document.querySelector('#sidebar');
const orderEl = document.querySelector('#order');
const productSide = orderEl.querySelector('#product-side');
const summarySide = orderEl.querySelector('#summary-side');

let listenersMade = false;

loadPage({
  products: true,
  summary: true,
  categories: true,
  sessionInfo: true
});
makeEventListeners();


async function loadPage({
  products = false,
  summary = false,
  categories = false,
  sessionInfo = false
} = {}) {
  
  const toLoad = [];

  if (products) {
    toLoad.push(renderProducts());
  }

  if (summary) {
    toLoad.push(renderSummary());
  }

  if (categories) {
    toLoad.push(renderSelectableCategories());
  }

  if (sessionInfo) {
    toLoad.push(renderDropdownSessionInfo());
  }

  await Promise.all(toLoad);
}


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
        loadPage({
          categories: true,
          products: true
        });
        return;
      }

      saveSelectedCategory(categoryButton.dataset.category)
      loadPage({
        categories: true,
        products: true
      });
      return;
    }

    if (event.target.matches('.plus-button, .summary-plus-button')) {
      const plusButton = event.target;
      const productId = plusButton.dataset.productId;
      order.updateQuantity(productId, 1);
      loadPage({
        products: true,
        summary: true
      });
      return;
    }

    if (event.target.matches('.minus-button, .summary-minus-button')) {
      const minusButton = event.target;
      const productId = minusButton.dataset.productId;
      order.updateQuantity(productId, -1);
      loadPage({
        products: true,
        summary: true
      });
      return;
    }

    const removeItemButton = event.target.closest('.remove-item-button');
    if (removeItemButton && summarySide.contains(removeItemButton)) {
      const productId = removeItemButton.dataset.productId;
      order.setQuantity(productId, 0);
      loadPage({
        products: true,
        summary: true
      });
      return;
    }

    const returnButton = event.target.closest('#return-to-event-picker-button');
    if (returnButton && productSide.contains(returnButton)) {
      await renderEventPicker();
      return;
    }

    if (event.target.matches('#choose-new-event-button')) {
      if (selectingEvent) {
        return;
      }
      await unselectEventBooth();
      loadPage({
        categories: true,
        sessionInfo: true,
        products: true,
        summary: true
      });
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
      loadPage({
        products: true,
        summary: true
      });
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
        loadPage({
          categories: true,
          sessionInfo: true,
          products: true,
          summary: true
        });
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

