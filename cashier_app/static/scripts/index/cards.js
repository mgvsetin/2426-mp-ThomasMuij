/**
 * @file Zpracování načtené karty a zobrazení zůstatku peněženky.
 */
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

handleCardRead('00B824B800000000'); ///////// 


/**
 * Zpracuje načtení karty podle zadaného ID.
 * Nastaví poslední načtené ID karty, aktualizuje formulář uživatele a vykreslí kartu.
 * Po načtení karty vyřeší promisu newCardReadPromise.
 * @param {string} cardId - ID načtené karty
 * @returns {Promise<void>}
 */
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


/**
 * Vykreslí informace o kartě a zůstatku peněženky do příslušných prvků na stránce.
 * Pokud není peněženka zadána, načte ji podle posledního načteného ID karty.
 * @param {Object|null} wallet - Objekt peněženky nebo null
 * @returns {Promise<Object|null>} Vrací objekt peněženky nebo null
 */
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

  const balanceCzk = wallet ? `<strong>${escapeHTML(wallet.balance_czk)} Kč</strong>` : '-';
  const balanceAfterPurchase = wallet && orderPrice ? `<strong>${escapeHTML(wallet.balance_czk - orderPrice)} Kč</strong>` : '-';

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


/**
 * Odstraní informaci o poslední načtené kartě a resetuje promisu pro načtení nové karty.
 */
export function removeReadCard() {
  lastReadCardId = '';
  editUserFormOnChange();
  newCardReadPromise = new Promise(resolve => {
    newCardReadResolve = resolve;
  });
}


/**
 * Zruší aktuální promisu pro načtení karty a odstraní informaci o načtené kartě.
 */
export function cancelCardReadPromise() {
  if (newCardReadResolve) {
    newCardReadResolve(null);
  }
  removeReadCard()
}
