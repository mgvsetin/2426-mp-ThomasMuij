import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { cacheFunctionFactory } from "../general/cache_factory.js";
import { EventNotSelectedError, UnexpectedError } from "../general/errors.js";


/**
 * Načte peněženky pro aktuální událost s využitím cache.
 * Pokud není vybrána událost, vyhodí EventNotSelectedError.
 * Pokud dojde k neočekávané chybě, vyhodí UnexpectedError.
 * @function
 * @returns {Promise<Array>} Pole objektů peněženek
 * @throws {EventNotSelectedError} Pokud není vybrána událost
 * @throws {UnexpectedError} Při jiné chybě požadavku
 */
/**
 * Resetuje cache pro peněženky.
 * @function
 */
export const [fetchWallets, resetWalletsCache] = cacheFunctionFactory(async () => {
  const response = await fetch('/api/events/wallets');

  await handleUnauthorizedRedirect(response);

  const resData = await response.json();

  if (response.status === 400 && resData.error === 'no_selected_event') {
    throw new EventNotSelectedError();
  }

  if (!response.ok) {
    throw new UnexpectedError();
  }

  return resData.wallets;
}, 1000 * 60 /*1 min*/, 1000 * 60 / 2 /*30 s*/);


/**
 * Najde peněženku podle tagu v poli peněženek.
 * @param {Array} wallets - Pole peněženek
 * @param {string|number} tagId - ID tagu hledané peněženky
 * @returns {Object|null} Nalezená peněženka nebo null, pokud nebyla nalezena
 */
export function getWalletByTag(wallets, tagId) {
  if (!tagId || !wallets) {
    return null;
  }

  for (const wallet of wallets) {
    if (wallet.tag_id === tagId) {
      return wallet;
    }
  }

  return null;
}
