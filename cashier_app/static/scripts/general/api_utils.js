import { UnauthorizedRedirectError } from "./errors.js";

/**
 * Checks if response is a 401 and handles redirect if so.
 * Call this BEFORE calling response.json() for your data.
 * If 401: reads json, redirects, and throws UnauthorizedRedirectError.
 * If not 401: does nothing, allowing you to call response.json() after.
 */
export async function handleUnauthorizedRedirect(response) {
  if (response.status === 401) {
    const json = await response.json();
    window.location.href = json.redirect_url;
    throw new UnauthorizedRedirectError(json.redirect_url);
  }
}
