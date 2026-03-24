/**
 * @file Nastavení – správa profilu zaměstnance (heslo) a konfigurace čteček karet.
 */
import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { requestPortFromUser, setUpCardReading } from "../general/card_reader.js";
import { UnexpectedError } from "../general/errors.js";
import { headerClickListeners, renderHeader } from "../general/header.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { clearModalErrors, closeModal, openModal } from "../general/modals_forms.js";
import { renderSidebar, sidebarClickListeners } from "../general/sidebar.js";

const displayUsername = document.querySelector('#display-username');
const displayEmail = document.querySelector('#display-email');
const displayRole = document.querySelector('#display-role');
const readersList = document.querySelector('#readers-list');
const readersEmpty = document.querySelector('#readers-empty');
const readersNotSupported = document.querySelector('#readers-not-supported');
const addReaderButton = document.querySelector('#add-reader-button');
const readerTestResult = document.querySelector('#reader-test-result');
const readerTestValue = document.querySelector('#reader-test-value');

let currentProfile = null;

loadPage({
  header: true,
  sidebar: true,
  profile: true,
  readers: true
});


/**
 * Načte různé části stránky podle zadaných parametrů.
 * @param {Object} param0 - Objekt s volbami, co načíst.
 * @param {boolean} [param0.header=false] - Zda načíst hlavičku.
 * @param {boolean} [param0.sidebar=false] - Zda načíst postranní panel.
 * @param {boolean} [param0.profile=false] - Zda načíst profil uživatele.
 * @param {boolean} [param0.readers=false] - Zda načíst čtečky karet.
 * @returns {Promise<void>} - Vrací promise po načtení všech částí.
 */
async function loadPage({
  header = false,
  sidebar = false,
  profile = false,
  readers = false } = {}) {
  const toLoad = [];
  if (header) toLoad.push(renderHeader());
  if (sidebar) toLoad.push(renderSidebar());
  if (profile) toLoad.push(loadProfile());
  if (readers) toLoad.push(renderReaders());
  await Promise.all(toLoad);
}


document.addEventListener('click', (event) => {
  const headerClick = headerClickListeners(event);
  const sidebarClick = sidebarClickListeners(event);
  if (headerClick || sidebarClick) {
    return;
  }

  // zavřít modal
  const closeModalBtn = event.target.closest('.close-modal');
  if (closeModalBtn) {
    closeModal();
    return;
  }

  // ukaž nebo skryj heslo a změň oko
  const showPassword = event.target.closest('.pw-eye');
  if (showPassword) {
    const passwordInput = showPassword.parentElement.querySelector('input[type="password"], input[type="text"]');
    if (!passwordInput) return;

    if (showPassword.classList.contains('state-show')) {
      passwordInput.setAttribute('type', 'password');
    } else {
      passwordInput.setAttribute('type', 'text');
    }

    const isShow = showPassword.classList.toggle('state-hide');
    showPassword.classList.toggle('state-show', !isShow);
    showPassword.classList.toggle('state-hide', isShow);
    return;
  }

  // // otevřít modal pro úpravu uživatelského jména
  // if (event.target.closest('#edit-username-button')) {
  //   openEditUsernameModal();
  //   return;
  // }

  // // otevřít modal pro úpravu emailu
  // if (event.target.closest('#edit-email-button')) {
  //   openEditEmailModal();
  //   return;
  // }

  // otevřít modal pro změnu hesla
  if (event.target.closest('#change-password-button')) {
    openChangePasswordModal();
    return;
  }

  // otestovat čtečku
  const testReaderBtn = event.target.closest('.test-reader');
  if (testReaderBtn) {
    const index = parseInt(testReaderBtn.dataset.index);
    testReader(index);
    return;
  }

  // odebrat čtečku
  const removeReaderBtn = event.target.closest('.remove-reader');
  if (removeReaderBtn) {
    const index = parseInt(removeReaderBtn.dataset.index);
    forgetReader(index);
    return;
  }

  // přidat čtečku
  if (event.target.closest('#add-reader-button')) {
    addReader();
    return;
  }
});


document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    const overlay = document.querySelector('.overlay');
    if (overlay) {
      closeModal();
      return;
    }
  }
});


document.addEventListener('submit', async (event) => {
  // uložit uživatelské jméno
  // const usernameForm = event.target.closest('#edit-username-form');
  // if (usernameForm) {
  //   event.preventDefault();
  //   const saveButton = usernameForm.querySelector('.save-form');
  //   saveButton.disabled = true;
  //   clearModalErrors();

  //   const formData = new FormData(usernameForm);
  //   formData.set('username', formData.get('username').trim());

  //   const response = await updateProfile(formData);
  //   saveButton.disabled = false;

  //   if (response === true) {
  //     closeModal();
  //     loadPage({ profile: true, header: true });
  //     return;
  //   }

  //   showUsernameModalErrors(response.error);
  //   return;
  // }

  // // uložit email
  // const emailForm = event.target.closest('#edit-email-form');
  // if (emailForm) {
  //   event.preventDefault();
  //   const saveButton = emailForm.querySelector('.save-form');
  //   saveButton.disabled = true;
  //   clearModalErrors();

  //   const formData = new FormData(emailForm);
  //   formData.set('email', formData.get('email').trim());

  //   const response = await updateProfile(formData);
  //   saveButton.disabled = false;

  //   if (response === true) {
  //     closeModal();
  //     loadPage({ profile: true, header: true });
  //     return;
  //   }

  //   showEmailModalErrors(response.error);
  //   return;
  // }

  // změnit heslo
  const passwordForm = event.target.closest('#change-password-form');
  if (passwordForm) {
    event.preventDefault();
    const saveButton = passwordForm.querySelector('.save-form');
    saveButton.disabled = true;
    clearModalErrors();

    const formData = new FormData(passwordForm);

    const response = await updateProfile(formData);
    saveButton.disabled = false;

    if (response === true) {
      closeModal();
      return;
    }

    showPasswordModalErrors(response.error);
    return;
  }
});


if ('serial' in navigator) {
  navigator.serial.addEventListener('connect', (event) => {
    renderReaders()
  });

  navigator.serial.addEventListener('disconnect', (event) => {
    renderReaders()
  });
}



// -- Profil --

/**
 * Načte profil aktuálního uživatele a zobrazí jej na stránce.
 * @returns {Promise<void>} - Vrací promise po načtení profilu.
 */
async function loadProfile() {
  try {
    const response = await fetch('/api/settings/profile');
    await handleUnauthorizedRedirect(response);
    const data = await response.json();

    if (!response.ok) {
      throw new UnexpectedError();
    }

    currentProfile = data.employee;
    displayUsername.textContent = currentProfile.username || '-';
    displayEmail.textContent = currentProfile.email || '-';
    displayRole.textContent = currentProfile.is_admin ? 'Administrátor' : 'Zaměstnanec';
  } catch (error) {

  }
}


/**
 * Vrací SVG kód pro ikonu oka pro zobrazení/skrývání hesla.
 * @returns {string} - SVG kód jako string.
 */
function passwordEyeSVG() {
  return `
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24"
      class="pw-eye state-hide" role="img" aria-hidden="true" focusable="false">
      <path class="eye-shape"
        d="M1.5 12S5.5 5.5 12 5.5 22.5 12 22.5 12 18.5 18.5 12 18.5 1.5 12 1.5 12z" />
      <g class="g-show" aria-hidden="true">
        <circle cx="12" cy="12" r="4" fill="var(--contrast)" />
        <circle cx="12" cy="12" r="2" fill="var(--fg)" />
      </g>
      <g class="g-hide" aria-hidden="true">
        <circle cx="12" cy="12" r="4" fill="var(--contrast)" />
        <circle cx="12" cy="12" r="2" fill="var(--fg)" />
        <line class="slash" x1="6.4" y1="4.8" x2="18.4" y2="19.2" stroke="var(--contrast)" stroke-width="2" />
        <line class="slash" x1="5.2" y1="4.8" x2="17.2" y2="19.2" stroke="var(--fg)" stroke-width="2" />
      </g>
    </svg>`;
}



// function openEditUsernameModal() {
//   const html = `
//     <header>
//       <h2>Změnit uživatelské jméno</h2>
//     </header>

//     <form id="edit-username-form">
//       <div class="form-row">
//         <label for="modal-username">Nové uživatelské jméno</label>
//         <input id="modal-username" name="username" type="text" placeholder="Uživatelské jméno"
//           value="${escapeHTML(currentProfile?.username || '')}" required />
//         <div id="modal-username-error" class="form-error"></div>
//       </div>

//       <div class="form-row password-form-row">
//         <label for="modal-username-password">Aktuální heslo</label>
//         <input id="modal-username-password" name="current-password" type="password"
//           placeholder="Zadejte heslo pro potvrzení" required />
//         ${passwordEyeSVG()}
//         <div id="modal-username-password-error" class="form-error"></div>
//       </div>

//       <div class="form-row">
//         <div id="modal-username-general-error" class="form-error"></div>
//       </div>

//       <div class="modal-actions">
//         <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
//         <button type="submit" class="save-form btn btn-primary">Uložit</button>
//       </div>
//     </form>
//   `;

//   openModal(html);
// }


// function openEditEmailModal() {
//   const html = `
//     <header>
//       <h2>Změnit email</h2>
//     </header>

//     <form id="edit-email-form">
//       <div class="form-row">
//         <label for="modal-email">Nový email</label>
//         <input id="modal-email" name="email" type="email" placeholder="Email"
//           value="${escapeHTML(currentProfile?.email || '')}" required />
//         <div id="modal-email-error" class="form-error"></div>
//       </div>

//       <div class="form-row password-form-row">
//         <label for="modal-email-password">Aktuální heslo</label>
//         <input id="modal-email-password" name="current-password" type="password"
//           placeholder="Zadejte heslo pro potvrzení" required />
//         ${passwordEyeSVG()}
//         <div id="modal-email-password-error" class="form-error"></div>
//       </div>

//       <div class="form-row">
//         <div id="modal-email-general-error" class="form-error"></div>
//       </div>

//       <div class="modal-actions">
//         <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
//         <button type="submit" class="save-form btn btn-primary">Uložit</button>
//       </div>
//     </form>
//   `;

//   openModal(html);
// }


/**
 * Otevře modal pro změnu hesla uživatele.
 * @returns {void}
 */
function openChangePasswordModal() {
  const html = `
    <header>
      <h2>Změnit heslo</h2>
    </header>

    <form id="change-password-form">
      <div class="form-row password-form-row">
        <label for="modal-current-password">Aktuální heslo</label>
        <input id="modal-current-password" name="current-password" type="password"
          placeholder="Aktuální heslo" required />
        ${passwordEyeSVG()}
        <div id="modal-current-password-error" class="form-error"></div>
      </div>

      <div class="form-row password-form-row">
        <label for="modal-new-password">Nové heslo</label>
        <input id="modal-new-password" name="new-password" type="password"
          placeholder="Nové heslo" required />
        ${passwordEyeSVG()}
        <div id="modal-new-password-error" class="form-error"></div>
      </div>

      <div class="form-row password-form-row">
        <label for="modal-confirm-password">Potvrdit nové heslo</label>
        <input id="modal-confirm-password" name="confirm-password" type="password"
          placeholder="Potvrdit nové heslo" required />
        ${passwordEyeSVG()}
        <div id="modal-confirm-password-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="modal-password-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" class="close-modal btn btn-ghost">Zrušit</button>
        <button type="submit" class="save-form btn btn-primary">Změnit heslo</button>
      </div>
    </form>
  `;

  openModal(html);
}


// -- API --

/**
 * Odesílá změny profilu na server (např. změna hesla).
 * @param {FormData} formData - Data formuláře k odeslání.
 * @returns {Promise<true|Object>} - Vrací true při úspěchu, jinak objekt s chybou.
 */
async function updateProfile(formData) {
  try {
    const response = await fetch('/api/settings/update-profile', {
      method: 'post',
      body: formData
    });

    await handleUnauthorizedRedirect(response);

    const data = await response.json();

    if (!response.ok) {
      return data;
    }

    return true;

  } catch (error) {
    return { error: 'unexpected_error' };
  }
}


// -- Čtečky --

/**
 * Vykreslí seznam připojených čteček karet na stránce.
 * @returns {Promise<void>} - Vrací promise po vykreslení čteček.
 */
async function renderReaders() {
  if (!('serial' in navigator)) {
    readersNotSupported.style.display = 'block';
    readersEmpty.style.display = 'none';
    addReaderButton.style.display = 'none';
    return;
  }

  const ports = await navigator.serial.getPorts();

  if (ports.length === 0) {
    readersList.innerHTML = '';
    readersEmpty.style.display = 'block';
    return;
  }

  readersEmpty.style.display = 'none';

  let html = '';
  ports.forEach((port, index) => {
    const info = port.getInfo();

    let label = `Čtečka ${index + 1}`;
  
    const infoArr = [];
    if (info.usbVendorId) {
      infoArr.push(`VID: ${escapeHTML(String(info.usbVendorId))}`);
    }
    if (info.usbProductId) {
      infoArr.push(`PID: ${escapeHTML(String(info.usbProductId))}`);
    }
    if (infoArr.length > 0) {
      label += ` (${infoArr.join(', ')})`;
    }

    html += `
      <div class="reader-item">
        <div class="reader-info">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M2 17l10 5 10-5M2 12l10 5 10-5M12 2L2 7l10 5 10-5L12 2z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="reader-label">${label}</span>
        </div>
        <div class="reader-actions">
          <button class="test-reader icon-btn test" data-index="${index}" title="Otestovat čtečku">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M5 3l14 9-14 9V3z" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
            </svg>
          </button>
          <button class="remove-reader icon-btn delete" data-index="${index}">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </div>
      </div>
    `;
  });

  readersList.innerHTML = html;
}


/**
 * Přidá novou čtečku karet po výběru uživatelem.
 * @returns {Promise<void>} - Vrací promise po přidání čtečky.
 */
async function addReader() {
  if (!('serial' in navigator)) return;

  try {
    await requestPortFromUser(true);
    renderReaders();
  } catch (error) {
    // uživatel zrušil výběr
  }
}


/**
 * Zapomene (odebere) čtečku karet podle indexu.
 * @param {number} index - Index čtečky v seznamu.
 * @returns {Promise<void>} - Vrací promise po odebrání čtečky.
 */
async function forgetReader(index) {
  if (!('serial' in navigator)) return;

  const ports = await navigator.serial.getPorts();

  if (index < 0 || index >= ports.length) return;

  try {
    await ports[index].forget();
  } catch (error) { }

  renderReaders();
}


/**
 * Otestuje čtečku karet na zadaném indexu a zobrazí výsledek.
 * @param {number} index - Index čtečky v seznamu.
 * @returns {void}
 */
function testReader(index) {
  readerTestResult.style.display = 'flex';
  readerTestValue.textContent = 'Čekám na kartu...';

  setUpCardReading((cardId) => {
    cardId = cardId.trim();
    if (cardId.length === 0) return;
    readerTestValue.textContent = cardId;
  }, true, index);
}



// function showUsernameModalErrors(error) {
//   const usernameError = document.querySelector('#modal-username-error');
//   const passwordError = document.querySelector('#modal-username-password-error');
//   const generalError = document.querySelector('#modal-username-general-error');

//   const setErr = (el, text) => {
//     if (!el) return;
//     el.innerHTML = escapeHTML(String(text));
//     el.classList.add('show-form-error');
//   };

//   if (!error) {
//     setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
//     return;
//   }

//   const resStr = String(error);

//   switch (resStr) {
//     case 'missing_current_password':
//       setErr(passwordError, 'Zadejte aktuální heslo.');
//       return;
//     case 'invalid_current_password':
//       setErr(passwordError, 'Nesprávné heslo.');
//       return;
//     case 'username_taken':
//       setErr(usernameError, 'Uživatelské jméno už má jiný uživatel.');
//       return;
//     case 'db_integrity_error':
//       setErr(generalError, 'Něco se nepovedlo.');
//       return;
//     case 'nothing_to_update':
//       setErr(usernameError, 'Chybí uživatelské jméno.');
//       return;
//     case 'employee_not_found':
//       setErr(generalError, 'Zaměstnanec nenalezen.');
//       return;
//     case 'unexpected_error':
//       setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
//       return;
//     default:
//       break;
//   }

//   const low = resStr.toLowerCase();

//   if (low.includes('username must be at least')) {
//     let limit = low.split('username must be at least ');
//     limit = limit[1].split(' characters')[0];
//     setErr(usernameError, `Minimální délka uživatelského jména je ${limit}.`);
//     return;
//   }
//   if (low.includes('username must be at most')) {
//     let limit = low.split('username must be at most ');
//     limit = limit[1].split(' characters')[0];
//     setErr(usernameError, `Maximální délka uživatelského jména je ${limit}.`);
//     return;
//   }
//   if (low.includes('username must start and end with')) {
//     const allowedChars = low.split('characters: ')[1];
//     setErr(usernameError, `Uživatelské jméno musí začínat a končit písmenem nebo číslicí a může pouze obsahovat písmena, číslice a tyto znaky: ${allowedChars}`);
//     return;
//   }
//   if (low.includes('username must not contain')) {
//     setErr(usernameError, 'Uživatelské jméno nesmí obsahovat více speciálních znaků za sebou.');
//     return;
//   }

//   setErr(generalError, resStr);
// }


// function showEmailModalErrors(error) {
//   const emailError = document.querySelector('#modal-email-error');
//   const passwordError = document.querySelector('#modal-email-password-error');
//   const generalError = document.querySelector('#modal-email-general-error');

//   const setErr = (el, text) => {
//     if (!el) return;
//     el.innerHTML = escapeHTML(String(text));
//     el.classList.add('show-form-error');
//   };

//   if (!error) {
//     setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
//     return;
//   }

//   const resStr = String(error);

//   switch (resStr) {
//     case 'missing_current_password':
//       setErr(passwordError, 'Zadejte aktuální heslo.');
//       return;
//     case 'invalid_current_password':
//       setErr(passwordError, 'Nesprávné heslo.');
//       return;
//     case 'email_taken':
//       setErr(emailError, 'E-mail už má jiný uživatel.');
//       return;
//     case 'db_integrity_error':
//       setErr(generalError, 'Něco se nepovedlo.');
//       return;
//     case 'nothing_to_update':
//       setErr(emailError, 'Chybí email.');
//       return;
//     case 'invalid_email':
//       setErr(emailError, 'Neplatný e-mail.');
//       return;
//     case 'employee_not_found':
//       setErr(generalError, 'Zaměstnanec nenalezen.');
//       return;
//     case 'unexpected_error':
//       setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
//       return;
//     default:
//       break;
//   }

//   setErr(generalError, resStr);
// }


/**
 * Zobrazí chybové hlášky v modalu pro změnu hesla podle typu chyby.
 * @param {string} error - Kód nebo popis chyby.
 * @returns {void}
 */
function showPasswordModalErrors(error) {
  const currentPwError = document.querySelector('#modal-current-password-error');
  const newPwError = document.querySelector('#modal-new-password-error');
  const confirmPwError = document.querySelector('#modal-confirm-password-error');
  const generalError = document.querySelector('#modal-password-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const resStr = String(error);

  switch (resStr) {
    case 'missing_current_password':
      setErr(currentPwError, 'Zadejte aktuální heslo.');
      return;
    case 'invalid_current_password':
      setErr(currentPwError, 'Nesprávné heslo.');
      return;
    case 'missing_new_password':
      setErr(newPwError, 'Zadejte nové heslo.');
      return;
    case 'nothing_to_update':
      setErr(newPwError, 'Zadejte nové heslo.');
      return;
    case 'passwords_do_not_match':
      setErr(confirmPwError, 'Hesla se neshodují.');
      return;
    case 'employee_not_found':
      setErr(generalError, 'Zaměstnanec nenalezen.');
      return;
    case 'unexpected_error':
      setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
      return;
    default:
      break;
  }

  const low = resStr.toLowerCase();

  if (low.includes('password must be at least')) {
    let limit = low.split('password must be at least ');
    limit = limit[1].split(' characters')[0];
    setErr(newPwError, `Minimální délka hesla je ${limit}.`);
    return;
  }
  if (low.includes('password must not contain spaces or tabs')) {
    setErr(newPwError, 'Heslo nesmí obsahovat mezery nebo tabulátory.');
    return;
  }
  if (low.includes('uppercase')) {
    setErr(newPwError, 'Heslo musí obsahovat alespoň jedno velké písmeno.');
    return;
  }
  if (low.includes('lowercase')) {
    setErr(newPwError, 'Heslo musí obsahovat alespoň jedno malé písmeno.');
    return;
  }
  if (low.includes('digit')) {
    setErr(newPwError, 'Heslo musí obsahovat alespoň jedno číslo.');
    return;
  }
  if (low.includes('special character')) {
    setErr(newPwError, 'Heslo musí obsahovat alespoň jeden speciální znak (např. !@#$%).');
    return;
  }
  if (low.includes('too common')) {
    setErr(newPwError, 'Heslo je příliš jednoduché nebo běžné.');
    return;
  }
  if (low.includes('must not contain the username')) {
    setErr(newPwError, 'Heslo nesmí obsahovat uživatelské jméno.');
    return;
  }
  if (low.includes('must not contain the email local-part')) {
    setErr(newPwError, 'Heslo nesmí obsahovat část e-mailu před zavináčem.');
    return;
  }
  if (low.includes('repeated characters')) {
    setErr(newPwError, 'Heslo obsahuje příliš mnoho opakujících se znaků.');
    return;
  }

  setErr(generalError, 'Něco se nepovedlo.');
}
