import { headerClickListeners, headerKeydownListeners, renderHeader } from "../general/header.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";



loadPage({
  header: true,
  sidebar: true
});


async function loadPage({
  sidebar = false,
  header = false
} = {}) {
  
  const toLoad = [];

  if (sidebar) {
    toLoad.push(renderSidebar('#employee-manager-link'));
  }

  if (header) {
    toLoad.push(renderHeader());
  }

  await Promise.all(toLoad);
}


document.addEventListener('click', async (event) => {
  headerClickListeners(event);
  sidebarClickListeners(event);
})

document.addEventListener('keydown', (event) => {
  headerKeydownListeners(event);
})