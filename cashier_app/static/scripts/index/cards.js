import { escapeHTML } from "../general/html_display_utils.js";
import { order } from "./order.js";
import { fetchProductsAndCategories } from "./products.js";
import { editUserFormOnChange } from "./users.js";
import { getWalletByTag, fetchWallets } from "./wallets.js";

const tagIdDisplay = document.querySelector('#tag-id');
const balanceDisplay = document.querySelector('#balance');
const balanceAfterPurchaseDisplay = document.querySelector('#balance-after-purchase');

const cashierTagIdDisplay = document.querySelector('#cashier-tag-id');
const cashierBalanceDisplay = document.querySelector('#cashier-balance');

const changeBalanceByInput = document.querySelector('#change-balance-by-input');
const setNewBalanceInput = document.querySelector('#set-new-balance-input');

export let lastReadCardId = '';
let newCardReadResolve = null;


export let newCardReadPromise = new Promise(resolve => {
  newCardReadResolve = resolve;
});

handleCardRead('newcard'); /////////


export async function handleCardRead(cardId) {
  cardId = cardId.trim();
  if (cardId.length === 0) return;
  lastReadCardId = cardId;

  await Promise.all([
    editUserFormOnChange(),
    // renderCard(wallet)
    renderCard()
  ]);


  if (newCardReadResolve) {
    newCardReadResolve(cardId);
  }
}


export async function renderCard(wallet = null) {
  if (!wallet) {
    const wallets = await fetchWallets().catch(() => { });
    wallet = wallets ? getWalletByTag(wallets, lastReadCardId) : null;
  }

  const result = await fetchProductsAndCategories().catch(() => { });
  let orderPrice;
  if (result) {
    orderPrice = order.getTotalPrice(result.products);
  }

  const balanceCzk = wallet ? `${escapeHTML(wallet.balance_czk)} Kč` : '-';
  const balanceAfterPurchase = wallet && orderPrice ? `${escapeHTML(wallet.balance_czk - orderPrice)} Kč` : '-';

  tagIdDisplay.innerHTML = `Karta: ${escapeHTML(lastReadCardId) || '-'}`;
  balanceDisplay.innerHTML = `Zůstatek: ${balanceCzk}`;
  balanceAfterPurchaseDisplay.innerHTML = `Zůstatek po platbě: ${balanceAfterPurchase}`;

  cashierTagIdDisplay.innerHTML = `ID: ${escapeHTML(lastReadCardId) || '-'}`;
  cashierBalanceDisplay.innerHTML = `Zůstatek: ${balanceCzk}`;

  if (!changeBalanceByInput.value && !setNewBalanceInput.value) {
    changeBalanceByInput.value = lastReadCardId ? 0 : '';
    setNewBalanceInput.value = wallet ? wallet.balance_czk : lastReadCardId ? 0 : '';
  }

  return wallet;
}


export function removeReadCard() {
  lastReadCardId = '';
  editUserFormOnChange();
  newCardReadPromise = new Promise(resolve => {
    newCardReadResolve = resolve;
  });
}


export function cancelCardReadPromise() {
  if (newCardReadResolve) {
    newCardReadResolve(null);
  }
  removeReadCard()
}
