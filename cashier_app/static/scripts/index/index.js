import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker, unselectEventBooth, selectingEvent } from "./event_booth.js";
import { renderProducts, renderCategories, saveSelectedCategory, findProduct, getProductsAndCategories } from "./products.js";
import { order } from "./order.js";
import { renderSummary } from "./summary.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { getSessionInfo } from "../general/session.js";
import { setUpCardReading, lastReadCardId, newCardReadPromise, renderCard, removeReadCard, cancelCardReadPromise } from "./cards.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { phoneInputClickListeners } from "./phone_number_input.js";
import { selectRow, unselectRow } from "../general/table_utils.js";
import { editUserFormOnChange, openDeleteUserModal, openUserCardsModal, renderUsers, selectUserForUpdate, setOrder, unselectUserForUpdate } from "./users.js";
import { updateWalletBalance } from "./wallets.js";

const pageContainer = document.querySelector('#page-container');
const sellerPage = document.querySelector('#seller-page');
const productSide = sellerPage.querySelector('#product-side');
const summarySide = sellerPage.querySelector('#summary-side');
const productsSearchBar = sellerPage.querySelector('#products-search-bar');
const payError = document.querySelector('#pay-error');

const usersTableBody = document.querySelector('#users-table tbody');
const usersSearchBar = document.querySelector('#users-search-bar');

const userIdInput = document.querySelector('#user-id-input');

chooseAndLoadPage();


async function loadPage({
  products = false,
  summary = false,
  categories = false,
  cardInfo = false,
  users = false,
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

  if (cardInfo) {
    toLoad.push(renderCard());
  }

  if (users) {
    toLoad.push(renderUsers());
  }

  if (sidebar) {
    toLoad.push(renderSidebar());
  }

  if (header) {
    toLoad.push(renderHeader());
  }

  await Promise.all(toLoad);
}


async function chooseAndLoadPage() {
  const sessionInfo = await getSessionInfo().catch(() => {});

  if (!sessionInfo) {
    return; ///// display some error
  }

  if (sessionInfo.booth) {
    pageContainer.setAttribute('show', sessionInfo.booth.booth_type === 'seller' ? 'seller' : 'cashier');
    await Promise.all([
      setUpCardReading(false),
      loadPage({
        products: true,
        summary: true,
        categories: true,
        cardInfo: true,
        users: true,
        sidebar: true,
        header: true
      })
    ]);
  } else if (sessionInfo.event) {
    pageContainer.setAttribute('show', '');
    await Promise.all([
      renderBoothPicker(),
      loadPage({
        sidebar: true,
        header: true
      })
    ]);
  } else {
    pageContainer.setAttribute('show', '');
    await Promise.all([
      renderEventPicker(),
      loadPage({
        sidebar: true,
        header: true
      })
    ]);
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
  if (phoneInputClickListeners(event)) {
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
      cardInfo: true,
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
      cardInfo: true,
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
      cardInfo: true,
      summary: true
    });
    return;
  }

  const removeCardButton = event.target.closest('.remove-card-button');
  if (removeCardButton) {
    removeReadCard();
    await loadPage({
      cardInfo: true
    });
    return;
  }

  if (event.target.matches('#open-user-cards-modal')) {
    const userId = userIdInput.value.trim();
    if (userId) openUserCardsModal(userId);
  }


  if (event.target.matches('#pay-error')) {
    clearPayError();
    return;
  }

  const payButton = event.target.closest('#pay-button');
  if (payButton) {
    payButton.disabled = true;
    setUpCardReading(true);
    clearPayError();

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

    const result = await getProductsAndCategories().catch(() => {
      showPayError('unexpected_error');
    });
    if (!result) {
      payButton.disabled = false;
      return;
    }
    const products = result.products;

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
        showPayError(data.error || 'invalid_request', data.detail);
        payButton.disabled = false;
        return;
      }

      if (!response.ok) {
        showPayError('unexpected_error');
        payButton.disabled = false;
        return;
      }
    } catch (error) {
      showPayError('unexpected_error');
      return;
    } finally {
      payButton.disabled = false;
    }

    showPaySuccess();
    order.reset();
    updateWalletBalance(lastReadCardId, amount_czk);
    removeReadCard()
    await loadPage({
      products: true,
      cardInfo: true,
      summary: true
    });
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
      cardInfo: true,
      users: true,
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
    chooseAndLoadPage();
    loadPage({
      categories: true,
      products: true,
      summary: true,
      cardInfo: true,
      users: true,
      // sidebar: true,
      header: true
    });
    return;
  }

  // upravit uživatele
  const editUserBtn = event.target.closest('.edit-user');
  if (editUserBtn) {
    const row = editUserBtn.closest('tr[id]');
    if (row) {
      if (row.classList.contains('selected-for-update')) {
        await unselectUserForUpdate();
      } else {
        await selectUserForUpdate(row.id);
      }
    }
    return;
  }

  // smazat uživatele
  const deleteUserBtn = event.target.closest('.delete-user');
  if (deleteUserBtn) {
    const row = deleteUserBtn.closest('tr[id]');
    await openDeleteUserModal(row);
    return;
  }

  const closeModalBtn = event.target.closest('.close-modal');
  if (closeModalBtn) {
    const overlay = closeModalBtn.closest('.overlay');
    if (overlay) overlay.remove();
    return;
  }

  const cancelUserFormBtn = event.target.closest('#cancel-user-form');
  if (cancelUserFormBtn) {
    await unselectUserForUpdate();
  }

  // klinutí na span v záhlaví
  // nastavuje řazení
  const headerEl = event.target.closest('th');
  if (headerEl && event.target.matches('span')) {
    setOrder(headerEl);
    loadPage({
      users: true
    });
    return;
  }

  // kliknutí na řádek ho vybere (musí být pod ostatníma, aby nebral kliknutí na jiné věci)
  const row = event.target.closest('tr');
  if (row) {
    selectRow(row, usersTableBody);
    return;
  }

  const interactableEl = event.target.closest('input') || event.target.closest('button');
  if (interactableEl) {
    return;
  }
  // kliknutí na "nic" odvybere řádek
  unselectRow(usersTableBody);
});


usersTableBody.addEventListener('dblclick', async (event) => {
  const row = event.target.closest('tr[id]');
  if (row) {
    if (row.classList.contains('selected-for-update')) {
      await unselectUserForUpdate();
    } else {
      await selectUserForUpdate(row.id);
    }
    return;
  }
});


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
      cardInfo: true,
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
        cardInfo: true,
        users: true,
        // sidebar: true,
        header: true
      });
    } else if (booth_type === 'cashier') {
      pageContainer.setAttribute('show', 'cashier');
    }
    return;
  }
})


document.addEventListener('input', async (event) => {
  if (event.target === productsSearchBar) {
    loadPage({
      products: true
    });
  }

  if (event.target === usersSearchBar) {
    loadPage({
      users: true
    });
  }

  const userForm = event.target.closest('#user-form');
  if (userForm) {
    editUserFormOnChange(event);
    loadPage({
      users: true
    });
  }
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


function clearPayError() {
  payError.innerHTML = '';
  payError.classList.remove('show-pay-error');
}


function showPayError(error) {
  const setErr = (text) => {
    payError.innerHTML = escapeHTML(String(text));
    payError.classList.add('show-pay-error');
  };

  if (!error) {
    setErr('Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();
  switch (errorStr) {
    case 'unexpected_error':
      setErr('Něco se nepovedlo.');
      return;
    case 'no_selected_event':
      setErr('Něco se nepovedlo.');
      return;
    case 'no_selected_booth':
      setErr('Něco se nepovedlo.');
      return;
    case 'invalid_booth_type_for_transaction_type':
      setErr('Něco se nepovedlo.');
      return;
    case 'wallet_not_found':
      setErr('ID karty není registrované.');
      return;
    case 'amount_czk_must_be_a_number':
      setErr('Něco se nepovedlo.');
      return;
    case 'amount_czk_must_be_a_whole_number':
      setErr('Něco se nepovedlo.');
      return;
    case 'wallet_balance_czk_is_not_enough':
      setErr('Nedostatek peněz na kartě.');
      return;
    case 'resulting_wallet_balance_czk_is_too_high':
      setErr('Výsledná cená na kartě je moc velká.');
      return;
    case 'invalid_transaction_type':
      setErr('Něco se nepovedlo.');
      return;
    case 'invalid_transaction_type_for_amount_czk':
      setErr('Něco se nepovedlo.');
      return;
    case 'invalid_products_info':
      setErr('Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('amount_czk_must_be_more_than_or_equal_to')) {
    setErr('Cena je moc velké číslo.');
    return;
  }
  if (errorStr.includes('amount_czk_must_be_less_than_or_equal_to')) {
    setErr('Cena je moc velké číslo.');
    return;
  }

  setErr(errorStr); // make sure to remove these and put some general type error message
}


function showPaySuccess() {
  const existing = document.querySelector('.overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div')
  overlay.className = 'overlay';

  // add cross close button
  overlay.innerHTML = `
    <div id="successful-payment-modal">
      <img id="successful-payment-icon" src="/static/images/icons/checkmark_icon.png">
      <div id="successful-payment-message">Platba proběhla úspěšně.</div>
    </div>
  `;

  pageContainer.appendChild(overlay);

  setTimeout(() => {
    if (overlay) overlay.remove();
  }, 2000);
}
