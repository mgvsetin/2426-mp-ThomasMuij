import { escapeHTML } from "../general/html_display_utils.js";
import { formatDateTimeISOToDisplay } from "../general/date_utils.js";
import { handleUnauthorizedRedirect } from "../general/api_utils.js";

const transactionsTableBody = document.querySelector('#transactions-table-body');
const cardsTableBody = document.querySelector('#cards-table-body');
const usersTableBody = document.querySelector('#users-table-body');

const eventNameEl = document.querySelector('#event-name');
const eventStartAtEl = document.querySelector('#event-start-at');
const eventEndAtEl = document.querySelector('#event-end-at');
const eventCreatedAtEl = document.querySelector('#event-created-at');

const totalTransactionsEl = document.querySelector('#total-transactions');
const totalDepositsEl = document.querySelector('#total-deposits');
const totalDepositsCountEl = document.querySelector('#total-deposits-count');
const totalWithdrawalsEl = document.querySelector('#total-withdrawals');
const totalWithdrawalsCountEl = document.querySelector('#total-withdrawals-count');
const totalPaymentsEl = document.querySelector('#total-payments');
const totalPaymentsCountEl = document.querySelector('#total-payments-count');
const totalRefundsEl = document.querySelector('#total-refunds');
const totalRefundsCountEl = document.querySelector('#total-refunds-count');
const totalBalanceEl = document.querySelector('#total-balance');
const totalCardsCountEl = document.querySelector('#total-cards-count');

loadPage();

async function loadPage() {
  // /events/<event_id>/transaction-history
  const pathParts = window.location.pathname.split('/');
  const eventIdIndex = pathParts.indexOf('events') + 1;

  if (eventIdIndex <= 0) {
    showError('Neplatná URL.');
    return;
  }

  const eventId = pathParts[eventIdIndex];

  if (!eventId) {
    showError('Chybí ID akce.');
    return;
  }

  try {
    const response = await fetch(`/api/events/${eventId}/transaction-history`);

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

    await loadEventInfo(eventId);

    const transactions = data.event_transaction_history || [];
    renderTransactions(transactions);
    renderCards(transactions);
    renderUsers(transactions);

  } catch (err) {
    console.error('Error loading transaction history:', err);
    showError('Nepodařilo se načíst historii transakcí.');
  }
}

async function loadEventInfo(eventId) {
  try {
    const eventResponse = await fetch('/api/events');
    if (eventResponse.ok) {
      const eventData = await eventResponse.json();
      const event = eventData.events?.find(e => e.id === eventId);
      if (event) {
        eventNameEl.textContent = event.name || '-';
        eventStartAtEl.textContent = event.start_at ? formatDateTimeISOToDisplay(event.start_at) : '-';
        eventEndAtEl.textContent = event.end_at ? formatDateTimeISOToDisplay(event.end_at) : '-';
        eventCreatedAtEl.textContent = event.created_at ? formatDateTimeISOToDisplay(event.created_at) : '-';

        document.title = `Historie transakcí - ${event.name}`;
      }
    }
  } catch (err) {
    console.error('Error loading event info:', err);
  }
}

function renderUsers(transactions) {
  if (!transactions || transactions.length === 0) {
    usersTableBody.innerHTML = '<tr><td colspan="8" class="empty-message">Žádní uživatelé.</td></tr>';
    return;
  }

  const userMap = new Map();

  transactions.forEach(transaction => {
    const userName = `${transaction.user_first_name || '?'} ${transaction.user_last_name || '?'}`;

    if (!userMap.has(userName)) {
      userMap.set(userName, {
        userName: userName,
        depositsCount: 0,
        depositsTotal: 0,
        withdrawalsCount: 0,
        withdrawalsTotal: 0,
        paymentsCount: 0,
        paymentsTotal: 0,
        refundsCount: 0,
        refundsTotal: 0,
        totalTransactions: 0,
        cardBalances: new Map()
      });
    }

    const user = userMap.get(userName);
    const amountCzk = transaction.amount_czk || 0;
    const transactionType = transaction.transaction_type || 'unknown';
    const tagId = transaction.tag_id || 'unknown';

    user.totalTransactions++;
    user.cardBalances.set(tagId, transaction.balance_after || 0);

    if (transactionType === 'payment') {
      user.paymentsCount++;
      user.paymentsTotal += amountCzk;
    } else if (transactionType === 'refund') {
      user.refundsCount++;
      user.refundsTotal += amountCzk;
    } else if (transactionType === 'balance-change') {
      if (amountCzk > 0) {
        user.depositsCount++;
        user.depositsTotal += amountCzk;
      } else if (amountCzk < 0) {
        user.withdrawalsCount++;
        user.withdrawalsTotal += amountCzk;
      }
    }
  });

  const users = Array.from(userMap.values());
  let rows = '';

  users.forEach((user, index) => {
    const totalBalance = Array.from(user.cardBalances.values()).reduce((sum, b) => sum + b, 0);
    rows += `
      <tr>
        <td>${index + 1}</td>
        <td class="user-name">${escapeHTML(user.userName)}</td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${user.depositsTotal} Kč</span>
            <span class="stat-count">transakce: ${user.depositsCount}×</span>
          </div>
        </td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${user.withdrawalsTotal} Kč</span>
            <span class="stat-count">transakce: ${user.withdrawalsCount}×</span>
          </div>
        </td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${user.paymentsTotal} Kč</span>
            <span class="stat-count">transakce: ${user.paymentsCount}×</span>
          </div>
        </td>
        <td>
          <div class="stat-group">
            <span class="stat-amount">${user.refundsTotal} Kč</span>
            <span class="stat-count">transakce: ${user.refundsCount}×</span>
          </div>
        </td>
        <td>${user.totalTransactions}</td>
        <td><strong>${totalBalance} Kč</strong></td>
      </tr>
    `;
  });

  usersTableBody.innerHTML = rows;
}

function renderCards(transactions) {
  if (!transactions || transactions.length === 0) {
    cardsTableBody.innerHTML = '<tr><td colspan="8" class="empty-message">Žádné karty.</td></tr>';
    return;
  }

  // Group transactions by tag_id
  const cardMap = new Map();

  transactions.forEach(transaction => {
    const tagId = transaction.tag_id || 'unknown';
    // const userName = `${transaction.user_first_name || '?'} ${transaction.user_last_name || '?'}`;

    if (!cardMap.has(tagId)) {
      cardMap.set(tagId, {
        tagId: tagId,
        // userName: userName,
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
        card.depositsTotal += (amountCzk);
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
        <!-- <td class="user-name">${escapeHTML(card.userName)}</td> -->
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

function renderTransactions(transactions) {
  if (!transactions || transactions.length === 0) {
    transactionsTableBody.innerHTML = '<tr><td colspan="11" class="empty-message">Žádné transakce.</td></tr>';
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
    const userName = `${transaction.user_first_name || '?'} ${transaction.user_last_name || '?'}`;

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

    rows += `
      <tr>
        <td>${index + 1}</td>
        <td class="datetime">${occurredAt}</td>
        <td class="user-name">${escapeHTML(userName)}</td>
        <td class="card-tag">${escapeHTML(tagId)}</td>
        <td><span class="transaction-type ${typeClass}">${typeDisplay}</span></td>
        <td class="${amountClass}">${amountDisplay}</td>
        <td>${balanceBefore}</td>
        <td>${balanceAfter}</td>
        <td>${escapeHTML(boothName)}</td>
        <td>${escapeHTML(performedByUsername)}</td>
        <td>${productsHtml}</td>
      </tr>
    `;
  });

  transactionsTableBody.innerHTML = rows;

  totalTransactionsEl.textContent = transactions.length;
  totalDepositsEl.textContent = `${totalDeposits} Kč`;
  totalDepositsCountEl.textContent = `${totalDepositsCount} ${[1, 2, 3, 4].includes(totalDepositsCount) ? 'transakce' : 'transakcí'}`;
  totalWithdrawalsEl.textContent = `${totalWithdrawals} Kč`;
  totalWithdrawalsCountEl.textContent = `${totalWithdrawalsCount} ${[1, 2, 3, 4].includes(totalWithdrawalsCount) ? 'transakce' : 'transakcí'}`;
  totalPaymentsEl.textContent = `${totalPayments} Kč`;
  totalPaymentsCountEl.textContent = `${totalPaymentsCount} ${[1, 2, 3, 4].includes(totalPaymentsCount) ? 'transakce' : 'transakcí'}`;
  totalRefundsEl.textContent = `${totalRefunds} Kč`;
  totalRefundsCountEl.textContent = `${totalRefundsCount} ${[1, 2, 3, 4].includes(totalRefundsCount) ? 'transakce' : 'transakcí'}`;
  totalBalanceEl.textContent = `${totalBalance} Kč`;
  totalCardsCountEl.textContent = `${cardBalances.size} ${cardBalances.size === 1 ? 'karta' : 0 < cardBalances.size && cardBalances.size < 5 ? 'karty' : 'karet'}`;
}

function showError(message) {
  transactionsTableBody.innerHTML = `<tr><td colspan="10" class="error-message">${escapeHTML(message)}</td></tr>`;
  cardsTableBody.innerHTML = `<tr><td colspan="9" class="error-message">${escapeHTML(message)}</td></tr>`;
  usersTableBody.innerHTML = `<tr><td colspan="8" class="error-message">${escapeHTML(message)}</td></tr>`;
}
