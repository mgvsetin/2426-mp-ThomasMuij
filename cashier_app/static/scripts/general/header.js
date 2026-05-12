/**
 * @file Inicializace a vykreslení hlavičky stránky (header) s navigací a účtem.
 */

import { order } from "../index/order.js";
import { saveSelectedCategory } from "../index/products.js";
import { getSessionInfo } from "./session.js";


let header, /*searchBar,*/ accountDropdown, sessionInfoEl, sidebarOverlayPage;


/**
 * Inicializuje hlavičku stránky a vykreslí její HTML strukturu.
 * Přidá hlavičku do DOM, nastaví avatar a barvu podle uživatele.
 */
function initHeader() {
  if (document.getElementById('header')) return;

  const newEventBoothButtonHTML = location.pathname === '/' ? `
    <button id="choose-new-booth-button">
      Změnit stánek
    </button>
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
        <div id="account-icon"></div>
        <!-- <img id="account-icon" src="/static/images/icons/account_icon.png"> -->
      </button>

      <div id="account-dropdown">
        <div id="session-info"></div>
  
        
        <div class="dropdown-actions">
          <a href="/settings">Nastavení</a>
        </div>
        <div class="divider"></div>
        <div class="dropdown-actions">
          ${newEventBoothButtonHTML}
          <a id="logout-link" href="/api/auth/logout" class="logout">Odhlásit</a>
        </div>
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

  setTimeout(async () => {
    const sessionInfo = await getSessionInfo().catch(() => { });

    const displayName = sessionInfo?.employee?.username || "-";
    const avatarEl = document.getElementById('account-icon');
    avatarEl.textContent = displayName[0];
    avatarEl.style.backgroundColor = nameToColor(displayName);
  }, 0)

  // searchBar.value = new URL(window.location).searchParams.get('search_query') || '';
}


/**
 * Vypočítá barvu na základě jména (pro avatar).
 * @param {string} name - Jméno uživatele.
 * @returns {string} Barva v HSL formátu.
 */
function nameToColor(name) {
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash) % 360;

  return `hsl(${hue} 60% 45%)`;
}


// if (document.readyState === 'loading') {
//   document.addEventListener('DOMContentLoaded', initHeader, { once: true });
// } else {
//   initHeader();
// }

initHeader();


/**
 * Vykreslí informace o aktuálním uživateli do dropdownu v hlavičce.
 * @returns {Promise<void>}
 */
async function renderDropdownSessionInfo() {
  if (!sessionInfoEl) initHeader();

  const sessionInfo = await getSessionInfo().catch(() => { });

  if (!sessionInfo) return;

  let sessionInfoHTML = '';

  if (sessionInfo.employee) {
    sessionInfoHTML += `<div id="username">${sessionInfo.employee.username}</div>`;
  }

  if (sessionInfo.event && !sessionInfo.booth) {
    sessionInfoHTML += `<div id="event-booth">${sessionInfo.event.name}</div>`;
  } else if (sessionInfo.event && sessionInfo.booth) {
    sessionInfoHTML += `<div id="event-booth">${sessionInfo.event.name} - ${sessionInfo.booth.name}</div>`;
  }

  sessionInfoEl.innerHTML = sessionInfoHTML;
}


/**
 * Vykreslí hlavičku a informace o uživateli (dropdown).
 * @returns {Promise<void>}
 */
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


/**
 * Zpracuje kliknutí v hlavičce (dropdown, odhlášení, otevření sidebaru).
 * @param {Event} event - Událost kliknutí.
 * @returns {boolean|undefined} True pokud byla akce zpracována, jinak false/undefined.
 */
export function headerClickListeners(event) {
  if (!header) initHeader();

  if (!(event.target.closest('#account-button')
    || (event.target.closest('#account-dropdown') && !event.target.closest('button, a')))) {
    // kliknutí jinam než na dropdown nebo ikonu uživatele
    // nebo na <button>/<a> v něm
    accountDropdown.removeAttribute('opened');
  }

  if (event.target.matches('#logout-link')) {
    // musí se zavolat před await
    // jestli bude potřeba await tak se prní
    // musí zavolat preventDefault()
    // event.preventDefault(); /////
    order.reset();
    saveSelectedCategory(null);
    localStorage.removeItem('copied');
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

  if (event.target.closest('#account-button')) {
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