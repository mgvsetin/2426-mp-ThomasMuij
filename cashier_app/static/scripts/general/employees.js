import { handleUnauthorizedRedirect } from "./api_utils.js";
import { cacheFunctionFactory } from "./cache_factory.js";
import { ForbiddenError, UnexpectedError } from "./errors.js";


export const [fetchEmployees, resetEmployeesCache] = cacheFunctionFactory(async () => {
  const response = await fetch('/api/employees');

  await handleUnauthorizedRedirect(response);

  const data = await response.json();

  if (response.status === 403 && data.error === 'admin_or_manager_required') {
    throw new ForbiddenError();
  }

  if (data.error === 'no_data_to_copy') {
    // display
    return;
  }

  if (!response.ok) {
    throw new UnexpectedError();
  }

  return data.employees;
});
