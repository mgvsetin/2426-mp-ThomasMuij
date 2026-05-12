/**
 * @file Pomocné funkce pro práci s API (zpracování odpovědí, přesměrování).
 */

import { UnauthorizedRedirectError } from "./errors.js";

/**
 * Zkontroluje, zda je odpověď 401, a případně provede přesměrování.
 * Volejte PŘED voláním response.json() pro vaše data.
 * Pokud 401: přečte JSON, přesměruje a vyhodí UnauthorizedRedirectError.
 * Pokud ne 401: nic neprovede, takže můžete poté zavolat response.json().
 */
export async function handleUnauthorizedRedirect(response) {
  if (response.status === 401) {
    const json = await response.json();
    window.location.href = json.redirect_url;
    throw new UnauthorizedRedirectError(json.redirect_url);
  }
}
