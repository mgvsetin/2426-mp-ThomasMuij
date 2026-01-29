import { cloneData } from "./cache.js";


export function cacheFunctionFactory(func, cacheTimeMs=1000 * 60 * 2 /*2 min*/, cacheRefetchMs=1000 * 60 /*1 min*/) {
  const cache = {
    data: null,
    fetchTime: 0
  }
  let promiseHolder;

  const wrapperFunc = (noCache = false, ...args) => {
    if (!noCache && cache.data && cache.fetchTime + cacheTimeMs > Date.now()) {
      if (cache.fetchTime + cacheRefetchMs < Date.now()) {
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
  }

  const resetCacheFunc = () => {
    cache.data = null;
    cache.fetchTime = 0;
    wrapperFunc();
  }

  return [wrapperFunc, resetCacheFunc]
}