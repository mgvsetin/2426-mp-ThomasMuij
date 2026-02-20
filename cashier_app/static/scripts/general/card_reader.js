/**
 * @file Komunikace s kartovou čtečkou přes Web Serial API.
 */
import { UnexpectedError } from "../general/errors.js";

let readerInfo;
let cardReaderIsBeingRead = false;



/**
 * Načte a uloží informace o kartové čtečce z backendu.
 * Vrací objekt s možnostmi sériového portu a filtry.
 * Vyvolá výjimku UnexpectedError při chybě načítání nebo neplatných datech.
 * @returns {Promise<object>} Objekt s informacemi o čtečce (možnosti portu, filtry).
 * @throws {UnexpectedError} Pokud selže načtení nebo jsou data neplatná.
 */
async function getReaderInfo() {
  if (readerInfo) return readerInfo;
  const response = await fetch('/api/reader/info');

  if (!response.ok) {
    throw new UnexpectedError();
  }

  const resData = await response.json();

  readerInfo = resData.reader_info;
  if (!readerInfo
    || !readerInfo.serial_port_options) {
    console.warn('Nepodařilo se získat informace o čtečce');
    throw new UnexpectedError();
  }

  return readerInfo;
}



/**
 * Požádá uživatele o výběr sériového portu pro kartovou čtečku.
 * Pokud je voláno z uživatelské interakce, použije filtry z backendu.
 * @param {boolean} [calledFromInteraction=false] - True, pokud je voláno z uživatelské akce (např. kliknutí).
 * @returns {Promise<SerialPort|null|undefined>} Vybraný SerialPort, nebo null/undefined pokud není dostupný.
 */
export async function requestPortFromUser(calledFromInteraction = false) {
  if (!('serial' in navigator)) return;

  if (calledFromInteraction) {
    const readerInfo = await getReaderInfo().catch(() => { });
    if (readerInfo
      && readerInfo.filters
      && readerInfo.filters.length > 0) {
      // [{
      //   usbVendorId: 'An unsigned short integer that identifies a USB device vendor. The USB Implementors Forum assigns IDs to specific vendors.',
      //   usbProductId (optional): 'An unsigned short integer that identifies a USB device. Each vendor assigns IDs to its products.'
      // }, {...]
      return await navigator.serial.requestPort({ filters: readerInfo.filters });
    }
    // může se zavolat jen při interakci se stránkou (např. kliknutí na tlačítko)
    return await navigator.serial.requestPort();
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
    return null;
  }
}


/**
 * Získá SerialPort pro kartovou čtečku – buď z již spárovaných portů, nebo vyzve uživatele k výběru.
 * @param {boolean} calledFromInteraction - True, pokud je voláno z uživatelské akce.
 * @param {number|undefined} [portIdx] - Volitelný index portu k výběru.
 * @returns {Promise<SerialPort|null>} Vybraný SerialPort, nebo null pokud není nalezen.
 */
async function getCardReaderPort(calledFromInteraction, portIdx = undefined) {
  try {
    // porty, které uživatel povolil pomocí navigator.serial.requestPort()
    const pairedPorts = await navigator.serial.getPorts();

    if (Number.isInteger(portIdx)) {
      if (portIdx < 0 || portIdx >= pairedPorts.length) {
        console.warn('Chyba párování portu: pokus o otevření portu s příliš vysokým indexem (nedostatek spárovaných portů)');
        return null;
      }
      return pairedPorts[portIdx];
    }
    if (pairedPorts.length === 1) {
      return pairedPorts[0];
    } else {
      return await requestPortFromUser(calledFromInteraction);
    }
  } catch (error) {
    console.warn('Chyba párování portu:', error);
    return null;
  }
}


/**
 * Otevře zadaný SerialPort, pokud ještě není otevřený.
 * @param {SerialPort} port - Sériový port k otevření.
 * @returns {Promise<boolean>} True pokud je port otevřený nebo byl úspěšně otevřen, jinak false.
 */
async function openPortIfNecessary(port) {
  try {
    if (!port.readable) { // port není otevřen
      const readerInfo = await getReaderInfo().catch(() => { });
      if (!readerInfo || !readerInfo.serial_port_options) return false;
      await port.open(readerInfo.serial_port_options);
      return true;
      // await cardReaderPort.open({
      //   baudRate: 9600, 
      //   dataBits: 8,
      //   stopBits: 1,
      //   parity: 'none',
      //   flowControl: 'none'
      // }); // get from app config (check reader docs for it)
      // docs for this reader say: Rychlost 9600 Bd, 8 bitů, 1 stop bit, parita žádná, řízení přenosu žádné
    }
    return true; // již je otevřen
  } catch (error) {
    console.warn('Chyba otevírání portu:', error);
    return false;
  }
}



/**
 * Vytvoří čtečku textového proudu ze SerialPortu.
 * @param {SerialPort} port - Sériový port pro čtení.
 * @returns {[ReadableStreamDefaultReader<string>, Promise<void>]} Čtečka a promise pro uzavření proudu.
 */
function getStringStreamReader(port) {
  const textDecoder = new TextDecoderStream();
  const readableStreamClosed = port.readable.pipeTo(textDecoder.writable);
  return [textDecoder.readable.getReader(), readableStreamClosed];
}


/**
 * Čte ID karet z textového proudu a volá callback při načtení karty.
 * @param {ReadableStreamDefaultReader<string>} reader - Čtečka proudu.
 * @param {Promise<void>} readableStreamClosed - Promise pro uzavření proudu.
 * @param {(cardId: string) => void} onCardRead - Callback při načtení ID karty.
 * @returns {Promise<void>}
 */
async function readStringStreamReader(reader, readableStreamClosed, onCardRead) {
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
        onCardRead(cardId);
        cardId = '';
      } else {
        // nebo dost dlouho od posdledního přečtení (100ms)
        timeoutId = setTimeout(() => {
          onCardRead(cardId);
          cardId = '';
        }, 100);
      }
    }
  } catch (error) {
    console.warn('Chyba čtení:', error);
  } finally {
    clearTimeout(timeoutId);
    reader.releaseLock();
    await readableStreamClosed.catch(() => { });
  }
}


/**
 * Interní nastavení čtení karet: získá port, otevře jej a spustí čtení.
 * @param {(cardId: string) => void} onCardRead - Callback při načtení ID karty.
 * @param {boolean} [calledFromInteraction=false] - True, pokud je voláno z uživatelské akce.
 * @param {number|undefined} [portIdx] - Volitelný index portu k výběru.
 * @returns {Promise<void>}
 */
async function _setUpCardReading(onCardRead, calledFromInteraction = false, portIdx = undefined) {
  document.querySelector('#select-reader-modal')?.remove();

  const cardReaderPort = await getCardReaderPort(calledFromInteraction, portIdx);
  if (!cardReaderPort) return;

  const success = await openPortIfNecessary(cardReaderPort);
  if (!success) return;

  // pošli stream textu v binárním kódování z čtečky do TextDecoderStream
  // čti stream stringů z jeho .readable
  const [reader, readableStreamClosed] = getStringStreamReader(cardReaderPort);

  await readStringStreamReader(reader, readableStreamClosed, onCardRead)
}



/**
 * Nastaví čtení karet: zajistí, že probíhá jen jedno čtení najednou, ověří podporu v prohlížeči a spustí čtení.
 * @param {(cardId: string) => void} onCardRead - Callback při načtení ID karty.
 * @param {boolean} [calledFromInteraction=false] - True, pokud je voláno z uživatelské akce.
 * @param {number|undefined} [portIdx] - Volitelný index portu k výběru.
 * @returns {Promise<void>}
 */
export async function setUpCardReading(onCardRead, calledFromInteraction = false, portIdx = undefined) {
  if (!('serial' in navigator)) {
    // prohlížeč nepodporuje Web Serial API
    console.warn('Prohlížeč nepodporuje Web Serial API.');
    return;
  }
  if (cardReaderIsBeingRead) return;
  try {
    cardReaderIsBeingRead = true;
    await _setUpCardReading(onCardRead, calledFromInteraction, portIdx);
  } finally {
    cardReaderIsBeingRead = false;
  }
}