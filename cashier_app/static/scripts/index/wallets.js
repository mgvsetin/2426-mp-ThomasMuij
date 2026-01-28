import { cloneData } from "../general/cache.js";
import { EventNotSelectedError, UnauthorizedRedirectError, UnexpectedError } from "../general/errors.js";

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
        throw new UnauthorizedRedirectError(json.redirect_url);
      }

      const resData = await response.json();

      if (response.status === 400 && resData.error === 'no_selected_event') {
        throw new EventNotSelectedError();
      }

      if (!response.ok) {
        throw new UnexpectedError();
      }

      _walletsCache.wallets = resData.wallets;
      _walletsCache.expiry = Date.now() + cache_time_ms;

      return cloneData(_walletsCache.wallets);

    } finally {
      _getWalletsPromise = null;
    }
  })();

  return _getWalletsPromise;
}


export function resetWalletsCache() {
  _walletsCache.wallets = null;
  _walletsCache.expiry = 0;
  getWallets()
}


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
