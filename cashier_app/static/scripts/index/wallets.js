import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { cloneData } from "../general/cache.js";
import { cacheFunctionFactory } from "../general/cache_factory.js";
import { EventNotSelectedError, UnexpectedError } from "../general/errors.js";


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
