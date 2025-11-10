import { getSessionInfo } from "./session.js";


let sidebar, sidebarLinks, overlay;


function initSidebar() {
  if (document.getElementById('sidebar')) return;

  const sidebarHTML = `
    <div id="sidebar">
      <div id="close-sidebar-container">
        <button id="close-sidebar-button">
          <img id="close-sidebar-icon" src="/static/images/icons/sidebar_icon.png">
        </button>
      </div>
      <div id="sidebar-links"></div>
    </div>
  `;

  overlay = document.createElement('div');
  overlay.id = 'sidebar-overlay-page';
  overlay.innerHTML = sidebarHTML;
  document.body.prepend(overlay);

  sidebar = overlay.querySelector('#sidebar');
  sidebarLinks = sidebar.querySelector('#sidebar-links');
}


initSidebar();


export async function renderSidebar() {
  if (!sidebarLinks) initSidebar();

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
        <a id="event-manager-link" href="/events/event_manager/">Spravovat akci</a>
      </div>
    `;
  }

  if (isAdmin) {
    sidebarLinksHTML += `
      <div id="admin-part">
        <div id="admin-part-title">Admin</div>
        <a id="employee-manager-link" href="/admin/employee_manager/">Spravovat zaměstnance</a>
        <a id="events-manager-link" href="">Spravovat akce</a>
      </div>
    `;
  }

  sidebarLinks.innerHTML = sidebarLinksHTML;

  let selected = sidebarLinks.querySelector(`a[href="${location.pathname}"]`);

  // jestli href nekončí /
  if (!selected) {
    let path = location.pathname;
    if (path.endsWith('/')) {
      path = path.slice(0, path.length - 1);
      selected = sidebarLinks.querySelector(`a[href="${path}"]`);
    }
  }

  if (selected) selected.classList.add('selected');
}


export function sidebarClickListeners(event) {
  if (!overlay) initSidebar();

  if (!event.target.closest('#sidebar') && !event.target.matches('#open-sidebar-button, #open-sidebar-icon')) {
    // kliknutí jinam než na sidebar nebo otevírání sidebar
    overlay.removeAttribute('opened');
  }

  if (event.target.matches('#close-sidebar-button, #close-sidebar-icon')) {
    overlay.removeAttribute('opened');
    return true;
  }

  return false;
}