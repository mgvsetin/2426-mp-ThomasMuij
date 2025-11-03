import { getSessionInfo } from "./session.js";

const sessionInfoEl = document.querySelector('#session-info');


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
  searchBar.value = new URL(window.location).searchParams.get('search_query') || '';
  await renderDropdownSessionInfo();
}