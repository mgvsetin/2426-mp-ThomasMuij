import { escapeHTML } from "../general/html_display_utils.js";
import { formatDateTimeISOToDisplay } from "../general/date_utils.js";
import { handleUnauthorizedRedirect } from "../general/api_utils.js";
import { openModal, closeModal } from "../general/modals_forms.js";

const transactionsTableBody = document.querySelector('#transactions-table-body');
const cardsTableBody = document.querySelector('#cards-table-body');

const userFirstNameEl = document.querySelector('#user-first-name');
const userLastNameEl = document.querySelector('#user-last-name');
const userEmailEl = document.querySelector('#user-email');
const userPhoneEl = document.querySelector('#user-phone');
const userOtherIdentifierEl = document.querySelector('#user-other-identifier');
const eventNameEl = document.querySelector('#event-name');

const totalTransactionsEl = document.querySelector('#total-transactions');
const totalDepositsEl = document.querySelector('#total-deposits');
const totalDepositsCountEl = document.querySelector('#total-deposits-count');
const totalWithdrawalsEl = document.querySelector('#total-withdrawals');
const totalWithdrawalsCountEl = document.querySelector('#total-withdrawals-count');
const totalPaymentsEl = document.querySelector('#total-payments');
const totalPaymentsCountEl = document.querySelector('#total-payments-count');
const totalRefundsEl = document.querySelector('#total-refunds');
const totalRefundsCountEl = document.querySelector('#total-refunds-count');
const nonRefundedPaymentsEl = document.querySelector('#non-refunded-payments');
const nonRefundedPaymentsCountEl = document.querySelector('#non-refunded-payments-count');
const totalBalanceEl = document.querySelector('#total-balance');
const totalCardsCountEl = document.querySelector('#total-cards-count');

loadPage();

/**
 * Načte data o transakcích uživatele a informace o uživateli a akci.
 * @returns {Promise<void>}
 */
async function loadPage() {
  // /events/<event_id>/users/<user_id>/transaction-history
  const pathParts = window.location.pathname.split('/');
  const eventIdIndex = pathParts.indexOf('events') + 1;
  const userIdIndex = pathParts.indexOf('users') + 1;
  
  if (eventIdIndex <= 0 || userIdIndex <= 0) {
    showError('Neplatná URL.');
    return;
  }

  const eventId = pathParts[eventIdIndex];
  const userId = pathParts[userIdIndex];

  if (!eventId || !userId) {
    showError('Chybí ID akce nebo uživatele.');
    return;
  }

  try {
    const response = await fetch(`/api/events/${eventId}/users/${userId}/transaction-history`);

    await handleUnauthorizedRedirect(response);

    const data = await response.json();

    if (response.status === 400) {
      showError(data.error || 'Neplatný požadavek.');
      return;
    }

    if (response.status === 403) {
      showError('Nemáte oprávnění k zobrazení těchto dat.');
      return;
    }

    if (!response.ok) {
      showError('Nepodařilo se načíst data.');
      return;
    }

    await loadUserAndEventInfo(userId, eventId);

    const transactions = data.user_transaction_history || [];
    const canAdminRefund = data.can_admin_refund || false;
    renderTransactions(transactions, canAdminRefund);
    renderCards(transactions);

  } catch (err) {
    console.error('Error loading transaction history:', err);
    showError('Nepodařilo se načíst historii transakcí.');
  }
}

/**
 * Načte a zobrazí informace o uživateli a akci.
 * @param {string} userId - ID uživatele
 * @param {string} eventId - ID akce
 * @returns {Promise<void>}
 */
async function loadUserAndEventInfo(userId, eventId) {
  try {
    const userResponse = await fetch('/api/users');
    if (userResponse.ok) {
      const userData = await userResponse.json();
      const user = userData.users?.find(u => u.id === userId);
      if (user) {
        userFirstNameEl.textContent = user.first_name || '-';
        userLastNameEl.textContent = user.last_name || '-';
        userEmailEl.textContent = user.email || '-';
        userPhoneEl.textContent = user.phone_number_international || user.phone_number || '-';
        userOtherIdentifierEl.textContent = user.other_identifier || '-';
        
        document.title = `Historie transakcí - ${user.first_name} ${user.last_name}`;
      }
    }

    const eventResponse = await fetch('/api/events');
    if (eventResponse.ok) {
      const eventData = await eventResponse.json();
      const event = eventData.events?.find(e => e.id === eventId);
      if (event) {
        eventNameEl.textContent = event.name || '-';
      }
    }
  } catch (err) {
    console.error('Error loading user/event info:', err);
  }
}

/**
 * Vykreslí tabulku karet a jejich souhrnných statistik podle transakcí.
 * @param {Array<Object>} transactions - Pole transakcí
 */
function renderCards(transactions) {
  if (!transactions || transactions.length === 0) {
    cardsTableBody.innerHTML = '<tr><td colspan="8" class="empty-message">Žádné karty.</td></tr>';
    return;
  }

  // Group transactions by tag_id
  const cardMap = new Map();
  
  transactions.forEach(transaction => {
    const tagId = transaction.tag_id || 'unknown';
    
    if (!cardMap.has(tagId)) {
      cardMap.set(tagId, {
        tagId: tagId,
        depositsCount: 0,
        depositsTotal: 0,
        withdrawalsCount: 0,
        withdrawalsTotal: 0,
        paymentsCount: 0,
        paymentsTotal: 0,
        refundsCount: 0,
        refundsTotal: 0,
        totalTransactions: 0,
        finalBalance: 0
      });
    }
    
    const card = cardMap.get(tagId);
    const amountCzk = transaction.amount_czk || 0;
    const transactionType = transaction.transaction_type || 'unknown';
    
    card.totalTransactions++;
    card.finalBalance = transaction.balance_after || 0;
    
    if (transactionType === 'payment') {
      card.paymentsCount++;
      card.paymentsTotal += amountCzk;
    } else if (transactionType === 'refund') {
      card.refundsCount++;
      card.refundsTotal += amountCzk;
    } else if (transactionType === 'balance-change') {
      if (amountCzk > 0) {
        card.depositsCount++;
        card.depositsTotal += amountCzk;
      } else if (amountCzk < 0) {
        card.withdrawalsCount++;
        card.withdrawalsTotal += amountCzk;
      }
      // if amountCzk === 0, nepatří do deposists ani withdrawals
    }
  });


  const cards = Array.from(cardMap.values());
  let rows = '';

  cards.forEach((card, index) => {
    rows += `
      <tr>
        <td>${index + 1}</td>
        <td class="card-tag">${escapeHTML(card.tagId)}</td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${card.depositsTotal} Kč</span>
            <span class="stat-count">transakce: ${card.depositsCount}×</span>
          </div>
        </td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${card.withdrawalsTotal} Kč</span>
            <span class="stat-count">transakce: ${card.withdrawalsCount}×</span>
          </div>
        </td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${card.paymentsTotal} Kč</span>
            <span class="stat-count">transakce: ${card.paymentsCount}×</span>
          </div>
        </td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${card.refundsTotal} Kč</span>
            <span class="stat-count">transakce: ${card.refundsCount}×</span>
          </div>
        </td>
        <td>${card.totalTransactions}</td>
        <td><strong>${card.finalBalance} Kč</strong></td>
      </tr>
    `;
  });

  cardsTableBody.innerHTML = rows;
}

/**
 * Vykreslí tabulku transakcí a souhrnné statistiky.
 * @param {Array<Object>} transactions - Pole transakcí
 * @param {boolean} canAdminRefund - Zda má přihlášený zaměstnanec právo refundovat platby
 */
function renderTransactions(transactions, canAdminRefund = false) {
  if (canAdminRefund) {
    const theadRow = document.querySelector('#transactions-table thead tr');
    if (!theadRow.querySelector('.actions-header')) {
      const th = document.createElement('th');
      th.className = 'actions-header';
      th.textContent = 'Akce';
      theadRow.appendChild(th);
    }
  }

  const colspan = 10 + (canAdminRefund ? 1 : 0);

  if (!transactions || transactions.length === 0) {
    transactionsTableBody.innerHTML = `<tr><td colspan="${colspan}" class="empty-message">Žádné transakce.</td></tr>`;
    return;
  }

  let totalDeposits = 0;
  let totalDepositsCount = 0;
  let totalWithdrawals = 0;
  let totalWithdrawalsCount = 0;
  let totalPayments = 0;
  let totalPaymentsCount = 0;
  let totalRefunds = 0;
  let totalRefundsCount = 0;
  let totalBalance = 0;

  const cardBalances = new Map();
  transactions.forEach(transaction => {
    const tagId = transaction.tag_id || 'unknown';
    cardBalances.set(tagId, transaction.balance_after || 0);
  });
  totalBalance = Array.from(cardBalances.values()).reduce((sum, balance) => sum + balance, 0);

  let rows = '';
  transactions.forEach((transaction, index) => {
    const occurredAt = formatDateTimeISOToDisplay(transaction.occurred_at);
    const transactionType = transaction.transaction_type || 'unknown';
    const amountCzk = transaction.amount_czk || 0;
    const balanceBefore = transaction.balance_before || 0;
    const balanceAfter = transaction.balance_after || 0;
    const tagId = transaction.tag_id || '-';
    const boothName = transaction.booth_name || '-';
    const performedByUsername = transaction.performed_by_username || '-';

    let typeClass = '';
    let typeDisplay = '';
    
    if (transactionType === 'payment') {
      typeClass = 'payment';
      typeDisplay = 'Platba';
      totalPayments += amountCzk;
      totalPaymentsCount++;
    } else if (transactionType === 'refund') {
      typeClass = 'refund';
      typeDisplay = 'Vrácení';
      totalRefunds += amountCzk;
      totalRefundsCount++;
    } else if (transactionType === 'balance-change') {
      if (amountCzk > 0) {
        typeClass = 'deposit';
        typeDisplay = 'Vklad';
        totalDeposits += amountCzk;
        totalDepositsCount++;
      } else if (amountCzk < 0) {
        typeClass = 'withdrawal';
        typeDisplay = 'Výběr';
        totalWithdrawals += amountCzk;
        totalWithdrawalsCount++;
      } else {
        typeClass = 'no-change';
        typeDisplay = 'Bez změny';
      }
    } else {
      typeClass = 'unknown';
      typeDisplay = 'Neznámý';
    }

    let amountClass = 'amount-zero';
    let amountDisplay = amountCzk;
    if (amountCzk > 0) {
      amountClass = 'amount-positive';
      amountDisplay = `+${amountCzk}`;
    } else if (amountCzk < 0) {
      amountClass = 'amount-negative';
    }

    let productsHtml = '-';
    if (transaction.products_info && Array.isArray(transaction.products_info) && transaction.products_info.length > 0) {
      const productItems = transaction.products_info
        .map(p => `<div class="product-item">${escapeHTML(p.name || '')} (${p.quantity || 0}× ${p.price || 0} Kč)</div>`)
        .join('');
      productsHtml = `<div class="products-info">${productItems}</div>`;
    }

    let actionCell = '';
    if (canAdminRefund) {
      const btnHtml = (transactionType === 'payment' && !transaction.is_refunded)
        ? `<button class="refund-btn" data-transaction-id="${escapeHTML(String(transaction.id))}" data-amount="${amountCzk}">Refundovat</button>`
        : '';
      actionCell = `<td class="action-cell">${btnHtml}</td>`;
    }

    rows += `
      <tr>
        <td>${index + 1}</td>
        <td class="datetime">${occurredAt}</td>
        <td class="card-tag">${escapeHTML(tagId)}</td>
        <td><span class="transaction-type ${typeClass}">${typeDisplay}</span></td>
        <td class="${amountClass}">${amountDisplay}</td>
        <td>${balanceBefore}</td>
        <td>${balanceAfter}</td>
        <td>${escapeHTML(boothName)}</td>
        <td>${escapeHTML(performedByUsername)}</td>
        <td>${productsHtml}</td>
        ${actionCell}
      </tr>
    `;
  });

  transactionsTableBody.innerHTML = rows;

  if (canAdminRefund) {
    transactionsTableBody.addEventListener('click', handleRefundClick);
  }

  totalTransactionsEl.textContent = transactions.length;
  totalDepositsEl.textContent = `${totalDeposits} Kč`;
  totalDepositsCountEl.textContent = `${totalDepositsCount} ${[1, 2, 3, 4].includes(totalDepositsCount) ? 'transakce' : 'transakcí'}`;
  totalWithdrawalsEl.textContent = `${totalWithdrawals} Kč`;
  totalWithdrawalsCountEl.textContent = `${totalWithdrawalsCount} ${[1, 2, 3, 4].includes(totalWithdrawalsCount) ? 'transakce' : 'transakcí'}`;
  totalPaymentsEl.textContent = `${totalPayments} Kč`;
  totalPaymentsCountEl.textContent = `${totalPaymentsCount} ${[1, 2, 3, 4].includes(totalPaymentsCount) ? 'transakce' : 'transakcí'}`;
  totalRefundsEl.textContent = `${totalRefunds} Kč`;
  totalRefundsCountEl.textContent = `${totalRefundsCount} ${[1, 2, 3, 4].includes(totalRefundsCount) ? 'transakce' : 'transakcí'}`;
  const nonRefundedPayments = totalPayments + totalRefunds;
  const nonRefundedPaymentsCount = totalPaymentsCount - totalRefundsCount;
  nonRefundedPaymentsEl.textContent = `${nonRefundedPayments} Kč`;
  nonRefundedPaymentsCountEl.textContent = `${nonRefundedPaymentsCount} ${[1, 2, 3, 4].includes(nonRefundedPaymentsCount) ? 'transakce' : 'transakcí'}`;
  totalBalanceEl.textContent = `${totalBalance} Kč`;
  totalCardsCountEl.textContent = `${cardBalances.size} ${cardBalances.size === 1 ? 'karta' : 0 < cardBalances.size && cardBalances.size < 5 ? 'karty' : 'karet'}`;
}

/**
 * Zpracuje kliknutí na tlačítko refundace — otevře potvrzovací modál.
 * @param {MouseEvent} e
 */
function handleRefundClick(e) {
  const btn = e.target.closest('.refund-btn');
  if (!btn) return;

  const transactionId = btn.dataset.transactionId;
  const amount = parseInt(btn.dataset.amount, 10);
  const refundAmount = -amount;

  const overlay = openModal(`
    <header>
      <h2>Vrácení platby</h2>
    </header>
    <p>Opravdu chcete vrátit platbu <strong>${refundAmount} Kč</strong>?</p>
    <div class="form-error" id="admin-refund-error"></div>
    <div class="modal-actions">
      <button class="btn btn-ghost close-modal">Zrušit</button>
      <button class="btn btn-delete" id="confirm-admin-refund"
        data-transaction-id="${escapeHTML(transactionId)}"
        data-refund-amount="${refundAmount}">Vrátit</button>
    </div>
  `, false);

  overlay.addEventListener('click', async (e2) => {
    if (e2.target.closest('.close-modal')) {
      closeModal();
      return;
    }

    const confirmBtn = e2.target.closest('#confirm-admin-refund');
    if (!confirmBtn) return;

    confirmBtn.disabled = true;
    confirmBtn.textContent = 'Refunduji...';

    const errorEl = overlay.querySelector('#admin-refund-error');
    errorEl.textContent = '';
    errorEl.classList.remove('show-form-error');

    try {
      const formData = new FormData();
      formData.append('transaction-id', confirmBtn.dataset.transactionId);
      formData.append('idempotency-key', crypto.randomUUID());

      const response = await fetch('/api/transactions/admin-refund', {
        method: 'POST',
        body: formData
      });

      if (response.ok) {
        closeModal();
        window.location.reload();
        return;
      }

      const data = await response.json();
      errorEl.textContent = getAdminRefundErrorMessage(data.error);
      errorEl.classList.add('show-form-error');
    } catch {
      errorEl.textContent = 'Něco se nepovedlo. Zkuste to prosím později.';
      errorEl.classList.add('show-form-error');
    }

    confirmBtn.disabled = false;
    confirmBtn.textContent = 'Vrátit';
  });
}

/**
 * Vrátí čitelnou chybovou zprávu pro chybu admin refundace.
 * @param {string} error
 * @returns {string}
 */
function getAdminRefundErrorMessage(error) {
  switch (error) {
    case 'payment_transaction_not_found': return 'Platba nebyla nalezena.';
    case 'transaction_already_refunded': return 'Tato platba již byla vrácena.';
    case 'wallet_not_found': return 'Peněženka nebyla nalezena.';
    case 'resulting_wallet_balance_czk_is_too_high': return 'Výsledný zůstatek na kartě by byl příliš vysoký.';
    case 'insufficient_privileges': return 'Nemáte oprávnění k vrácení platby.';
    case 'idempotency_key_data_conflict': return 'Něco se nepovedlo. Zkuste to prosím znovu.';
    default: return 'Něco se nepovedlo. Zkuste to prosím později.';
  }
}

/**
 * Zobrazí chybovou zprávu v tabulkách transakcí a karet.
 * @param {string} message - Chybová zpráva
 */
function showError(message) {
  transactionsTableBody.innerHTML = `<tr><td colspan="99" class="error-message">${escapeHTML(message)}</td></tr>`;
  cardsTableBody.innerHTML = `<tr><td colspan="99" class="error-message">${escapeHTML(message)}</td></tr>`;
}