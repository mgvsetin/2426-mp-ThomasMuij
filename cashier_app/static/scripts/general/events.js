const cache_time_ms = 60 * 1000; // 1 minuta
// maybe figure out cache max time so that the slow doenst have to happen

const _eventsCache = {
  events: null,
  expiry: 0
};


export function resetEventsCache() {
  _eventsCache.events = null;
  _eventsCache.expiry = 0;
}


export async function getEvents() {
  if (_eventsCache.events && _eventsCache.expiry > Date.now()) {
    return _eventsCache.events;
  }

  try {
    const response = await fetch('/api/events');

    if (response.status === 401) {
      const json = await response.json();
      window.location.href = json.redirect_url;
      return;
    }

    const data = await response.json();

    if (!response.ok) {
      throw new Error('unexpected_error');
    }

    _eventsCache.events = data.events;
    _eventsCache.expiry = Date.now() + cache_time_ms;

    return data.events;

  } catch (error) {
    return 'unexpected_error';
  }
}