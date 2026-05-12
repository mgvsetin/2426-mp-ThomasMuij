import { handleUnauthorizedRedirect } from '../../cashier_app/static/scripts/general/api_utils.js';
import { UnauthorizedRedirectError } from '../../cashier_app/static/scripts/general/errors.js';

describe('handleUnauthorizedRedirect', () => {

  // Save original and mock window.location
  const originalLocation = window.location;

  beforeEach(() => {
    delete window.location;
    window.location = { href: '' };
  });

  afterEach(() => {
    window.location = originalLocation;
  });

  test('does nothing for non-401 response', async () => {
    const response = {
      status: 200,
      json: async () => ({}),
    };
    // Should not throw
    await handleUnauthorizedRedirect(response);
    expect(window.location.href).toBe('');
  });

  test('redirects on 401 and throws UnauthorizedRedirectError', async () => {
    const redirectUrl = '/auth/login';
    const response = {
      status: 401,
      json: async () => ({ redirect_url: redirectUrl }),
    };

    await expect(handleUnauthorizedRedirect(response)).rejects.toThrow(UnauthorizedRedirectError);
    expect(window.location.href).toBe(redirectUrl);
  });

  test('thrown error contains redirect URL', async () => {
    const redirectUrl = '/auth/login';
    const response = {
      status: 401,
      json: async () => ({ redirect_url: redirectUrl }),
    };

    try {
      await handleUnauthorizedRedirect(response);
    } catch (err) {
      expect(err).toBeInstanceOf(UnauthorizedRedirectError);
      expect(err.redirectUrl).toBe(redirectUrl);
    }
  });

  test('does not redirect for 403', async () => {
    const response = {
      status: 403,
      json: async () => ({ error: 'forbidden' }),
    };
    await handleUnauthorizedRedirect(response);
    expect(window.location.href).toBe('');
  });

  test('does not redirect for 500', async () => {
    const response = {
      status: 500,
      json: async () => ({ error: 'server_error' }),
    };
    await handleUnauthorizedRedirect(response);
    expect(window.location.href).toBe('');
  });
});
