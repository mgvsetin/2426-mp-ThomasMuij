/**
 * @file Tovární funkce pro vytváření cachovaných asynchronních volání.
 */

import { cloneData } from "./cache.js";


/**
 * Factory function to create a cached async function and a cache resetter.
 *
 * @template T
 * @param {(...args: any[]) => Promise<T>} func - The async function to cache.
 * @param {number} [cacheTimeMs=1000 * 60 * 2] - How long (ms) the cache is valid (default 2 minutes).
 * @param {number} [cacheRefetchMs=1000 * 60] - How soon (ms) to refetch in background (default 1 minute).
 * @returns {[function(noCache?: boolean, ...args: any[]): Promise<T>, function(): void]} Array with [cached function, reset cache function].
 */
export function cacheFunctionFactory(func, cacheTimeMs = 1000 * 60 * 2 /*2 minuty*/, cacheRefetchMs = 1000 * 60 /*1 minuta*/) {
  const cache = {
    data: null,
    fetchTime: 0
  }
  let promiseHolder;

  /**
   * Cached wrapper for the async function.
   * @param {boolean} [noCache=false] - If true, bypasses cache and fetches fresh data.
   * @param {...any} args - Arguments to pass to the original function.
   * @returns {Promise<any>} Promise resolving to the (possibly cached) data.
   */
  const wrapperFunc = (noCache = false, ...args) => {
    if (!noCache && cache.data && cache.fetchTime + cacheTimeMs > Date.now()) {
      if (cache.fetchTime + cacheRefetchMs < Date.now()) {
        // Trigger background refetch, but don't await
        wrapperFunc(true, ...args);
      }
      return Promise.resolve(cloneData(cache.data));
    }

    if (promiseHolder) return promiseHolder;

    promiseHolder = (async () => {
      try {
        cache.data = await func(...args);
        cache.fetchTime = Date.now();

        return cloneData(cache.data);

      } finally {
        promiseHolder = null;
      }
    })();

    return promiseHolder;
  };

  /**
   * Resets the cache and triggers a background fetch.
   */
  const resetCacheFunc = () => {
    cache.data = null;
    cache.fetchTime = 0;
    wrapperFunc().catch(() => { });
  };

  return [wrapperFunc, resetCacheFunc];
}