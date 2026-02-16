/**
 * @file Načítání a cachování seznamu zaměstnanců z API.
 */

import { handleUnauthorizedRedirect } from "./api_utils.js";
import { cacheFunctionFactory } from "./cache_factory.js";
import { ForbiddenError, UnexpectedError } from "./errors.js";


/**
 * Načte seznam zaměstnanců z API a uloží jej do cache.
 * Pokud je uživatel neautorizovaný, přesměruje nebo vyvolá chybu.
 * @returns {Promise<Array>|undefined} Pole zaměstnanců nebo undefined při chybě 'no_data_to_copy'.
 * @throws {ForbiddenError} Pokud je vyžadováno oprávnění admin/manager.
 * @throws {UnexpectedError} Při jiné chybě načítání.
 */
export const [fetchEmployees, resetEmployeesCache] = cacheFunctionFactory(async () => {
  const response = await fetch('/api/employees');

  await handleUnauthorizedRedirect(response);

  const data = await response.json();

  if (response.status === 403 && data.error === 'admin_or_manager_required') {
    throw new ForbiddenError();
  }

  if (data.error === 'no_data_to_copy') {
    // zobrazit
    return;
  }

  if (!response.ok) {
    throw new UnexpectedError();
  }

  return data.employees;
});
