/**
 * @file Získání informací o aktuální relaci uživatele.
 */
import { UnexpectedError } from "./errors.js";

let alertOpen = false;

/**
 * Načte informace o aktuální relaci uživatele z API.
 * Při překročení limitu požadavků zobrazí upozornění.
 * @returns {Promise<object>} Objekt s informacemi o relaci.
 * @throws {UnexpectedError} Při chybě načítání.
 */
export async function getSessionInfo() {
  const response = await fetch('/api/session');

  if (response.status === 429) {
    if (!alertOpen) {
      alertOpen = true;
      setTimeout(() => {
        window.alert("Odesíláte příliš mnoho požadavků. Zkuste to prosím později.");
        alertOpen = false;
      }, 0);
    }
  }

  if (!response.ok) {
    throw new UnexpectedError();
  }

  const data = await response.json();

  return data
}
