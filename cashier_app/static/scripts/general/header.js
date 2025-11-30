import { getSessionInfo } from "./session.js";


let header, /*searchBar,*/ accountDropdown, sessionInfoEl, sidebarOverlayPage;


function initHeader() {
  if (document.getElementById('header')) return;

  const newEventButtonHTML = location.pathname === '/' ? `
    <button id="choose-new-event-button">
      Změnit akci
    </button>
  ` : '';

  const headerHTML = `
    <div id="header-left">
      <button id="open-sidebar-button">
        <img id="open-sidebar-icon" src="/static/images/icons/sidebar_icon.png">
      </button>
    </div>

    <div id="header-middle">
      <!-- <div id="search-div"> -->
      <!--
        <div id="search-bar-container">
          <input id="search-bar" placeholder="Vyhledávání">
          <button id="search-button">
            <img id="search-icon" src="/static/images/icons/search_icon.png">
          </button>
        </div>
      -->
      <!-- </div> -->
    </div>

    <div id="header-right">
      <button id="account-button">
        <img id="account-icon" src="/static/images/icons/account_icon.png">
      </button>

      <div id="account-dropdown">
        <div id="session-info"></div>
        ${newEventButtonHTML}
        <a id="logout-link" href="/api/auth/logout">
          Odhlásit
        </a>
      </div>
    </div>
  `;

  header = document.createElement('div');
  header.id = 'header';
  header.innerHTML = headerHTML;
  document.body.prepend(header);

  // searchBar = document.querySelector('#search-bar');
  accountDropdown = document.querySelector('#account-dropdown');
  sessionInfoEl = document.querySelector('#session-info');

  // searchBar.value = new URL(window.location).searchParams.get('search_query') || '';
}


// if (document.readyState === 'loading') {
//   document.addEventListener('DOMContentLoaded', initHeader, { once: true });
// } else {
//   initHeader();
// }

initHeader();


async function renderDropdownSessionInfo() {
  if (!sessionInfoEl) initHeader();

  const sessionInfo = await getSessionInfo();

  if (!sessionInfo) return;

  let sessionInfoHTML = '';

  try { sessionInfoHTML += `<div id="username">${sessionInfo.employee.username}</div>`; } catch { }
  try { sessionInfoHTML += `<div id="event">${sessionInfo.event.name}</div>`; } catch { }
  try { sessionInfoHTML += `<div id="booth">${sessionInfo.booth.name}</div>`; } catch { }

  sessionInfoEl.innerHTML = sessionInfoHTML;
}


export async function renderHeader() {
  if (!header) initHeader();
  await renderDropdownSessionInfo();
}


// function addSearchParam() {
//   if (!searchBar) initHeader();

//   const searchQuery = searchBar.value.toLowerCase().trim();
//   const url = new URL(window.location);
//   const currentQuery = url.searchParams.get('search_query') || '';

//   if (searchQuery === currentQuery) {
//     return;
//   }

//   if (!searchQuery) {
//     url.searchParams.delete('search_query');
//     window.location.href = url;
//     return;
//   }

//   url.searchParams.set('search_query', searchQuery);
//   window.location.href = url;
// }


export function headerClickListeners(event) {
  if (!header) initHeader();

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
  
  // sidebar se tvoří přes js, takže ještě nemusí existovat
  if (!sidebarOverlayPage) {
    sidebarOverlayPage = document.querySelector('#sidebar-overlay-page');
  }

  if (sidebarOverlayPage && event.target.matches('#open-sidebar-button, #open-sidebar-icon')) {
    sidebarOverlayPage.setAttribute('opened', '');
    return true;
  }

  // const searchButton = event.target.closest('#search-button');
  // if (searchButton && header.contains(searchButton)) {
  //   addSearchParam();
  //   return true;
  // }

  if (event.target.matches('#account-button, #account-icon')) {
    accountDropdown.toggleAttribute('opened');
    return true;
  }

  return false;
}


// export function headerKeydownListeners(event) {
//   if (!header) initHeader();

//   if (event.code === 'Enter' && event.target.matches('#search-bar')) {
//     addSearchParam();
//     return true;
//   }

//   return false;
// }