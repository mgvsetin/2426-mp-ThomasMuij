export async function getSessionInfo() {
  try {
    const response = await fetch('/api/session/');

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

    const data = await response.json();

    return data

  } catch (error) {
    return false;
  }
}