import { jest } from '@jest/globals';
import { cacheFunctionFactory } from '../../cashier_app/static/scripts/general/cache_factory.js';

describe('cacheFunctionFactory', () => {

  test('returns an array with wrapper and reset functions', () => {
    const [wrapper, reset] = cacheFunctionFactory(async () => 'data');
    expect(typeof wrapper).toBe('function');
    expect(typeof reset).toBe('function');
  });

  test('calls the underlying function and returns data', async () => {
    const fn = jest.fn(async () => ({ value: 42 }));
    const [wrapper] = cacheFunctionFactory(fn, 60000, 30000);

    const result = await wrapper();
    expect(result).toEqual({ value: 42 });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test('returns cached data on second call within cache time', async () => {
    const fn = jest.fn(async () => ({ value: 42 }));
    const [wrapper] = cacheFunctionFactory(fn, 60000, 60000);

    await wrapper();
    const result2 = await wrapper();

    expect(result2).toEqual({ value: 42 });
    expect(fn).toHaveBeenCalledTimes(1); // not called again
  });

  test('returns a clone, not the same reference', async () => {
    const fn = jest.fn(async () => ({ value: 42 }));
    const [wrapper] = cacheFunctionFactory(fn, 60000, 60000);

    const result1 = await wrapper();
    const result2 = await wrapper();

    expect(result1).toEqual(result2);
    expect(result1).not.toBe(result2); // different objects
  });

  test('deduplicates concurrent calls', async () => {
    let resolvePromise;
    const fn = jest.fn(() => new Promise(resolve => { resolvePromise = resolve; }));
    const [wrapper] = cacheFunctionFactory(fn, 60000, 60000);

    const p1 = wrapper(true);
    const p2 = wrapper(true);

    // Both should be the same promise since one is in-flight
    resolvePromise({ value: 1 });

    const [r1, r2] = await Promise.all([p1, p2]);
    expect(r1).toEqual({ value: 1 });
    expect(r2).toEqual({ value: 1 });
    expect(fn).toHaveBeenCalledTimes(1);
  });

  test('noCache=true forces a refetch', async () => {
    const fn = jest.fn(async () => ({ value: Math.random() }));
    const [wrapper] = cacheFunctionFactory(fn, 60000, 60000);

    await wrapper();
    await wrapper(true); // force refetch

    expect(fn).toHaveBeenCalledTimes(2);
  });

  test('reset clears cache and triggers refetch', async () => {
    const fn = jest.fn(async () => ({ value: 'fresh' }));
    const [wrapper, reset] = cacheFunctionFactory(fn, 60000, 60000);

    await wrapper();
    expect(fn).toHaveBeenCalledTimes(1);

    reset(); // should clear cache and call wrapper() internally
    // Wait for the internal refetch to settle
    await new Promise(resolve => setTimeout(resolve, 10));
    expect(fn).toHaveBeenCalledTimes(2);
  });
});
