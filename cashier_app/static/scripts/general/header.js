import { getSessionInfo } from "./session.js";

const header = document.querySelector('#header');
const searchBar = header.querySelector('#search-bar')
const accountDropdown = header.querySelector('#account-dropdown')
const sessionInfoEl = accountDropdown.querySelector('#session-info')


export async function renderDropdownSessionInfo() {
  const sessionInfo = await getSessionInfo();;

  if (!sessionInfo) {
    return;
  }

  let sessionInfoHTML = '';

  try { sessionInfoHTML += `<div id="username">${sessionInfo.employee.username}</div>`; } catch { }
  try { sessionInfoHTML += `<div id="event">${sessionInfo.event.name}</div>`; } catch { }
  try { sessionInfoHTML += `<div id="booth">${sessionInfo.booth.name}</div>`; } catch { }

  sessionInfoEl.innerHTML = sessionInfoHTML;
}


export async function renderHeader() {
  // make the change event only appear sometimes
  if (!searchBar.value) {
    searchBar.value = new URL(window.location).searchParams.get('search_query') || '';
  }
  await renderDropdownSessionInfo();
}


function addSearchParam() {
  const searchQuery = searchBar.value.toLowerCase().trim();
  const url = new URL(window.location);
  const currentQuery = url.searchParams.get('search_query') || '';

  if (searchQuery === currentQuery) {
    return;
  }

  if (!searchQuery) {
    url.searchParams.delete('search_query');
    window.location.href = url;
    return;
  }

  url.searchParams.set('search_query', searchQuery);
  window.location.href = url;
}


export function headerClickListeners(event) {
  if (!(event.target.matches('#account-button, #account-icon')
    || (event.target.closest('#account-dropdown') && !event.target.closest('button, a')))) {
    // kliknutí jinam než na dropdown nebo ikonu uživatele
    // nebo na <button>/<a> v něm
    accountDropdown.removeAttribute('opened');
  }

  if (event.target.matches('#logout-link')) {
    // musí se zavolat před await
    // jestli bude potřeba await tak se prní
    // musí zavolat preventDefault()
    order.reset();
    saveSelectedCategory(null);
    // sessionStorage.clear();
    return true;
  }

  if (event.target.matches('#open-sidebar-button, #open-sidebar-icon')) {
    sidebar.setAttribute('opened', '');
    return true;
  }

  const searchButton = event.target.closest('#search-button');
  if (searchButton && header.contains(searchButton)) {
    addSearchParam();
    return true;
  }

  if (event.target.matches('#account-button, #account-icon')) {
    accountDropdown.toggleAttribute('opened');
    return true;
  }

  return false;
}


export function headerKeydownListeners(event) {
  if (event.code === 'Enter' && event.target.matches('#search-bar')) {
    addSearchParam();
    return true;
  }

  return false;
}