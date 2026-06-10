/**
 * CryptoVault - Transactions
 */
let currentOffset = 0;
const PAGE_SIZE = 20;

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    initTransactions();
});

async function initTransactions() {
    document.getElementById('filterType')?.addEventListener('change', () => { currentOffset = 0; loadTransactions(); });
    document.getElementById('filterTxType')?.addEventListener('change', () => { currentOffset = 0; loadTransactions(); });
    document.getElementById('prevPage')?.addEventListener('click', () => { if (currentOffset >= PAGE_SIZE) { currentOffset -= PAGE_SIZE; loadTransactions(); } });
    document.getElementById('nextPage')?.addEventListener('click', () => { currentOffset += PAGE_SIZE; loadTransactions(); });
    await loadTransactions();
}

async function loadTransactions() {
    const container = document.getElementById('transactionsList');
    if (!container) return;
    Utils.showLoading(container);
    try {
        const data = await API.getTransactions(PAGE_SIZE, currentOffset);
        const txs = data.transactions || [];
        const filterType = document.getElementById('filterType')?.value || '';
        const filterTxType = document.getElementById('filterTxType')?.value || '';
        const filtered = txs.filter(t => {
            if (filterType === 'credit' && !t.is_credit) return false;
            if (filterType === 'debit' && t.is_credit) return false;
            if (filterTxType && (t.type || '').toLowerCase() !== filterTxType) return false;
            return true;
        });
        renderTransactions(filtered);
        const pageNum = Math.floor(currentOffset / PAGE_SIZE) + 1;
        document.getElementById('pageInfo').textContent = `Page ${pageNum}`;
        document.getElementById('prevPage').disabled = currentOffset === 0;
        document.getElementById('nextPage').disabled = txs.length < PAGE_SIZE;
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-center">Failed to load transactions</p>';
    }
}

function renderTransactions(txs) {
    const container = document.getElementById('transactionsList');
    if (!txs.length) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-receipt"></i><p>No transactions found</p></div>';
        return;
    }
    let html = '';
    for (const tx of txs) {
        const isCredit = tx.is_credit;
        const typeCls = isCredit ? 'credit' : 'debit';

        // Determine a human-readable label from the actual transaction type
        let typeLabel = '';
        let typeIcon = '';
        const rawType = (tx.type || '').toLowerCase();
        if (rawType === 'deposit') {
            typeLabel = 'Deposit';
            typeIcon = 'fa-arrow-down';
        } else if (rawType === 'withdrawal') {
            typeLabel = 'Withdrawal';
            typeIcon = 'fa-arrow-up';
        } else if (rawType === 'transfer' && isCredit) {
            typeLabel = 'Received';
            typeIcon = 'fa-arrow-down';
        } else if (rawType === 'transfer') {
            typeLabel = 'Sent';
            typeIcon = 'fa-arrow-up';
        } else if (rawType === 'interest') {
            typeLabel = 'Earn Interest';
            typeIcon = 'fa-percent';
        } else {
            typeLabel = isCredit ? 'Credit' : 'Debit';
            typeIcon = isCredit ? 'fa-arrow-down' : 'fa-arrow-up';
        }

        const amountCls = isCredit ? 'text-green' : 'text-red';
        const sign = isCredit ? '+' : '-';
        const coin = tx.coin || 'USDT';
        const txId = tx.tx_hash ? Utils.truncateAddress(tx.tx_hash) : ('Tx-' + (tx.id || '').toString().slice(0, 8));
        const txDate = tx.timestamp || tx.created_at || new Date().toISOString();
        const desc = tx.description || typeLabel;
        html += `
        <div class="tx-card-item">
            <div class="tx-card-top">
                <div class="tx-top-left">
                    <span class="tx-type-badge ${typeCls}"><i class="fas ${typeIcon}"></i> ${typeLabel}</span>
                    ${Utils.getCoinBadge(coin)}
                </div>
                <span class="tx-id">${txId}</span>
            </div>
            <div class="tx-card-details">
                <span>${desc}</span>
                <span>Date: ${Utils.formatDate(txDate)}</span>
            </div>
            <div class="tx-card-bottom">
                <span class="tx-card-total ${amountCls}">${sign} ${Utils.formatAmount(Math.abs(tx.amount), coin)}</span>
                <div class="tx-card-arrow"><i class="fas fa-chevron-right"></i></div>
            </div>
        </div>`;
    }
    container.innerHTML = html;
}
