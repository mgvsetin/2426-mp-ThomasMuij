import { cloneData } from "../general/cache.js";
import { BoothNotSelectedError, EventNotSelectedError, InvalidBoothTypeError, UnauthorizedRedirectError, UnexpectedError } from "../general/errors.js";
import { escapeHTML } from "../general/html_display_utils.js";
import { markSelectedRow } from "../general/table_utils.js";
import { lastReadCardId, removeReadCard, renderCard } from "./cards.js";
import { changeSelectedCode } from "./phone_number_input.js";
import { getWallets } from "./wallets.js";


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

const openUserCardsModalBtn = document.querySelector('#open-user-cards-modal');
const saveUserFormBtn = document.querySelector('#save-user-form');

let selectedUserForUpdate;

const orderBy = { key: '', ascending: true };

const cache_time_ms = 60 * 1000; // 1 minuta
// maybe figure out cache max time so that the slow doenst have to happen

const _usersCache = {
  users: null,
  expiry: 0
};

let _getUsersPromise = null;

editUserFormOnChange();


function getUsers() {
  if (_usersCache.users && _usersCache.expiry > Date.now()) {
    return Promise.resolve(cloneData(_usersCache.users));
  }

  if (_getUsersPromise) return _getUsersPromise;

  _getUsersPromise = (async () => {
    try {
      const response = await fetch('/api/users');

      if (response.status === 401) {
        const json = await response.json();
        window.location.href = json.redirect_url;
        throw new UnauthorizedRedirectError(json.redirect_url);
      }

      const resData = await response.json();

      console.log(resData);

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

      _usersCache.users = resData.users;
      _usersCache.expiry = Date.now() + cache_time_ms;

      // {
      //   "email": "pavel.struhař@gmail.com",
      //   "first_name": "Pavel_Ev1",
      //   "id": "01000000-0000-0000-0000-000000000001",
      //   "last_name": "Struhař",
      //   "other_identifier": null,
      //   "phone_number": "+420123456789",
      //   "phone_number_country_code": "+420",
      //   "phone_number_international": "+420 123456789",
      //   "phone_number_national": "123456789",
      //   "phone_number_national_significant_number": "123456789"
      // }

      return cloneData(_usersCache.users);

    } finally {
      _getUsersPromise = null;
    }
  })();

  return _getUsersPromise;
}


function resetUsersCache() {
  _usersCache.users = null;
  _usersCache.expiry = 0;
}


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

  const firstNameSearch = firstNameInput.value.toLowerCase().trim().replace(/\s/g, '');
  const lastNameSearch = lastNameInput.value.toLowerCase().trim().replace(/\s/g, '');
  const emailSearch = emailInput.value.toLowerCase().trim().replace(/\s/g, '');
  // country code je vynechaný schválně
  const phoneNumberSearch = phoneNumberInput.value.toLowerCase().trim().replace(/\s/g, '');
  const otherIdentifierSearch = otherIdentifierInput.value.toLowerCase().trim().replace(/\s/g, '');

  const queries = searchQuery.split(/\s+/);

  const addSearch = (search, searchKey) => {
    if (!search) return;
    queries.push(`${searchKey}=${search}`)
  }

  addSearch(firstNameSearch, 'first_name');
  addSearch(lastNameSearch, 'last_name');
  addSearch(emailSearch, 'email');
  addSearch(phoneNumberSearch, 'phone_number');
  addSearch(otherIdentifierSearch, 'other_identifier');

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
  const users = await getUsers().catch((error) => {
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
    if ((!selectedUserForUpdate || selectedUserForUpdate.id !== user.id) && !userIsSearchedFor(user)) return;
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
  markSelectedRow(usersTableBody);

  if (selectedUserForUpdate) {
    const rowSelectedForUpdate = document.getElementById(selectedUserForUpdate.id);
    rowSelectedForUpdate.classList.add('selected-for-update');
  }
}


export async function selectUserForUpdate(userId) {
  userId = userId.trim();
  const users = await getUsers().catch(() => { });
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
  changeSelectedCode('');
  phoneNumberInput.value = '';
  otherIdentifierInput.value = '';

  const selectedRow = document.querySelector('tr.selected-for-update');
  if (selectedRow) selectedRow.classList.remove('selected-for-update');

  selectedUserForUpdate = null;
  await editUserFormOnChange();
  renderUsers();
}


export async function editUserFormOnChange(inputEvent = null) {
  const [users, wallet] = await Promise.all([
    getUsers().catch(() => { }),
    renderCard().catch(() => { })
  ]);

  if (wallet && wallet.owner_id && wallet.owner_id !== userIdInput.value.toLowerCase().trim()) {
    await selectUserForUpdate(wallet.owner_id);
  }

  const userId = userIdInput.value.trim();
  const firstName = firstNameInput.value.toLowerCase().trim();
  const lastName = lastNameInput.value.toLowerCase().trim();
  const email = emailInput.value.toLowerCase().trim();
  const countryCode = countryCodeInput.value.toLowerCase().trim();
  const phoneNumber = phoneNumberInput.value.toLowerCase().trim();
  const otherIdentifier = otherIdentifierInput.value.toLowerCase().trim();

  const user = users.find((user) => { return user.id === userId; });

  const firstNamesMatch = user?.first_name.toLowerCase() === firstName;
  const lastNamesMatch = user?.last_name.toLowerCase() === lastName;
  const emailsMatch = user?.email === email;
  const phoneNumbersMatch = user?.phone_number === (countryCode && phoneNumber ? `${countryCode}${phoneNumber}` : null);
  const otherIdentifiersMatch = user?.other_identifier === (otherIdentifier ? otherIdentifier : null);

  const valuesMatch = firstNamesMatch && lastNamesMatch && emailsMatch && phoneNumbersMatch && otherIdentifiersMatch;

  if (user && valuesMatch) {
    saveUserFormBtn.textContent = 'Žádná změna';
    saveUserFormBtn.setAttribute('user-job', '');
    openUserCardsModalBtn.disabled = false;
  } else if (user && !valuesMatch) {
    saveUserFormBtn.textContent = 'Upravit';
    saveUserFormBtn.setAttribute('user-job', 'edit');
    openUserCardsModalBtn.disabled = false;
  } else {
    openUserCardsModalBtn.disabled = true;
    if (userId) {
      userIdInput.value = '';
      const selectedRow = document.querySelector('tr.selected-for-update');
      if (selectedRow) selectedRow.classList.remove('selected-for-update');
      selectedUserForUpdate = null;
    }

    saveUserFormBtn.textContent = 'Vytvořit';
    saveUserFormBtn.setAttribute('user-job', 'create');
  }

  if (wallet) {
    if (inputEvent && inputEvent.target === changeBalanceByInput) {
      const changeBalanceBy = Number(changeBalanceByInput.value);
      if (!isNaN(changeBalanceBy)) {
        const newBalance = wallet.balance_czk + changeBalanceBy;
        setNewBalanceInput.value = newBalance;
        changeBalanceByInput.value = changeBalanceBy; // pro 0
      }
    }

    if (inputEvent && inputEvent.target === setNewBalanceInput) {
      const newBalance = Number(setNewBalanceInput.value);

      if (!isNaN(newBalance)) {
        const changeBalanceBy = newBalance - wallet.balance_czk;
        changeBalanceByInput.value = changeBalanceBy;
        setNewBalanceInput.value = newBalance; // pro 0
      }
    }

    if (wallet.owner_id === userId && wallet.balance_czk === Number(setNewBalanceInput.value)) {
      saveUserFormBtn.setAttribute('card-job', '');
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
  const users = await getUsers().catch(() => { });
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
        <input type="hidden" name="id" value="${id}"/>
        <div class="form-row">
          <div>Opravdu chcete smazat uživatele "${escapeHTML(user.first_name)} ${escapeHTML(user.last_name)}"?</div>
        </div>

        <div class="form-row">
          <div id="delete-user-general-error" class="form-error"></div>
        </div>

        <div class="modal-actions">
          <button type="button" class="cancel-form close-modal">Zrušit</button>
          <button type="submit" class="save-form user-form-delete-button">Smazat</button>
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


export async function openUserCardsModal(userId) {
  userId = userId.trim();
  const users = await getUsers().catch(() => { });
  if (!users) return;
  const user = users.find(user => user.id === userId);
  if (!user) return;

  const wallets = await getWallets().catch((error) => {
    // maybe display some error
  });
  if (!wallets) return;
  
  const userWallets = wallets.filter((wallet) => { wallet.owner_id === userId });

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
        <input type="hidden" name="id" value="${userId}"/>
        <div class="form-row">
          <div>Opravdu chcete smazat uživatele "${escapeHTML(user.first_name)} ${escapeHTML(user.last_name)}"?</div>
        </div>

        <div class="form-row">
          <div id="delete-user-general-error" class="form-error"></div>
        </div>

        <div class="modal-actions">
          <button type="button" class="cancel-form close-modal">Zrušit</button>
          <button type="submit" class="save-form user-form-delete-button">Smazat</button>
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