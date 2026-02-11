import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { cloneData } from "../general/cache.js";
import { cacheFunctionFactory } from "../general/cache_factory.js";
import { BoothNotSelectedError, EventNotSelectedError, InvalidBoothTypeError, UnexpectedError } from "../general/errors.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { clearModalErrors, openModal } from "../general/modals_forms.js";
import { getSessionInfo } from "../general/session.js";
import { markSelectedRows } from "../general/table_utils.js";
import { lastReadCardId, removeReadCard, renderCard } from "./cards.js";
import { changeSelectedCode } from "./phone_number_input.js";
import { fetchWallets } from "./wallets.js";


const usersPanel = document.querySelector('#users-panel');
const usersTableBody = document.querySelector('#users-table tbody');
const usersSearchBar = document.querySelector('#users-search-bar');

const userIdInput = document.querySelector('#user-id-input');
const firstNameInput = document.querySelector('#first-name-input');
const lastNameInput = document.querySelector('#last-name-input');
const emailInput = document.querySelector('#email-input');
const countryCodeInput = document.querySelector('#country-code-input');
const phoneNumberInput = document.querySelector('#phone-number-input');
const otherIdentifierInput = document.querySelector('#other-identifier-input');
const changeBalanceByInput = document.querySelector('#change-balance-by-input');
const setNewBalanceInput = document.querySelector('#set-new-balance-input');

const openMoreUserOptionsModalBtn = document.querySelector('#open-more-user-options');
const saveUserFormBtn = document.querySelector('#save-user-form');

const searchUsersWithInputs = document.querySelector('#user-inputs-search-table-toggle');

export let selectedUserForUpdate;

const orderBy = { key: '', ascending: true };

// editUserFormOnChange(); volá se v index (chooseAndLoadPage, po pickBooth)


export const [fetchUsers, resetUsersCache] = cacheFunctionFactory(async () => {
  const response = await fetch('/api/users');

  await handleUnauthorizedRedirect(response);

  const resData = await response.json();

  if (response.status === 400 && resData.error === 'no_selected_event') {
    throw new EventNotSelectedError();
  }

  if (response.status === 400 && resData.error === 'no_selected_booth') {
    throw new BoothNotSelectedError();
  }

  if (response.status === 400 && resData.error === 'invalid_booth_type') {
    throw new InvalidBoothTypeError();
  }

  if (!response.ok) {
    throw new UnexpectedError();
  }

  return resData.users;
})


// export function findProduct(products, productId) {
//   for (const product of products) {
//     if (product.id === productId) {
//       return product;
//     }
//   }
// }


export function setOrder(headerEl) {
  const id = headerEl.id || '';

  switch (id) {
    case 'first-name-header':
      toggleOrder('first_name', headerEl);
      break;
    case 'last-name-header':
      toggleOrder('last_name', headerEl);
      break;
    case 'email-header':
      toggleOrder('email', headerEl);
      break;
    case 'phone-number-header':
      toggleOrder('phone_number', headerEl);
      break;
    case 'other-identifier-header':
      toggleOrder('other_identifier', headerEl);
      break;
  }
}


function toggleOrder(key, headerEl) {
  if (orderBy.key !== key) {
    orderBy.key = key;
    orderBy.ascending = true;
  } else if (orderBy.ascending) {
    orderBy.ascending = false;
  } else {
    orderBy.key = '';
    orderBy.ascending = true;
  }

  usersPanel.querySelectorAll('.order-by-arrow').forEach(el => el.remove());

  if (orderBy.key) {
    const orderByArrow = document.createElement('span');
    orderByArrow.classList.add('order-by-arrow');
    orderByArrow.innerHTML = orderBy.ascending ? '&#8595;' : '&#8593;';
    headerEl.querySelector('div').appendChild(orderByArrow);
  }
}


function userIsSearchedFor(user) {
  const searchQuery = usersSearchBar.value.toLowerCase().trim();

  const queries = searchQuery.split(/\s+/);

  const addSearch = (search, searchKey) => {
    if (!search) return;
    queries.push(`${searchKey}=${search}`)
  }

  const doInputSearch = searchUsersWithInputs.hasAttribute('search-users');
  if (doInputSearch) {
    const firstNameSearch = firstNameInput.value.toLowerCase().trim().replace(/\s/g, '');
    const lastNameSearch = lastNameInput.value.toLowerCase().trim().replace(/\s/g, '');
    const emailSearch = emailInput.value.toLowerCase().trim().replace(/\s/g, '');
    // country code je vynechaný schválně
    const phoneNumberSearch = phoneNumberInput.value.toLowerCase().trim().replace(/\s/g, '');
    const otherIdentifierSearch = otherIdentifierInput.value.toLowerCase().trim().replace(/\s/g, '');

    addSearch(firstNameSearch, 'first_name');
    addSearch(lastNameSearch, 'last_name');
    addSearch(emailSearch, 'email');
    addSearch(phoneNumberSearch, 'phone_number');
    addSearch(otherIdentifierSearch, 'other_identifier');
  }


  const firstName = String(user.first_name || '').toLowerCase();
  const lastName = String(user.last_name || '').toLowerCase();
  const email = String(user.email || '-').toLowerCase();
  const phoneNumber = String(user.phone_number || '-').toLowerCase().replace(/\s/g, '');
  const otherIdentifier = String(user.other_identifier || '-').toLowerCase();

  const searchable = `${firstName} ${lastName} ${email} ${phoneNumber} ${otherIdentifier}`;

  for (const query of queries) {
    if (!query.includes('=')) {
      if (!searchable.includes(query)) return false;
    } else {
      const [searchKeyWord, search] = query.split('=');

      if (['name',
        'jméno',
        'jmeno',
        'uživatel',
        'uzivatel',
        'uživatelské_jméno',
        'uzivatelske_jmeno',
        'uživatelskéjméno',
        'uzivatelskejmeno'].includes(searchKeyWord)) {
        if (!`${firstName} ${lastName}`.includes(search)) return false;
      } else if ([
        'first_name',
        'firstname',
        'křestníjméno',
        'krestnijmeno',
        'křestní_jméno',
        'krestni_jmeno',
        'křestní',
        'krestni',].includes(searchKeyWord)) {
        if (!firstName.includes(search)) return false;
      } else if (['last_name',
        'lastname',
        'příjmení',
        'prijmeni'].includes(searchKeyWord)) {
        if (!lastName.includes(search)) return false;
      } else if (['email',
        'e-mail',
        'mail'].includes(searchKeyWord)) {
        if (!email.includes(search)) return false;
      } else if (['phone',
        'phone_number',
        'phonenumber',
        'telephone',
        'number',
        'telefonní_číslo',
        'telefonni_cislo',
        'telefonníčíslo',
        'telefonnicislo',
        'telefon',
        'číslo',
        'cislo',
        'telefonní',
        'telefonni'].includes(searchKeyWord)) {
        if (!phoneNumber.includes(search)) return false;
      } else if (['identifier',
        'other_identifier',
        'otheridentifier',
        'other',
        'jiný_identifikátor',
        'jiny_identifikator',
        'jinýidentifikátor',
        'jinyidentifikator',
        'identifikátor',
        'identifikator',
        'jiný',
        'jiny'].includes(searchKeyWord)) {
        if (!otherIdentifier.includes(search)) return false;
      } else {
        if (!searchable.includes(query)) return false;
      }
    }
  }
  return true;
}


export async function renderUsers() {
  const users = await fetchUsers().catch((error) => {
    usersTableBody.innerHTML = '<tr><td colspan="7">Nepovedlo se načíst uživatele.</td></tr>';
  });
  if (!users) return;


  const sorter = (a, b) => {
    if (!orderBy.key) return 0;
    const key = orderBy.key;
    let aValue = a[key] || '';
    let bValue = b[key] || '';

    aValue = String(aValue).toLowerCase();
    bValue = String(bValue).toLowerCase();

    return aValue.localeCompare(bValue) * (orderBy.ascending ? 1 : -1);
  }


  const sortedUsers = users.toSorted(sorter);

  let rows = '';

  sortedUsers.forEach((user, idx) => {
    const doInputSearch = searchUsersWithInputs.hasAttribute('search-users');
    if (doInputSearch) {
      if ((!selectedUserForUpdate || selectedUserForUpdate.id !== user.id) && !userIsSearchedFor(user)) return;
    } else {
      if (!userIsSearchedFor(user)) return;
    }

    rows += `
      <tr id="${user.id}">
        <td>${idx + 1}</td>
        <td>${escapeHTML(user.first_name)}</td>
        <td>${escapeHTML(user.last_name)}</td>
        <td>${escapeHTML(user.email || '-')}</td>
        <td>${escapeHTML(user.phone_number || '-')}</td>
        <td>${escapeHTML(user.other_identifier || '-')}</td>
        <td class="actions">
          <button class="icon-btn edit edit-user">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="">
              <path d="M3 21l3-1 11-11 1-3-3 1L4 20z" stroke="currentColor" stroke-width="1.4"
                stroke-linecap="round" stroke-linejoin="round" fill="none"></path>
            </svg>
          </button>
          <button class="icon-btn delete delete-user">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" aria-hidden="">
              <path d="M3 6h18M8 6v12a2 2 0 0 0 2 2h4a2 2 0 0 0 2-2V6M10 6V4a2 2 0 0 1 2-2h0a2 2 0 0 1 2 2v2"
                stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round"></path>
            </svg>
          </button>
        </td>
      </tr>
    `;
  });

  usersTableBody.innerHTML = rows || '<tr><td colspan="7">Žádní uživatelé.</td></tr>';
  markSelectedRows(usersTableBody);

  if (selectedUserForUpdate) {
    const rowSelectedForUpdate = document.getElementById(selectedUserForUpdate.id);
    rowSelectedForUpdate?.classList.add('selected-for-update');
  }
}


export async function selectUserForUpdate(userId) {
  userId = userId.trim();
  const users = await fetchUsers().catch(() => { });
  if (!users) return;

  const user = users.find(user => user.id === userId);
  if (!user) return;

  if (userIdInput.value === user.id) {
    return;
  }

  const selectedRow = document.querySelector('tr.selected-for-update');
  if (selectedRow) selectedRow.classList.remove('selected-for-update');

  const userRow = document.querySelector(`tr[id="${userId}"]`)
  userRow?.classList.add('selected-for-update');

  const countryCode = user.phone_number_country_code;
  const phoneNumber = user.phone_number_national_significant_number;

  userIdInput.value = user.id;
  firstNameInput.value = user.first_name;
  lastNameInput.value = user.last_name;
  emailInput.value = user.email;
  changeSelectedCode(countryCode);
  phoneNumberInput.value = phoneNumber;
  otherIdentifierInput.value = user.other_identifier;

  selectedUserForUpdate = user;
  await editUserFormOnChange();
  renderUsers();
}


export async function unselectUserForUpdate() {
  removeReadCard();

  userIdInput.value = '';
  firstNameInput.value = '';
  lastNameInput.value = '';
  emailInput.value = '';
  // changeSelectedCode('');
  phoneNumberInput.value = '';
  otherIdentifierInput.value = '';

  const selectedRow = document.querySelector('tr.selected-for-update');
  if (selectedRow) selectedRow.classList.remove('selected-for-update');

  selectedUserForUpdate = null;
  await editUserFormOnChange();
  renderUsers();
}


export async function editUserFormOnChange(inputEvent = null) {
  const result = await Promise.all([
    fetchUsers().catch(() => { }),
    renderCard().catch(() => { })
  ]);

  const users = result[0];
  let wallet = result[1]

  if (wallet && wallet.owner_id && wallet.owner_id !== userIdInput.value.toLowerCase().trim()) {
    await selectUserForUpdate(wallet.owner_id);
  }

  if (!wallet && lastReadCardId) {
    wallet = {
      tag_id: lastReadCardId,
      owner_id: null,
      balance_czk: 0
    }
  }

  const userId = userIdInput.value.trim();
  const firstName = firstNameInput.value.toLowerCase().trim();
  const lastName = lastNameInput.value.toLowerCase().trim();
  const email = emailInput.value.toLowerCase().trim();
  const countryCode = countryCodeInput.value.toLowerCase().trim();
  const phoneNumber = phoneNumberInput.value.toLowerCase().trim();
  const otherIdentifier = otherIdentifierInput.value.toLowerCase().trim();

  const user = users?.find((user) => { return user.id === userId; });

  const firstNamesMatch = user?.first_name.toLowerCase() === firstName;
  const lastNamesMatch = user?.last_name.toLowerCase() === lastName;
  const emailsMatch = user?.email === (email ? email : null);
  const phoneNumbersMatch = user?.phone_number === (countryCode && phoneNumber ? `${countryCode}${phoneNumber}` : null);
  const otherIdentifiersMatch = user?.other_identifier === (otherIdentifier ? otherIdentifier : null);

  const valuesMatch = firstNamesMatch && lastNamesMatch && emailsMatch && phoneNumbersMatch && otherIdentifiersMatch;

  if (user && valuesMatch) {
    saveUserFormBtn.textContent = 'Žádná změna';
    saveUserFormBtn.setAttribute('user-job', '');
    openMoreUserOptionsModalBtn.disabled = false;
  } else if (user && !valuesMatch) {
    saveUserFormBtn.textContent = 'Upravit';
    saveUserFormBtn.setAttribute('user-job', 'edit');
    openMoreUserOptionsModalBtn.disabled = false;
  } else {
    openMoreUserOptionsModalBtn.disabled = true;
    if (userId) {
      userIdInput.value = '';
      const selectedRow = document.querySelector('tr.selected-for-update');
      if (selectedRow) selectedRow.classList.remove('selected-for-update');
      selectedUserForUpdate = null;
    }

    saveUserFormBtn.textContent = 'Vytvořit';
    saveUserFormBtn.setAttribute('user-job', 'create');
  }

  if (lastReadCardId) {
    if (inputEvent && inputEvent.target === changeBalanceByInput) {
      let changeBalanceBy = Number(changeBalanceByInput.value);

      if (!isNaN(changeBalanceBy)) {
        const newBalance = wallet.balance_czk + changeBalanceBy;
        setNewBalanceInput.value = newBalance;
        if (changeBalanceByInput.value === '' || changeBalanceBy !== 0) {
          // odendá navíc nuly na začátku, pokud hodnota není nula (když je nula tak ne protože můžu chytít přepsat 1000 na 2000 přes 000)
          // a změní '' na 0
          changeBalanceByInput.value = changeBalanceBy;
        }
      }
    }

    if (inputEvent && inputEvent.target === setNewBalanceInput) {
      let newBalance = Number(setNewBalanceInput.value);

      if (!isNaN(newBalance)) {
        const changeBalanceBy = newBalance - wallet.balance_czk;
        changeBalanceByInput.value = changeBalanceBy;
        if (setNewBalanceInput.value === '' || newBalance !== 0) {
          // odendá navíc nuly na začátku, pokud hodnota není nula (když je nula tak ne protože můžu chytít přepsat 1000 na 2000 přes 000)
          // a změní '' na 0
          setNewBalanceInput.value = newBalance;
        }
      }
    }


    if (wallet.owner_id === userId && wallet.balance_czk === Number(setNewBalanceInput.value)) {
      if (saveUserFormBtn.textContent === 'Žádná změna') {
        saveUserFormBtn.textContent = 'Vrátit kartu';
        saveUserFormBtn.setAttribute('card-job', 'return');
      } else {
        saveUserFormBtn.setAttribute('card-job', '');
      }
    } else if (wallet.owner_id === userId && wallet.balance_czk !== Number(setNewBalanceInput.value)) {
      saveUserFormBtn.textContent = saveUserFormBtn.textContent !== 'Žádná změna' ? `${saveUserFormBtn.textContent} a změnit zůstatek na kartě` : 'Změnit zůstatek na kartě';
      saveUserFormBtn.setAttribute('card-job', 'change-balance');
    } else {
      saveUserFormBtn.textContent = saveUserFormBtn.textContent !== 'Žádná změna' ? `${saveUserFormBtn.textContent} a přiradit kartu` : 'Přiřadit kartu';
      saveUserFormBtn.setAttribute('card-job', 'assign');
    }
  } else {
    setNewBalanceInput.value = '';
    changeBalanceByInput.value = '';

    saveUserFormBtn.setAttribute('card-job', '');
  }
}



export async function openDeleteUserModal(row) {
  const id = row.id;
  const users = await fetchUsers().catch(() => { });
  if (!users) return;

  const user = users.find(user => user.id === id);
  if (!user) return;

  const html = `
    <div class="modal">
      <header>
        <h2 class="delete-form-text">Smazat uživatele</h2>
        <button class="close-modal cross-close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </header>
      <form id="delete-user-form">
        <input type="hidden" name="user-id" value="${id}"/>
        <div class="form-row">
          <div>Opravdu chcete smazat uživatele "${escapeHTML(user.first_name)} ${escapeHTML(user.last_name)}"?</div>
        </div>

        <div class="form-row">
          <div id="delete-user-general-error" class="form-error"></div>
        </div>

        <div class="modal-actions">
          <button type="button" class="btn btn-ghost close-modal">Zrušit</button>
          <button type="submit" class="btn btn-delete">Smazat</button>
        </div>
      </form>
    </div>
  `;

  if (document.querySelector('.overlay')) return;
  const div = document.createElement('div');
  div.className = 'overlay';
  div.innerHTML = html;
  document.body.appendChild(div);
}


export async function openMoreUserOptionsModal(userId) {
  userId = userId.trim();
  const users = await fetchUsers().catch(() => { });
  if (!users) return;
  const user = users.find(user => user.id === userId);
  if (!user) return;

  const sessionInfo = await getSessionInfo().catch(() => { });
  if (!sessionInfo || !sessionInfo.event) return;

  const overlay = document.createElement('div');
  overlay.classList.add('overlay');
  overlay.innerHTML = `
    <div class="modal">
      <header>
        <h2>Dalsí možnosti pro "${user.first_name} ${user.last_name}"</h2>
        <button class="close-modal cross-close">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
            <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </header>
      <div id="more-user-options-actions">
        <button id="open-user-cards-modal">Zobrazit všechny karty</button>
        <a href="/events/${sessionInfo.event.id}/users/${user.id}/transaction-history" target="_blank"><button id="open-user-transaction-history">Zobrazit transakce</button></a>
      </div>
    </div>
  `;

  document.body.appendChild(overlay);
}


export async function openUserCardsModal(userId, modal = null) {
  userId = userId.trim();
  const users = await fetchUsers().catch(() => { });
  if (!users) return;
  const user = users.find(user => user.id === userId);
  if (!user) return;

  const wallets = await fetchWallets().catch((error) => {
    // maybe display some error
  });
  if (!wallets) return;

  const userWallets = wallets.filter((wallet) => { return wallet.owner_id === userId });
  let userWalletsHTML = '';

  userWallets.forEach((wallet) => {
    userWalletsHTML += `
      <li tag-id="${wallet.tag_id}">
        <div> <span>ID: ${wallet.tag_id}</span> <span>Zůstatek: ${wallet.balance_czk} Kč</span> </div>
      </li>
    `;
  })

  const html = `
    <header>
      <h2>Karty uživatele "${user.first_name} ${user.last_name}"</h2>
      <button class="close-modal cross-close">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </header>
    <ul id="user-wallets-list">
      ${userWalletsHTML ? userWalletsHTML : 'Uživatel nemá žádné karty.'}
    </ul>
  `;

  if (!modal) {
    if (document.querySelector('.overlay')) return;
    const div = document.createElement('div');
    div.className = 'overlay';
    div.innerHTML = `
    <div class="modal">
      ${html}
    </div>
  `;
    document.body.appendChild(div);
  } else {
    modal.innerHTML = html;
  }
}


export async function openUserCardModal(userWalletLi) {
  const tagId = userWalletLi.getAttribute('tag-id').trim();
  const modal = userWalletLi.closest('.modal');

  if (!modal) return;

  const [wallets, users] = await Promise.all([
    fetchWallets().catch(() => { }),
    fetchUsers().catch(() => { })
  ]);

  if (!wallets || !users) return;

  const wallet = wallets.find((wallet) => { return wallet.tag_id === tagId });
  if (!wallet) return;
  const user = users.find(user => user.id === wallet.owner_id);
  if (!user) return;

  modal.innerHTML = `
    <header>
      <h2>Karta uživatele "${user.first_name} ${user.last_name}"</h2>
      <button class="close-modal cross-close">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
          <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </button>
    </header>
    <div class="edit-wallet-card-info">ID: ${wallet.tag_id}</div>
    <div class="edit-wallet-card-info">Zůstatek: ${wallet.balance_czk} Kč</div>
    <form id="edit-wallet-form">

      <input type="hidden" name="tag-id" id="edit-wallet-tag-id-input" value=${wallet.tag_id}>

      <div class="form-row">
        <label for="change-balance-by-input">Přidat nebo ubrat peníze (Kč)</label>
        <input id="edit-wallet-change-balance-by-input" name="change-balance-by" type="number" value="0"/>
        <div id="edit-wallet-change-balance-by-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <label for="set-new-balance-input">Nový zůstatek (Kč)</label>
        <input id="edit-wallet-set-new-balance-input" name="new-balance" type="number" value="${wallet.balance_czk}"/>
        <div id="edit-wallet-set-new-balance-error" class="form-error"></div>
      </div>

      <div class="form-row">
        <div id="edit-wallet-general-error" class="form-error"></div>
      </div>

      <div class="modal-actions">
        <button type="button" id="back-to-user-cards" class="btn btn-ghost" user-id="${user.id}">Zpět</button>
        <button type="button" class="btn btn-primary" id="return-card-button">Vrátit kartu</button>
        <button type="submit" class="btn btn-primary">Uložit</button>
      </div>
    </form>
  `;
}


export async function editWalletInputListeners(event) {
  const editWalletTagIdInput = document.querySelector('#edit-wallet-tag-id-input');
  if (editWalletTagIdInput) {
    const tagId = editWalletTagIdInput.value.trim();
    const editWalletChangeBalanceByInput = document.querySelector('#edit-wallet-change-balance-by-input');
    const editWalletSetNewBalanceInput = document.querySelector('#edit-wallet-set-new-balance-input');

    if (event.target === editWalletChangeBalanceByInput) {
      const wallets = await fetchWallets().catch(() => { });
      if (!wallets) return;
      const wallet = wallets.find((wallet) => { return wallet.tag_id === tagId });
      if (!wallet) return;

      const changeBalanceBy = Number(editWalletChangeBalanceByInput.value);
      if (!isNaN(changeBalanceBy)) {
        const newBalance = wallet.balance_czk + changeBalanceBy;
        editWalletSetNewBalanceInput.value = newBalance;
        editWalletChangeBalanceByInput.value = changeBalanceBy; // pro 0
      }
    }

    if (event.target === editWalletSetNewBalanceInput) {
      const wallets = await fetchWallets().catch(() => { });
      if (!wallets) return;
      const wallet = wallets.find((wallet) => { return wallet.tag_id === tagId });
      if (!wallet) return;

      const newBalance = Number(editWalletSetNewBalanceInput.value);

      if (!isNaN(newBalance)) {
        const changeBalanceBy = newBalance - wallet.balance_czk;
        editWalletChangeBalanceByInput.value = changeBalanceBy;
        editWalletSetNewBalanceInput.value = newBalance; // pro 0
      }
    }
  }
}


export function clearFormErrors() {
  clearModalErrors();
}


export function showUserFormErrors(error, detail) {
  const firstNameError = document.querySelector('#first-name-error');
  const lastNameError = document.querySelector('#last-name-error');
  const emailError = document.querySelector('#email-error');
  const phoneNumberError = document.querySelector('#phone-number-error');
  const otherIdentifierError = document.querySelector('#other-identifier-error');
  const changeBalanceByError = document.querySelector('#change-balance-by-error');
  const setNewBalanceError = document.querySelector('#set-new-balance-error');
  const generalError = document.querySelector('#general-error');

  let nameErrorEl = generalError;
  if (detail === 'first_name_error') {
    nameErrorEl = firstNameError;
  } else if (detail === 'last_name_error') {
    nameErrorEl = lastNameError;
  }

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();

  switch (errorStr) {
    case 'unexpected_error':
    case 'internal_server_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'no_selected_event':
      setErr(generalError, 'Není vybraná akce.');
      return;
    case 'no_selected_booth':
      setErr(generalError, 'Není vybraný stánek.');
      return;
    case 'invalid_booth_type':
      setErr(generalError, 'Neplatný typ stánku.');
      return;
    case 'invalid_user_id':
      setErr(generalError, 'ID uživatele není správné.');
      return;
    case 'missing_user_id':
      setErr(generalError, 'Chybí ID uživatele.');
      return;
    case 'user_not_found':
      setErr(generalError, 'Uživatel nebyl nalezen.');
      return;
    case 'owner_not_found':
      setErr(generalError, 'Vlastník karty nebyl nalezen.');
      return;
    case 'missing_first_name':
      setErr(firstNameError, 'Chybí jméno.');
      return;
    case 'missing_last_name':
      setErr(lastNameError, 'Chybí příjmení.');
      return;
    case 'missing_country_code':
      setErr(phoneNumberError, 'Chybí předčíslí.');
      return;
    case 'invalid_phone_number':
      setErr(phoneNumberError, 'Telefonní číslo není správné.');
      return;
    case 'missing_tag_id':
      setErr(generalError, 'Chybí ID karty.');
      return;
    case 'wallet_not_found':
      setErr(generalError, 'Karta nebyla nalezena.');
      return;
    case 'at_least_one_of_email_phone_number_other_identifier_is_required':
      setErr(generalError, 'Vyplňte alespoň jeden z: email, telefonní číslo, jiný identifikátor.');
      return;
    case 'change_balance_by_must_be_a_number':
      setErr(changeBalanceByError, 'Změna musí být číslo.');
      return;
    case 'change_balance_by_must_be_a_whole_number':
      setErr(changeBalanceByError, 'Změna musí být celé číslo.');
      return;
    case 'new_balance_must_be_a_number':
      setErr(setNewBalanceError, 'Nový zůstatek musí být číslo.');
      return;
    case 'new_balance_must_be_a_whole_number':
      setErr(setNewBalanceError, 'Nový zůstatek musí být celé číslo.');
      return;
    case 'change_balance_by_and_new_balance_do_not_match':
      setErr(generalError, 'Změna a nový zůstatek se neshodují.');
      return;
    case 'changes_do_not_match_balance_czk':
      setErr(generalError, 'Změny neodpovídají aktuálnímu zůstatku.');
      return;
    case 'wallet_balance_czk_is_not_enough':
      setErr(generalError, 'Nedostatek peněz na kartě.');
      return;
    case 'resulting_wallet_balance_czk_is_too_high':
      setErr(generalError, 'Výsledný zůstatek je příliš vysoký.');
      return;
    case 'missing_idempotency_key':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'idempotency_key_data_conflict':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'user_identifier_taken':
      setErr(generalError, 'Uživatel se stejnými údaji už existuje.');
      return;
    case 'user_email_taken':
      setErr(emailError, 'Email už má jiný uživatel.');
      return;
    case 'tag_id_taken':
      setErr(generalError, 'ID karty je už použité pro tuto akci.');
      return;
    case 'db_integrity_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('name must be a string')) {
    setErr(nameErrorEl, 'Jméno nebo příjmení není správně zadané.');
    return;
  }
  if (errorStr.includes('name must be at least')) {
    let limit = errorStr.split('name must be at least ')[1].split(' characters')[0];
    setErr(nameErrorEl, `Jméno nebo příjmení může mít minimálně ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('name must be at most')) {
    let limit = errorStr.split('name must be at most ')[1].split(' characters')[0];
    setErr(nameErrorEl, `Jméno nebo příjmení může mít maximálně ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('name may only contain letters, digits, and these characters:')) {
    const allowedChars = errorStr.split('characters: ')[1];
    setErr(nameErrorEl, `Jméno nebo příjmení může obsahovat pouze písmena, číslice a tyto znaky: ${allowedChars}`);
    return;
  }
  if (errorStr.includes('name must not be all numeric')) {
    setErr(nameErrorEl, 'Jméno nebo příjmení nesmí obsahovat pouze čísla.');
    return;
  }
  if (errorStr.includes('name must not contain the reserved word:')) {
    const reservedWord = errorStr.split('reserved word: ')[1];
    setErr(nameErrorEl, `Jméno nebo příjmení nesmí obsahovat: ${reservedWord}`);
    return;
  }


  if (errorStr.includes('email must be a string')) {
    setErr(emailError, 'Email není správně zadaný.');
    return;
  }
  if (errorStr.includes('email is empty')) {
    setErr(emailError, 'Email je prázdný.');
    return;
  }

  if (errorStr.includes('email') && !errorStr.includes('must not contain')) {
    setErr(emailError, 'Email není platný.');
    return;
  }

  if (errorStr.includes('other_identifier must be at least')) {
    let limit = errorStr.split('other_identifier must be at least ')[1].split(' characters')[0];
    setErr(otherIdentifierError, `Minimální délka identifikátoru je ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('other_identifier must be at most')) {
    let limit = errorStr.split('other_identifier must be at most ')[1].split(' characters')[0];
    setErr(otherIdentifierError, `Maximální délka identifikátoru je ${limit} znaků.`);
    return;
  }
  if (errorStr.includes('other_identifier must not contain the reserved word:')) {
    const reservedWord = errorStr.split('reserved word: ')[1];
    setErr(otherIdentifierError, `Identifikátor nesmí obsahovat: ${reservedWord}`);
    return;
  }

  if (errorStr.includes('change_balance_by_must_be_more_than_or_equal_to')) {
    let limit = errorStr.split('change_balance_by_must_be_more_than_or_equal_to_');
    limit = limit[1];
    setErr(changeBalanceByError, `Změna může být minimálně ${limit} Kč.`);
    return;
  }
  if (errorStr.includes('change_balance_by_must_be_less_than_or_equal_to')) {
    let limit = errorStr.split('change_balance_by_must_be_less_than_or_equal_to_');
    limit = limit[1];
    setErr(changeBalanceByError, `Změna může být maximálně ${limit} Kč.`);
    return;
  }
  if (errorStr.includes('new_balance_must_be_more_than_or_equal_to')) {
    let limit = errorStr.split('new_balance_must_be_more_than_or_equal_to_');
    limit = limit[1];
    setErr(setNewBalanceError, `Nový zůstatek může být minimálně ${limit} Kč.`);
    return;
  }
  if (errorStr.includes('new_balance_must_be_less_than_or_equal_to')) {
    let limit = errorStr.split('new_balance_must_be_less_than_or_equal_to_');
    limit = limit[1];
    setErr(setNewBalanceError, `Nový zůstatek může být maximálně ${limit} Kč.`);
    return;
  }

  setErr(generalError, errorStr); /////
}


export function showDeleteUserFormErrors(error) {
  const generalError = document.querySelector('#delete-user-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();

  switch (errorStr) {
    case 'unexpected_error':
    case 'internal_server_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'no_selected_event':
      setErr(generalError, 'Není vybraná akce.');
      return;
    case 'no_selected_booth':
      setErr(generalError, 'Není vybraný stánek.');
      return;
    case 'invalid_booth_type':
      setErr(generalError, 'Neplatný typ stánku.');
      return;
    case 'invalid_user_id':
      setErr(generalError, 'ID uživatele není správné.');
      return;
    case 'missing_user_id':
      setErr(generalError, 'Chybí ID uživatele.');
      return;
    case 'user_not_found':
      setErr(generalError, 'Uživatel nebyl nalezen.');
      return;
    default:
      break;
  }

  setErr(generalError, errorStr); /////
}


export function showEditWalletFormErrors(error) {
  const changeBalanceByError = document.querySelector('#edit-wallet-change-balance-by-error');
  const setNewBalanceError = document.querySelector('#edit-wallet-set-new-balance-error');
  const generalError = document.querySelector('#edit-wallet-general-error');

  const setErr = (el, text) => {
    if (!el) return;
    el.innerHTML = escapeHTML(String(text));
    el.classList.add('show-form-error');
  };

  if (!error) {
    setErr(generalError, 'Něco se nepovedlo. Zkuste to prosím později.');
    return;
  }

  const errorStr = String(error).toLowerCase().trim();

  switch (errorStr) {
    case 'unexpected_error':
    case 'internal_server_error':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'no_selected_event':
      setErr(generalError, 'Není vybraná akce.');
      return;
    case 'no_selected_booth':
      setErr(generalError, 'Není vybraný stánek.');
      return;
    case 'invalid_booth_type':
      setErr(generalError, 'Neplatný typ stánku.');
      return;
    case 'missing_tag_id':
      setErr(generalError, 'Chybí ID karty.');
      return;
    case 'wallet_not_found':
      setErr(generalError, 'Karta nebyla nalezena.');
      return;
    case 'change_balance_by_must_be_a_number':
      setErr(changeBalanceByError, 'Změna musí být číslo.');
      return;
    case 'change_balance_by_must_be_a_whole_number':
      setErr(changeBalanceByError, 'Změna musí být celé číslo.');
      return;
    case 'new_balance_must_be_a_number':
      setErr(setNewBalanceError, 'Nový zůstatek musí být číslo.');
      return;
    case 'new_balance_must_be_a_whole_number':
      setErr(setNewBalanceError, 'Nový zůstatek musí být celé číslo.');
      return;
    case 'change_balance_by_and_new_balance_do_not_match':
      setErr(generalError, 'Změna a nový zůstatek se neshodují.');
      return;
    case 'changes_do_not_match_balance_czk':
      setErr(generalError, 'Změny neodpovídají aktuálnímu zůstatku.');
      return;
    case 'wallet_balance_czk_is_not_enough':
      setErr(generalError, 'Nedostatek peněz na kartě.');
      return;
    case 'resulting_wallet_balance_czk_is_too_high':
      setErr(generalError, 'Výsledný zůstatek je příliš vysoký.');
      return;
    case 'missing_idempotency_key':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    case 'idempotency_key_data_conflict':
      setErr(generalError, 'Něco se nepovedlo.');
      return;
    default:
      break;
  }

  if (errorStr.includes('change_balance_by_must_be_more_than_or_equal_to')) {
    let limit = errorStr.split('change_balance_by_must_be_more_than_or_equal_to_');
    limit = limit[1];
    setErr(changeBalanceByError, `Změna může být minimálně ${limit} Kč.`);
    return;
  }
  if (errorStr.includes('change_balance_by_must_be_less_than_or_equal_to')) {
    let limit = errorStr.split('change_balance_by_must_be_less_than_or_equal_to_');
    limit = limit[1];
    setErr(changeBalanceByError, `Změna může být maximálně ${limit} Kč.`);
    return;
  }
  if (errorStr.includes('new_balance_must_be_more_than_or_equal_to')) {
    let limit = errorStr.split('new_balance_must_be_more_than_or_equal_to_');
    limit = limit[1];
    setErr(setNewBalanceError, `Nový zůstatek může být minimálně ${limit} Kč.`);
    return;
  }
  if (errorStr.includes('new_balance_must_be_less_than_or_equal_to')) {
    let limit = errorStr.split('new_balance_must_be_less_than_or_equal_to_');
    limit = limit[1];
    setErr(setNewBalanceError, `Nový zůstatek může být maximálně ${limit} Kč.`);
    return;
  }

  setErr(generalError, errorStr); /////
}


export function showMoneyToExchangeModal(balanceChangedBy) {
  let html = '';

  if (balanceChangedBy <= 0) {
    html = `
      <div class="modal">
        <header>
          <h2>Peníze k vrácení zákazníkovi</h2>
          <button class="close-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <div class="money-to-exchange">${-balanceChangedBy} Kč</div>
      </div>
    `;
  } else if (balanceChangedBy > 0) {
    html = `
      <div class="modal">
        <header>
          <h2>Peníze k zaplacení zákazníkem</h2>
          <button class="close-modal cross-close">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
              <path d="M18 6L6 18M6 6l12 12" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
        </header>
        <div class="money-to-exchange">${balanceChangedBy} Kč</div>
      </div>
    `;
  }

  const overlay = document.createElement('div');
  overlay.classList.add('overlay');
  overlay.innerHTML = html;

  document.body.appendChild(overlay);
}