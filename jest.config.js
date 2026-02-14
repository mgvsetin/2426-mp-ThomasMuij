/** @type {import('jest').Config} */
export default {
  testEnvironment: 'jsdom',
  roots: ['<rootDir>/tests/js'],
  testMatch: ['**/*.test.mjs'],
  transform: {},
};
