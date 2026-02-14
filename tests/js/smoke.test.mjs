// Quick smoke test to verify Jest + ESM imports from source work
import { jest } from '@jest/globals';
import { mod, isUUID } from '../../cashier_app/static/scripts/general/utils.js';

test('jest ESM import works', () => {
  expect(mod(5, 3)).toBe(2);
  expect(isUUID('550e8400-e29b-41d4-a716-446655440000')).toBe(true);
});
