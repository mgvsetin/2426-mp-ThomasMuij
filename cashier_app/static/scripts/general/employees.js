import { cloneData } from "./cache.js";

const cache_time_ms = 60 * 1000; // 1 minuta
// maybe figure out cache max time so that the slow doenst have to happen

const _employeesCache = {
  employees: null,
  expiry: 0
};

let _getEmployeesPromise = null;


export function resetEmployeesCache() {
  _employeesCache.employees = null;
  _employeesCache.expiry = 0;
}


export function getEmployees() {
  if (_employeesCache.employees && _employeesCache.expiry > Date.now()) {
    return Promise.resolve(cloneData(_employeesCache.employees));
  }

  if (_getEmployeesPromise) return _getEmployeesPromise;

  _getEmployeesPromise = (async () => {
    try {
      const response = await fetch('/api/employees');

      if (response.status === 401) {
        const json = await response.json();
        _getEmployeesPromise = null;
        window.location.href = json.redirect_url;
        return;
      }

      const data = await response.json();

      if (response.status === 403 && data.error === 'admin_or_manager_required') {
        throw new Error('insufficient_priviliges');
      }

      if (!response.ok) {
        throw new Error('unexpected_error');
      }

      _employeesCache.employees = data.employees;
      _employeesCache.expiry = Date.now() + cache_time_ms;

      return cloneData(data.employees);

    } catch (error) {
      if (error.message === 'insufficient_priviliges') {
        return 'insufficient_priviliges';
      }
      return 'unexpected_error';
    } finally {
      _getEmployeesPromise = null;
    }
  })();

  return _getEmployeesPromise;
}