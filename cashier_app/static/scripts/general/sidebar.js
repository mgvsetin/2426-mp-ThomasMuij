import { getSessionInfo } from "./session.js";

const sidebar = document.querySelector('#sidebar');
const sidebarLinks = sidebar.querySelector('#sidebar-links');


export async function renderSidebar(selectedId) {
  const sessionInfo = await getSessionInfo();

  if (!sessionInfo || !sessionInfo.employee) {
    sidebarLinks.innerHTML = '';
    return;
  }

  const isAdmin = sessionInfo.employee.is_admin;
  const isManager = sessionInfo.employee.is_event_manager;
  const boothType = sessionInfo.booth ? sessionInfo.booth.booth_type : null;

  let sidebarLinksHTML = '';

  sidebarLinksHTML += `
    <div id="general-part">
      <a id="index-link" href="/">Domů</a>
    </div>
  `;
  
  // if (boothType === 'seller') {
  //   sidebarLinksHTML += `
  //     <div id="seller-part">
  //       <!-- <div id="seller-part-title"></div> wont have? -->
  //       <a id="seller-link" href="/">Prodej</a>
  //     </div>
  //   `;
  // }

  // if (boothType === 'cashier') {
  //   sidebarLinksHTML += `
  //     <div id="cashier-part">
  //       cashier-part
  //       <!-- <div id="cashier-part-title"></div> wont have? -->
  //     </div>
  //   `;
  // }

  if (isManager || (sessionInfo.event && isAdmin)) {
    sidebarLinksHTML += `
      <div id="manager-part">
        <div id="manager-part-title">Manažer</div>
        <a id="event-manager-link" href="">Spravovat akci</a>
      </div>
    `;
  }

  if (isAdmin) {
    sidebarLinksHTML += `
      <div id="admin-part">
        <div id="admin-part-title">Admin</div>
        <a id="employee-manager-link" href="/admin/employees/manager">Spravovat zaměstnance</a>
        <a id="events-manager-link" href="">Spravovat akce</a>
      </div>
    `;
  }

  sidebarLinks.innerHTML = sidebarLinksHTML;

  const selected = document.querySelector(selectedId);
  selected.classList.add('selected');
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