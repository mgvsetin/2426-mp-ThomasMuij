import { cloneData } from "../general/cache.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { order } from "./order.js";
import { getProductsAndCategories } from "./products.js";

const tagIdDisplay = document.querySelector('#tag-id');
const balanceDisplay = document.querySelector('#balance');
const balanceAfterPurchaseDisplay = document.querySelector('#balance-after-purchase');
let cardReaderIsBeingRead = false;
export let lastReadCardId = '';
let newCardReadResolve = null;

let readerInfo;


async function getReaderInfo() {
  if (readerInfo) return readerInfo;
  try {
    const response = await fetch('/api/reader/info');

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

    const resData = await response.json();

    readerInfo = resData.reader_info;
    return readerInfo;
  } catch (error) {

  }
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
      const readerInfo = await getReaderInfo();
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

  renderCard();

  if (newCardReadResolve) {
    newCardReadResolve(cardId);
  }
}


export async function renderCard() {
  const wallets = await getWallets();
  const wallet = wallets ? getWalletByTag(wallets, lastReadCardId) : null;

  const orderPrice = order.getTotalPrice((await getProductsAndCategories()).products);

  const balanceCzk = wallet ? `${escapeHTML(wallet.balance_czk)} Kč` : '-';
  const balanceAfterPurchase = wallet ? `${escapeHTML(wallet.balance_czk - orderPrice)} Kč` : '-';

  tagIdDisplay.innerHTML = `Karta: ${escapeHTML(lastReadCardId) || '-'}`;
  balanceDisplay.innerHTML = `Zůstatek: ${balanceCzk}`;
  balanceAfterPurchaseDisplay.innerHTML = `Zůstatek po platbě: ${balanceAfterPurchase}`;
}


export let newCardReadPromise = new Promise(resolve => {
  newCardReadResolve = resolve;
});


export async function removeReadCard() {
  lastReadCardId = '';
  newCardReadPromise = new Promise(resolve => {
    newCardReadResolve = resolve;
  });
}


export async function cancelCardReadPromise() {
  if (newCardReadResolve) {
    newCardReadResolve(null);
  }
  removeReadCard()
}


const cache_time_ms = 30 * 1000; // 30 sekund
// maybe figure out cache max time so that the slow doenst have to happen

const _walletsCache = {
  wallets: null,
  expiry: 0
};

let _getWalletsPromise = null;

export function getWallets() {
  if (_walletsCache.wallets && _walletsCache.expiry > Date.now()) {
    return Promise.resolve(cloneData(_walletsCache.wallets));
  }

  if (_getWalletsPromise) return _getWalletsPromise;

  _getWalletsPromise = (async () => {
    try {
      const response = await fetch('/api/events/wallets');

      if (response.status === 401) {
        const json = await response.json();
        window.location.href = json.redirect_url;
        return false;
      }

      const resData = await response.json();

      if (response.status === 400 && resData.error === 'no_selected_event') {
        return 'event_not_selected';
      }

      if (!response.ok) {
        throw new Error('unexpected_error')
      }

      _walletsCache.wallets = resData.wallets;
      _walletsCache.expiry = Date.now() + cache_time_ms;

      return cloneData(_walletsCache.wallets);

    } catch (error) {
      return 'unexpected_error';
    } finally {
      _getWalletsPromise = null;
    }
  })();

  return _getWalletsPromise;
}


export function resetWalletsCache() {
  _walletsCache.wallets = null;
  _walletsCache.expiry = 0;
}


export function getWalletByTag(wallets, tagId) {
  for (const wallet of wallets) {
    if (wallet.tag_id === tagId) {
      return wallet;
    }
  }
}


export function updateWalletBalance(tagId, amountCzk) {
  const wallet = getWalletByTag(_walletsCache.wallets, tagId);
  wallet.balance_czk += amountCzk;
}