import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker, unselectEventBooth, selectingEvent } from "./event_booth.js";
import { renderProducts, renderCategories, saveSelectedCategory, findProduct, getProductsAndCategories } from "./products.js";
import { order } from "./order.js";
import { renderSummary } from "./summary.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { getSessionInfo } from "../general/session.js";
import { setUpCardReading, lastReadCardId, newCardReadPromise, renderCard, removeReadCard, getWalletByTag, getWallets, updateWalletBalance, cancelCardReadPromise } from "./cards.js";

const pageContainer = document.querySelector('#page-container');
const sellerPage = document.querySelector('#seller-page');
const productSide = sellerPage.querySelector('#product-side');
const summarySide = sellerPage.querySelector('#summary-side');
const searchBar = sellerPage.querySelector('#search-bar');

choosePage();

loadPage({
  products: true,
  summary: true,
  categories: true,
  card: true,
  sidebar: true,
  header: true
});


async function loadPage({
  products = false,
  summary = false,
  categories = false,
  card = false,
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

  if (card) {
    toLoad.push(renderCard());
  }

  if (sidebar) {
    toLoad.push(renderSidebar());
  }

  if (header) {
    toLoad.push(renderHeader());
  }

  await Promise.all(toLoad);
}


async function choosePage() {
  const sessionInfo = await getSessionInfo();

  if (sessionInfo && sessionInfo.booth) {
    setUpCardReading(false);
    pageContainer.setAttribute('show', sessionInfo.booth.booth_type === 'seller' ? 'seller' : 'cashier');
  } else {
    pageContainer.setAttribute('show', '');
  }
}


// function makeEventListeners() {
//   if (listenersMade) {
//     throw new Error('Listeners should only be created once');
//   }
//   listenersMade = true;

document.addEventListener('click', async (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
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
      card: true,
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
      card: true,
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
      card: true,
      summary: true
    });
    return;
  }

  const payButton = event.target.closest('#pay-button');
  if (payButton) {
    payButton.disabled = true;
    setUpCardReading(true);
    clearPayErrors();

    if (!lastReadCardId) {
      const existing = document.querySelector('.overlay');
      if (existing) existing.remove();

      const overlay = document.createElement('div')
      overlay.className = 'overlay';

      overlay.innerHTML = `
        <div id="scan-card-request-modal">
          <div id="scan-card-request-message">Naskenujte kartu</div>
          <button id="cancel-scan-card-request-modal">Zrušit</button>
        </div>
      `;

      pageContainer.appendChild(overlay);
      const result = await newCardReadPromise;
      if (overlay) overlay.remove();
      if (!result) {
        payButton.disabled = false;
        return;
      }
    }

    const products = (await getProductsAndCategories()).products;

    const productsInfo = [];
    let amount_czk = 0;

    order.items.forEach(orderItem => {
      const product = findProduct(products, orderItem.productId);
      product.quantity = orderItem.quantity;
      productsInfo.push(product);
      amount_czk -= product.price * product.quantity;
    });

    const formData = new FormData();
    formData.set('tag-id', lastReadCardId);
    formData.set('transaction-type', 'payment');
    formData.set('products-info', JSON.stringify(productsInfo));
    formData.set('amount-czk', amount_czk);

    try {
      const response = await fetch('api/transactions/make', {
        method: 'post',
        body: formData
      });

      if (response.status === 401) {
        const json = await response.json();
        window.location.href = json.redirect_url;
        return;
      }

      const data = await response.json();

      if (response.status === 400) {
        showPayErrors(data.error || 'invalid_request', data.detail);
        payButton.disabled = false;
        return;
      }

      if (!response.ok) {
        showPayErrors('unexpected_error');
        payButton.disabled = false;
        return;
      }
    } catch (error) {
      showPayErrors('unexpected_error');
      return;
    } finally {
      payButton.disabled = false;
    }

    showPaySuccess();
    order.reset();
    updateWalletBalance(lastReadCardId, amount_czk);
    await Promise.all([
      removeReadCard(),
      loadPage({
        products: true,
        card: true,
        summary: true
      })
    ]);
    return;
  }

  const cancelScanCardRequestButton = event.target.closest('#cancel-scan-card-request-modal')
  if (cancelScanCardRequestButton) {
    const overlay = cancelScanCardRequestButton.closest('.overlay');
    if (overlay) overlay.remove();
    cancelCardReadPromise();
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

  if (event.target.matches('#choose-card-reader')) {
    await setUpCardReading(true);
  }

  const closeChoosingReader = event.target.closest('#close-choosing-reader');
  if (closeChoosingReader) {
    const modal = document.querySelector('#select-reader-modal');
    if (modal) modal.remove();
  }

  // header protože je jen pro index:
  if (event.target.matches('#choose-new-event-button')) {
    if (selectingEvent) {
      return;
    }
    await unselectEventBooth();
    choosePage();
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
    const newQuantity = Number(quantityInput.value.replace(/\s/g, ''));
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
      card: true,
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
    setUpCardReading(true);
    const formData = new FormData(boothForm);
    const booth_type = await pickBooth(formData);

    if (booth_type === 'seller') {
      pageContainer.setAttribute('show', 'seller');
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


sellerPage.addEventListener('focusout', (event) => {
  if (event.target.matches('.productQuantity, .summary-productQuantity')) {
    const quantityInput = event.target;
    const productId = quantityInput.dataset.productId;
    const currentQuantity = order.getQuantity(productId);

    quantityInput.value = currentQuantity;
    return;
  }
})
// }

navigator.serial.addEventListener('connect', (event) => {
  setUpCardReading(false);
});


function clearPayErrors() {

}


function showPayErrors(error, detail) {
  console.log(error)
}


function showPaySuccess() {

}
