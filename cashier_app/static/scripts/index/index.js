import { pickEvent, pickBooth, renderEventPicker, renderBoothPicker, unselectEventBooth, selectingEvent, unselectBooth } from "./event_booth.js";
import { renderProducts, renderCategories, saveSelectedCategory, findProduct, fetchProductsAndCategories } from "./products.js";
import { order } from "./order.js";
import { renderSummary } from "./summary.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { closeModal, openModal } from "../general/modals_forms.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";
import { getSessionInfo } from "../general/session.js";
import { lastReadCardId, newCardReadPromise, renderCard, removeReadCard, cancelCardReadPromise, handleCardRead } from "./cards.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { phoneInputClickListeners, phoneInputFocusinisteners, phoneInputInputisteners, phoneInputKeydownListeners } from "./phone_number_input.js";
import { handleRowSelection, unselectRows } from "../general/table_utils.js";
import { clearFormErrors, editUserFormOnChange, editWalletInputListeners, fetchUsers, openDeleteUserModal, openMoreUserOptionsModal, openUserCardModal, openUserCardsModal, renderUsers, resetUsersCache, selectedUserForUpdate, selectUserForUpdate, setOrder, showDeleteUserFormErrors, showEditWalletFormErrors, showMoneyToExchangeModal, showUserFormErrors, unselectUserForUpdate } from "./users.js";
import { getWalletByTag, fetchWallets, resetWalletsCache } from "./wallets.js";
import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { setUpCardReading } from "../general/card_reader.js";

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
  const sessionInfo = await getSessionInfo().catch(() => { });

  if (!sessionInfo) {
    return;
  }

  if (sessionInfo.booth) {
    pageContainer.setAttribute('show', sessionInfo.booth.booth_type === 'seller' ? 'seller' : 'cashier');
    await Promise.all([
      setUpCardReading(handleCardRead, false),
      editUserFormOnChange(),
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

  const numberSelector = event.target.closest('.number-selector');
  if (!numberSelector) {
    const productContainer = event.target.closest('.product-container');
    if (productContainer) {
      const plusButton = productContainer.querySelector('.plus-button');
      const productId = plusButton.dataset.productId;
      order.updateQuantity(productId, 1);
      loadPage({
        products: true,
        cardInfo: true,
        summary: true
      });
      return;
    }
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

  if (event.target.matches('#pay-error')) {
    clearPayError();
    return;
  }

  const payButton = event.target.closest('#pay-button');
  if (payButton) {
    payButton.disabled = true;
    setUpCardReading(handleCardRead, true);
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

    const result = await fetchProductsAndCategories().catch(() => {
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

    const idempotencyKey = crypto.randomUUID();

    const formData = new FormData();
    formData.set('tag-id', lastReadCardId);
    // formData.set('transaction-type', 'payment');
    formData.set('products-info', JSON.stringify(productsInfo));
    formData.set('amount-czk', amount_czk);
    formData.set('idempotency-key', idempotencyKey);

    const headers = new Headers();
    headers.set('Idempotency-Key', idempotencyKey);

    try {
      const response = await fetch('/api/transactions/make-payment', {
        method: 'POST',
        headers,
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showPayError(data.error || 'unexpected_error');
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
    // updateWalletBalance(lastReadCardId, amount_czk);
    resetWalletsCache();
    removeReadCard();
    await loadPage({
      products: true,
      cardInfo: true,
      summary: true
    });
    return;
  }

  const confirmRefundButton = event.target.closest('#confirm-refund-button');
  if (confirmRefundButton) {
    try {
      confirmRefundButton.disabled = true;

      const idempotencyKey = crypto.randomUUID();

      const formData = new FormData();
      formData.set('tag-id', lastReadCardId);
      formData.set('idempotency-key', idempotencyKey);

      const headers = new Headers();
      headers.set('Idempotency-Key', idempotencyKey);

      const response = await fetch('/api/transactions/make-refund', {
        method: 'POST',
        headers,
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showRefundError(data.error || 'unexpected_error');
        confirmRefundButton.disabled = false;
        return;
      }
    } catch (error) {
      showRefundError('unexpected_error');
      return;
    } finally {
      confirmRefundButton.disabled = false;
    }

    const confirmOverlay = confirmRefundButton.closest('.overlay');
    confirmOverlay?.remove();
    showRefundSuccess();
    resetWalletsCache();
    removeReadCard();
    await loadPage({
      products: true,
      cardInfo: true,
      summary: true
    });
  }

  const refundButton = event.target.closest('#refund-button');
  if (refundButton) {
    openRefundModal();
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
    // try {
    await unselectEventBooth().catch(() => { });
    renderEventPicker();
    // loadPage({
    //   products: true,
    //   summary: true,
    //   categories: true,
    //   cardInfo: true,
    //   users: true,
    //   // sidebar: true,
    //   header: true
    // });
    // }
    // catch {
    //   const errorMessageEl = document.querySelector('.booth-submit-error-message');
    //   errorMessageEl.innerHTML = 'Něco se nepovedlo, zkuste to prosím později.';
    //   errorMessageEl.classList.add('display-block');
    // }
    return;
  }

  if (event.target.matches('#choose-card-reader')) {
    await setUpCardReading(handleCardRead, true);
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
    return;
  }

  if (event.target.matches('#choose-new-booth-button')) {
    if (selectingEvent) {
      return;
    }
    await unselectBooth();
    chooseAndLoadPage();
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

  const toggleUserSearch = event.target.closest('#user-inputs-search-table-toggle');
  if (toggleUserSearch) {
    toggleUserSearch.toggleAttribute('search-users');
    renderUsers();
    return;
  }

  // smazat uživatele
  const deleteUserBtn = event.target.closest('.delete-user');
  if (deleteUserBtn) {
    const row = deleteUserBtn.closest('tr[id]');
    await openDeleteUserModal(row.id);
    return;
  }

  const closeModalBtn = event.target.closest('.close-modal');
  if (closeModalBtn) {
    closeModal();
    return;
  }

  const cancelUserFormBtn = event.target.closest('#cancel-user-form');
  if (cancelUserFormBtn) {
    await unselectUserForUpdate();
    return;
  }

  if (event.target.matches('#open-more-user-options')) {
    const userId = userIdInput.value.trim();
    if (userId) {
      openMoreUserOptionsModal(userId);
      return;
    }
  }

  if (event.target.matches('#open-user-cards-modal')) {
    closeModal();
    const userId = userIdInput.value.trim();
    if (userId) {
      openUserCardsModal(userId);
      return;
    }
  }

  const userWalletLi = event.target.closest('li[tag-id]');
  if (userWalletLi) {
    openUserCardModal(userWalletLi);
    return;
  }

  const backToUserCardsBtn = event.target.closest('#back-to-user-cards');
  if (backToUserCardsBtn) {
    openUserCardsModal(backToUserCardsBtn.getAttribute('user-id'), backToUserCardsBtn.closest('.modal'));
    return;
  }

  const returnCardButton = event.target.closest('#return-card-button');
  if (returnCardButton) {
    event.preventDefault();
    const editWalletForm = returnCardButton.closest('#edit-wallet-form');
    const saveButton = editWalletForm.querySelector('button[type=submit]');
    saveButton.disabled = true;
    returnCardButton.disabled = true;

    clearFormErrors();

    const formData = new FormData(editWalletForm);

    const idempotencyKey = crypto.randomUUID();
    formData.set('idempotency-key', idempotencyKey);

    const headers = new Headers();
    headers.set('Idempotency-Key', idempotencyKey);

    try {
      const response = await fetch('/api/users/wallets/return', {
        method: 'post',
        headers,
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditWalletFormErrors(data.error || 'unexpected_error');
        return;
      }

      closeModal();
      showMoneyToExchangeModal(data.balance_changed_by);

    } catch (err) {
      showEditWalletFormErrors('unexpected_error');
      return;
    } finally {
      saveButton.disabled = false;
      returnCardButton.disabled = false;
    }

    resetWalletsCache();
    if (lastReadCardId === formData.get('tag-id').trim()) {
      editUserFormOnChange();
    }
    return;
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
  const row = event.target.closest('tr[id]');
  if (row) {
    handleRowSelection(event);
    return;
  }

  const interactableEl = event.target.closest('input') || event.target.closest('button');
  if (interactableEl || document.querySelector('.modal')) {
    return;
  }
  // kliknutí na "nic" odvybere řádek
  unselectRows();
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
  if (phoneInputKeydownListeners(event)) return;

  handleRowSelection(event);

  if (event.target.matches('#change-balance-by-input, #edit-wallet-change-balance-by-input') && event.key === '-') {
    event.preventDefault();
    const changeBalanceByInput = event.target;
    let value = Number(changeBalanceByInput.value);
    if (!isNaN(value)) {
      changeBalanceByInput.value = -value;
      changeBalanceByInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return;
  }



  if (event.target.matches('#set-new-balance-input, #edit-wallet-set-new-balance-input') && event.key === '-') {
    event.preventDefault();
    const setNewBalanceInput = event.target;
    let value = Number(setNewBalanceInput.value);
    if (!isNaN(value)) {
      setNewBalanceInput.value = -value;
      setNewBalanceInput.dispatchEvent(new Event('input', { bubbles: true }));
    }
    return;
  }


  if (event.key === 'Enter' && event.target.matches('.productQuantity, .summary-productQuantity')) {
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

  if (event.key === 'Enter') {
    const selectedRows = document.querySelectorAll('tr[selected]');
    if (selectedRows.length === 1) {
      const row = selectedRows[0];
      if (row && usersTableBody.contains(row)) {
        selectUserForUpdate(row.id);
      }
    }
  }

  if (event.key === 'Delete') {
    const selectedRows = document.querySelectorAll('tr[selected]');
    if (selectedRows.length === 1) {
      const row = selectedRows[0];
      if (row && usersTableBody.contains(row)) {
        openDeleteUserModal(row.id);
      }
    }
  }

  if (event.key === 'Escape') {
    const overlay = document.querySelector('.overlay')
    if (overlay) {
      overlay.remove();
      return;
    }
    unselectUserForUpdate();
  }
});

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
    setUpCardReading(handleCardRead, true);
    const formData = new FormData(boothForm);
    const booth_type = await pickBooth(formData);

    if (booth_type === 'seller') {
      pageContainer.setAttribute('show', 'seller');
      loadPage({
        categories: true,
        products: true,
        summary: true,
        cardInfo: true,
        // sidebar: true,
        header: true
      });
    } else if (booth_type === 'cashier') {
      pageContainer.setAttribute('show', 'cashier');
      editUserFormOnChange();
      loadPage({
        cardInfo: true,
        users: true,
        // sidebar: true,
        header: true
      });
    }
    return;
  }


  if (event.target.matches('#user-form')) {
    event.preventDefault();
    const userForm = event.target;
    const saveButton = userForm.querySelector('button[type=submit]');
    saveButton.disabled = true;
    const userJob = saveButton.getAttribute('user-job');
    const cardJob = saveButton.getAttribute('card-job');

    clearFormErrors();

    const formData = new FormData(userForm);
    if (cardJob) formData.set('tag-id', lastReadCardId);


    if (userJob === 'create') {
      try {
        const response = await fetch('/api/users/create', {
          method: 'post',
          body: formData
        });

        await handleUnauthorizedRedirect(response);

        const data = await response.json();

        if (!response.ok) {
          showUserFormErrors(data.error || 'unexpected_error', data.detail);
          saveButton.disabled = false;
          return;
        }

        formData.set('user-id', data.user_id);

      } catch (err) {
        showUserFormErrors('unexpected_error');
        saveButton.disabled = false;
        return;
      }
    } else if (userJob === 'edit') {
      try {
        const response = await fetch('/api/users/edit', {
          method: 'post',
          body: formData
        });

        await handleUnauthorizedRedirect(response);

        const data = await response.json();

        if (!response.ok) {
          showUserFormErrors(data.error || 'unexpected_error', data.detail);
          saveButton.disabled = false;
          return;
        }
      } catch (err) {
        showUserFormErrors('unexpected_error');
        saveButton.disabled = false;
        return;
      }
    }

    if (userJob) {
      resetUsersCache();
      loadPage({ users: true });
    }

    if (cardJob === 'assign') {
      const idempotencyKey = crypto.randomUUID();
      formData.set('idempotency-key', idempotencyKey);

      const headers = new Headers();
      headers.set('Idempotency-Key', idempotencyKey);

      try {
        const response = await fetch('/api/users/wallets/create', {
          method: 'post',
          headers,
          body: formData
        });

        await handleUnauthorizedRedirect(response);

        const data = await response.json();

        if (!response.ok) {
          showUserFormErrors(data.error || 'unexpected_error', data.detail);
          saveButton.disabled = false;
          return;
        }

        showMoneyToExchangeModal(data.balance_changed_by);
      } catch (err) {
        showUserFormErrors('unexpected_error');
        saveButton.disabled = false;
        return;
      }
    } else if (cardJob === 'change-balance') {
      const idempotencyKey = crypto.randomUUID();
      formData.set('idempotency-key', idempotencyKey);

      const headers = new Headers();
      headers.set('Idempotency-Key', idempotencyKey);

      try {
        const response = await fetch('/api/transactions/make-balance-change', {
          method: 'POST',
          headers,
          body: formData
        });

        await handleUnauthorizedRedirect(response);

        const data = await response.json();

        if (!response.ok) {
          showUserFormErrors(data.error || 'unexpected_error', data.detail);
          saveButton.disabled = false;
          return;
        }

        showMoneyToExchangeModal(data.balance_changed_by);
      } catch (err) {
        showUserFormErrors('unexpected_error');
        saveButton.disabled = false;
        return;
      }
    } else if (cardJob === 'return') {
      const idempotencyKey = crypto.randomUUID();
      formData.set('idempotency-key', idempotencyKey);

      const headers = new Headers();
      headers.set('Idempotency-Key', idempotencyKey);

      try {
        const response = await fetch('/api/users/wallets/return', {
          method: 'post',
          headers,
          body: formData
        });

        await handleUnauthorizedRedirect(response);

        const data = await response.json();

        if (!response.ok) {
          showUserFormErrors(data.error || 'unexpected_error', data.detail);
          saveButton.disabled = false;
          return;
        }

        showMoneyToExchangeModal(data.balance_changed_by);
      } catch (err) {
        showUserFormErrors('unexpected_error');
        saveButton.disabled = false;
        return;
      }
    }

    if (cardJob) {
      resetWalletsCache();
    }

    if (userJob || cardJob) {
      unselectUserForUpdate(); // volá i removeReadCard()
      // removeReadCard();

      // figure out what happens if user gets created but there is a problem with wallet

      // make sure stuff like user deletion deletes the wallets too
    }
    saveButton.disabled = false;
    return;
  }

  if (event.target.matches('#delete-user-form')) {
    event.preventDefault();
    const deleteUserForm = event.target;
    const saveButton = deleteUserForm.querySelector('button[type=submit]');
    saveButton.disabled = true;

    clearFormErrors();

    const formData = new FormData(deleteUserForm);

    try {
      const response = await fetch('/api/users/delete', {
        method: 'delete',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showDeleteUserFormErrors(data.error || 'unexpected_error');
        saveButton.disabled = false;
        return;
      }

    } catch (err) {
      showDeleteUserFormErrors('unexpected_error');
      saveButton.disabled = false;
      return;
    }

    closeModal();
    resetUsersCache();
    resetWalletsCache();

    if (selectedUserForUpdate && selectedUserForUpdate.id === formData.get('user-id')) {
      await unselectUserForUpdate();
    }

    loadPage({ users: true });
    saveButton.disabled = false;
    return;
  }

  if (event.target.matches('#edit-wallet-form')) {
    event.preventDefault();
    const editWalletForm = event.target;
    const saveButton = editWalletForm.querySelector('button[type=submit]');
    const returnCardButton = editWalletForm.querySelector('#return-card-button');
    saveButton.disabled = true;
    returnCardButton.disabled = true;

    clearFormErrors();

    const formData = new FormData(editWalletForm);

    const idempotencyKey = crypto.randomUUID();
    formData.set('idempotency-key', idempotencyKey);

    const headers = new Headers();
    headers.set('Idempotency-Key', idempotencyKey);

    try {
      const response = await fetch('/api/transactions/make-balance-change', {
        method: 'post',
        body: formData
      });

      await handleUnauthorizedRedirect(response);

      const data = await response.json();

      if (!response.ok) {
        showEditWalletFormErrors(data.error || 'unexpected_error');
        return;
      }

      closeModal();
      showMoneyToExchangeModal(data.balance_changed_by);
    } catch (err) {
      showEditWalletFormErrors('unexpected_error');
      return;
    } finally {
      saveButton.disabled = false;
      returnCardButton.disabled = false;
    }

    resetWalletsCache();
    if (lastReadCardId === formData.get('tag-id').trim()) {
      editUserFormOnChange();
    }
    return;
  }
});


document.addEventListener('input', (event) => {
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

  editWalletInputListeners(event);
  phoneInputInputisteners(event);
})


document.addEventListener('focusin', (event) => {
  phoneInputFocusinisteners(event);
});


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

if ('serial' in navigator) {
  navigator.serial.addEventListener('connect', (event) => {
    setUpCardReading(handleCardRead, false);
  });
}


async function openRefundModal() {
  setUpCardReading(handleCardRead, true);
  clearPayError();

  if (!lastReadCardId) {
    const existing = document.querySelector('.overlay');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
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
      return;
    }
  }

  let lookupData
  try {
    const lookupResponse = await fetch(
      `/api/transactions/last-refundable?tag-id=${encodeURIComponent(lastReadCardId)}`
    );

    await handleUnauthorizedRedirect(lookupResponse);

    lookupData = await lookupResponse.json();

    if (!lookupResponse.ok) {
      showPayError(lookupData.error || 'unexpected_error');
      return;
    }
  } catch (error) {
    showPayError('unexpected_error');
    return;
  }

  const refundAmount = lookupData.refund_amount;
  const products = lookupData.products_info;

  let productsHTML = '';
  if (products && products.length > 0) {
    productsHTML = products.map(p =>
      `<div class="refund-product-item">
        <span class="refund-item-name">${escapeHTML(p.name)} (${p.quantity}x)</span>
        <span class="refund-item-price">${p.price * p.quantity} Kč</span>
      </div>`
    ).join('');
  }

  const html = `
    <header>
      <h2>Opravdu chcete vrátit poslední platbu?</h2>
    </header>

    <div id="refund-products-list">${productsHTML}</div>
    <div id="refund-confirmation-total">Celkem k vrácení: ${refundAmount} Kč</div>
    <div id="refund-general-error" class="form-error"></div>
    <div class="modal-actions">
      <button id="cancel-refund-button" class="btn btn-ghost close-modal">Zrušit</button>
      <button id="confirm-refund-button" class="btn btn-delete">Vrátit</button>
    </div>
  `;

  openModal(html);
}



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
    case 'invalid_booth_type':
      setErr('Něco se nepovedlo.');
      return;
    case 'missing_tag_id':
      setErr('Chybí ID karty.');
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
    case 'invalid_products_info':
      setErr('Něco se nepovedlo.');
      return;
    case 'missing_idempotency_key':
      setErr('Něco se nepovedlo.');
      return;
    case 'idempotency_key_data_conflict':
      setErr('Něco se nepovedlo.');
      return;
    case 'no_refundable_transaction':
      setErr('Nebyla nalezena platba k vrácení.');
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


function showRefundError(error) {
  const refundError = document.querySelector('#refund-general-error');
  const setErr = (text) => {
    refundError.innerHTML = escapeHTML(String(text));
    refundError.classList.add('show-form-error');
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
    case 'invalid_booth_type':
      setErr('Něco se nepovedlo.');
      return;
    case 'missing_tag_id':
      setErr('Chybí ID karty.');
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
    case 'invalid_products_info':
      setErr('Něco se nepovedlo.');
      return;
    case 'missing_idempotency_key':
      setErr('Něco se nepovedlo.');
      return;
    case 'idempotency_key_data_conflict':
      setErr('Něco se nepovedlo.');
      return;
    case 'no_refundable_transaction':
      setErr('Nebyla nalezena platba k vrácení.');
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


function showRefundSuccess() {
  const existing = document.querySelector('.overlay');
  if (existing) existing.remove();

  const overlay = document.createElement('div');
  overlay.className = 'overlay';

  overlay.innerHTML = `
    <div id="successful-refund-modal">
      <img id="successful-payment-icon" src="/static/images/icons/checkmark_icon.png">
      <div id="successful-refund-message">Platba byla vrácena.</div>
    </div>
  `;

  pageContainer.appendChild(overlay);

  setTimeout(() => {
    if (overlay) overlay.remove();
  }, 2000);
}
