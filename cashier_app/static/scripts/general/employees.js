export async function getEmployees() {
  try {
    const response = await fetch('/api/employees');

    if (response.status === 401) {
      const json = await response.json();
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

    return data.employees;

  } catch (error) {
    if (error.message === 'insufficient_priviliges') {
      return 'insufficient_priviliges';
    }
    return 'unexpected_error';
  }
}