import { UnexpectedError } from "../general/errors.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { order } from "./order.js";
import { getProductsAndCategories } from "./products.js";
import { editUserFormOnChange } from "./users.js";
import { getWalletByTag, getWallets } from "./wallets.js";

const tagIdDisplay = document.querySelector('#tag-id');
const balanceDisplay = document.querySelector('#balance');
const balanceAfterPurchaseDisplay = document.querySelector('#balance-after-purchase');

const cashierTagIdDisplay = document.querySelector('#cashier-tag-id');
const cashierBalanceDisplay = document.querySelector('#cashier-balance');

const changeBalanceByInput = document.querySelector('#change-balance-by-input');
const setNewBalanceInput = document.querySelector('#set-new-balance-input');

let cardReaderIsBeingRead = false;
export let lastReadCardId = '';
let newCardReadResolve = null;

let readerInfo;


export let newCardReadPromise = new Promise(resolve => {
  newCardReadResolve = resolve;
});

handleCardRead('newcard');

async function getReaderInfo() {
  if (readerInfo) return readerInfo;
  const response = await fetch('/api/reader/info');

  if (!response.ok) {
    throw new UnexpectedError();
  }

  const resData = await response.json();

  readerInfo = resData.reader_info;
  return readerInfo;
}


export async function setUpCardReading(calledFromInteraction = false) {
  if (cardReaderIsBeingRead) return;
  cardReaderIsBeingRead = true;
  let cardReaderPort;

  const modal = document.querySelector('#select-reader-modal');
  if (modal) modal.remove();

  try {
    // porty, které uživatel povolil pomocí navigator.serial.requestPort()
    const pairedPorts = await navigator.serial.getPorts();

    if (pairedPorts.length === 1) {
      cardReaderPort = pairedPorts[0];
    } else if (calledFromInteraction) {
      // může se zavolat jen při interakci se stránku (např. kliknutí na tlačítko)
      cardReaderPort = await navigator.serial.requestPort();
    } else {
      const modal = document.createElement('div')
      modal.id = 'select-reader-modal';
      modal.innerHTML = `
        <button id="close-choosing-reader">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
        <button id='choose-card-reader'>Vybrat čtečku</button>
      `;

      document.body.appendChild(modal);

      cardReaderIsBeingRead = false;
      return;
    }
  } catch (error) {
    console.warn('Error pairing port:', error);
    cardReaderIsBeingRead = false;
    return;
  }

  try {
    if (!cardReaderPort.readable) {
      const readerInfo = await getReaderInfo().catch(() => { });
      if (!readerInfo) {
        cardReaderIsBeingRead = false;
        console.warn('Unable to get reader information.')
        return;
      }
      await cardReaderPort.open(readerInfo.serial_port_options);
      // await cardReaderPort.open({
      //   baudRate: 9600, 
      //   dataBits: 8,
      //   stopBits: 1,
      //   parity: 'none',
      //   flowControl: 'none'
      // }); // get from app config (check reader docs for it)
      // docs for this reader say: Rychlost 9600 Bd, 8 bitů, 1 stop bit, parita žádná, řízení přenosu žádné
    }
  } catch (error) {
    console.warn('Error opening port:', error);
    cardReaderIsBeingRead = false;
    return;
  }

  const textDecoder = new TextDecoderStream();
  const readableStreamClosed = cardReaderPort.readable.pipeTo(textDecoder.writable);
  const reader = textDecoder.readable.getReader();

  let timeoutId;

  try {
    let cardId = '';
    while (true) {
      const { value, done } = await reader.read();
      clearTimeout(timeoutId);
      if (done) {
        break;
      }

      cardId += value;

      // konec id karty, nejspíš \n nebo \r
      if (cardId.includes('\n') || cardId.includes('\r')) {
        handleCardRead(cardId);
        cardId = '';
      } else {
        // nebo dost dlouho od posdledního přečtení (100ms)
        timeoutId = setTimeout(() => {
          handleCardRead(cardId);
          cardId = '';
        }, 100);
      }
    }
  } catch (error) {
    console.warn('Read error:', error);
  } finally {
    clearTimeout(timeoutId);
    reader.releaseLock();
    await readableStreamClosed.catch(() => { });
    cardReaderIsBeingRead = false;
  }
}


async function handleCardRead(cardId) {
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
    const wallets = await getWallets().catch(() => { });
    wallet = wallets ? getWalletByTag(wallets, lastReadCardId) : null;
  }

  const result = await getProductsAndCategories().catch(() => { });
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
    changeBalanceByInput.value = wallet ? 0 : '';
    setNewBalanceInput.value = wallet ? wallet.balance_czk : '';
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
