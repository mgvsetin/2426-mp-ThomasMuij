import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker, unselectEventBooth, selectingEvent } from "./event_booth.js";
import { renderProducts, renderCategories, saveSelectedCategory } from "./products.js";
import { order } from "./order.js";
import { renderSummary } from "./summary.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";

const pageContainer = document.querySelector('#page-container');
const orderEl = document.querySelector('#order');
const productSide = orderEl.querySelector('#product-side');
const summarySide = orderEl.querySelector('#summary-side');
const searchBar = orderEl.querySelector('#search-bar');

loadPage({
  products: true,
  summary: true,
  categories: true,
  sidebar: true,
  header: true
});


async function loadPage({
  products = false,
  summary = false,
  categories = false,
  sidebar = false,
  header = false
} = {}) {
  
  const toLoad = [];

  if (products) {
    toLoad.push(renderProducts());
  }

  if (summary) {
    toLoad.push(renderSummary());
  }

  if (categories) {
    toLoad.push(renderCategories());
  }

  if (sidebar) {
    toLoad.push(renderSidebar());
  }

  if (header) {
    toLoad.push(renderHeader());
  }

  await Promise.all(toLoad);
}


// function makeEventListeners() {
//   if (listenersMade) {
//     throw new Error('Listeners should only be created once');
//   }
//   listenersMade = true;

document.addEventListener('click', async (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick =  sidebarClickListeners(event);
  if (headerClick || sidebarClick) {
    return;
  }

  if (event.target.matches('.category')) {
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

  const payButton = event.target.closest('#pay-button');
  if (payButton) {
    payButton.disabled = true;
  }

  const returnButton = event.target.closest('#return-to-event-picker-button');
  if (returnButton) {
    await unselectEventBooth();
    loadPage({
      categories: true,
      products: true,
      summary: true,
      // sidebar: true,
      header: true
    });
    return;
  }

  // header protože je jen pro index:
  if (event.target.matches('#choose-new-event-button')) {
    if (selectingEvent) {
      return;
    }
    await unselectEventBooth();
    loadPage({
      categories: true,
      products: true,
      summary: true,
      // sidebar: true,
      header: true
    });
    return;
  }
})

document.addEventListener('keydown', (event) => {
  // headerKeydownListeners(event);

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

document.addEventListener('submit', async (event) => {
  const eventForm = event.target.closest('#event-selector-form');
  if (eventForm) {
    event.preventDefault();
    const formData = new FormData(eventForm);

    const ok = await pickEvent(formData);

    if (ok) {
      loadPage({
        header: true,
        // sidebar: true
      })
      renderBoothPicker();
    }
    return;
  }


  const boothForm = event.target.closest('#booth-selector-form');
  if (boothForm) {
    event.preventDefault();
    const formData = new FormData(boothForm);
    const booth_type = await pickBooth(formData);

    if (booth_type === 'seller') {
      pageContainer.setAttribute('show', 'order');
      loadPage({
        categories: true,
        products: true,
        summary: true,
        // sidebar: true,
        header: true
      });
    } else if (booth_type === 'cashier') {
      pageContainer.setAttribute('show', 'cashier');
    }
    return;
  }
})


searchBar.addEventListener('input', (event) => {
  // if (event.target.matches('#search-bar')) {
    loadPage({
      products: true
    })
  // }
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
// }
