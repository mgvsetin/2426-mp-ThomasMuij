import { getSessionInfo } from "./session.js";

const sidebar = document.querySelector('#sidebar');


export async function renderSidebar() {
  const sessionInfo = getSessionInfo();

  if (!sessionInfo) {
    return;
  }

  let sidebarHTML = '';

  
}