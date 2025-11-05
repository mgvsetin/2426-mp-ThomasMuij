import { getSessionInfo } from "./session.js";

const sidebar = document.querySelector('#sidebar');
const sidebarLinks = sidebar.querySelector('#sidebar-links');


export async function renderSidebar() {
  const sessionInfo = await getSessionInfo();

  if (!sessionInfo || !sessionInfo.employee) {
    sidebarLinks.innerHTML = '';
    return;
  }

  const isAdmin = sessionInfo.employee.is_admin;
  const isManager = sessionInfo.employee.is_event_manager;
  const boothType = sessionInfo.booth ? sessionInfo.booth.booth_type : null;

  let sidebarLinksHTML = '';
  
  if (boothType === 'seller') {
    sidebarLinksHTML += `
      <div id="seller-part">
        seller-part
        <!-- <div id="seller-part-title"></div> wont have? -->
      </div>
    `;
  }

  if (boothType === 'cashier') {
    sidebarLinksHTML += `
      <div id="cashier-part">
        cashier-part
        <!-- <div id="cashier-part-title"></div> wont have? -->
      </div>
    `;
  }

  if (isManager || (sessionInfo.event && isAdmin)) {
    sidebarLinksHTML += `
      <div id="manager-part">
        <div id="manager-part-title">Manažer</div>
        <a href="">Spravovat akci</a>
      </div>
    `;
  }

  if (isAdmin) {
    sidebarLinksHTML += `
      <div id="admin-part">
        <div id="admin-part-title">Admin</div>
        <a href="/admin/employees/manager">Spravovat uživatele</a>
        <a href="">Spravovat akce</a>
      </div>
    `;
  }

  sidebarLinks.innerHTML = sidebarLinksHTML;
}


export function sidebarClickListeners(event) {
  if (!event.target.closest('#sidebar') && !event.target.matches('#open-sidebar-button, #open-sidebar-icon')) {
    // kliknutí jinam než na sidebar nebo otevírání sidebar
    sidebar.removeAttribute('opened');
  }

  if (event.target.matches('#close-sidebar-button, #close-sidebar-icon')) {
    sidebar.removeAttribute('opened');
    return true;
  }

  return false;
}