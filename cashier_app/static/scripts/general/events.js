/**
 * @file Načítání a správa dat akcí a jejich identifikace z URL.
 */
import { handleUnauthorizedRedirect } from "./api_utils.js";
import { cacheFunctionFactory } from "./cache_factory.js";
import { EventNotFoundError, ForbiddenError, MissingEventIdError, UnexpectedError } from "./errors.js";


/**
 * Načte seznam akcí z API a uloží jej do cache.
 * @returns {Promise<Array>} Pole akcí.
 * @throws {UnexpectedError} Při chybě načítání.
 */
export const [fetchEvents, resetEventsCache] = cacheFunctionFactory(async () => {
  const response = await fetch('/api/events');

  await handleUnauthorizedRedirect(response);

  const data = await response.json();

  if (!response.ok) {
    throw UnexpectedError();
  }

  return data.events;

});


/**
 * Získá ID akce z aktuální URL cesty.
 * @returns {string|null} ID akce nebo null, pokud není nalezeno.
 */
export function getEventIdFromPath() {
  // filter(Boolean) odstraňuje falsy hodnoty jako ""
  const parts = window.location.pathname.split('/').filter(Boolean);
  // mělo by být ['events','<id>','manager']
  if (parts[0] === 'events' && parts.length >= 2) {
    return parts[1];
  }
  return null;
}


const eventId = getEventIdFromPath();


/**
 * Načte detailní data o akci podle ID z URL a uloží do cache.
 * @returns {Promise<object>} Objekt s daty akce, stánků, zaměstnanců, produktů, kategorií, uživatelů a peněženek.
 * @throws {MissingEventIdError|ForbiddenError|EventNotFoundError|UnexpectedError}
 */
export const [fetchEventData, resetEventDataCache] = cacheFunctionFactory(async () => {
  if (!eventId) {
    throw new MissingEventIdError();
  }

  const res = await fetch(`/api/events/${encodeURIComponent(eventId)}`);

  await handleUnauthorizedRedirect(res);

  if (res.status === 403) {
    throw new ForbiddenError();
  }

  const resData = await res.json();

  if (res.status === 404 && resData.error === 'event_not_found') {
    window.location.href = resData.redirect_url;
    throw new EventNotFoundError();
  }

  if (!res.ok) {
    throw new UnexpectedError();
  }

  const data = {
    event: resData.event,
    booths: resData.booths,
    employees: resData.employees,
    products: resData.products,
    categories: resData.categories,
    users: resData.users,
    wallets: resData.wallets
  };

  data.employees.forEach((emp) => {
    emp.isManager = !emp.booths.length;
  });

  return data;
});