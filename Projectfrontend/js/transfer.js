/**
 * CryptoVault - Transfer
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    initTransfer();
});

async function initTransfer() {
    await loadBalance();
    const searchInput = document.getElementById('recipientSearch');
    if (searchInput) {
        searchInput.addEventListener('input', Utils.debounce(lookupRecipient, 400));
    }
    document.getElementById('transferForm')?.addEventListener('submit', handleTransfer);
    document.getElementById('coinSelect')?.addEventListener('change', () => {
        const coin = document.getElementById('coinSelect').value;
        document.getElementById('amountLabel').textContent = `Amount (${coin})`;
        loadBalance(coin);
    });
}

async function loadBalance(coin) {
    if (!coin) coin = document.getElementById('coinSelect')?.value || 'USDT';
    try {
        const data = await API.getBalance(coin);
        const bal = parseFloat(data.balance || data.available_balance || 0);
        document.getElementById('availableBalance').textContent =
            `${Utils.formatCrypto(bal, coin === 'USDT' ? 2 : 6)} ${coin}`;
    } catch (e) { console.error(e); }
}

async function lookupRecipient() {
    const input = document.getElementById('recipientSearch');
    const result = document.getElementById('recipientResult');
    if (!input || !result) return;
    const username = input.value.trim();
    if (username.length < 2) { result.innerHTML = ''; return; }
    try {
        const data = await API.lookupUser(username);
        if (data.found) {
            result.innerHTML = `<div class="recipient-found"><i class="fas fa-check-circle text-green"></i> <strong>${data.username}</strong> found</div>`;
            result.dataset.username = data.username;
        } else {
            result.innerHTML = '<div class="recipient-not-found text-red"><i class="fas fa-times-circle"></i> User not found</div>';
            result.dataset.username = '';
        }
    } catch (e) {
        result.innerHTML = '<div class="text-muted">Error looking up user</div>';
        result.dataset.username = '';
    }
}

async function handleTransfer(e) {
    e.preventDefault();
    const recipientResult = document.getElementById('recipientResult');
    const username = recipientResult?.dataset.username;
    if (!username) { Utils.showError('Please search and select a valid recipient'); return; }
    const amount = parseFloat(document.getElementById('transferAmount').value);
    const coin = document.getElementById('coinSelect')?.value || 'USDT';
    const description = document.getElementById('transferDesc')?.value || '';
    if (!amount || amount <= 0) { Utils.showError('Enter a valid amount'); return; }
    const btn = document.querySelector('#transferForm button[type="submit"]');
    Utils.setBtnLoading(btn);
    try {
        await API.sendMoney(username, amount, description, coin);
        Utils.showSuccess(`Sent ${Utils.formatAmount(amount, coin)} to ${username}`);
        document.getElementById('transferForm').reset();
        recipientResult.innerHTML = '';
        recipientResult.dataset.username = '';
        await loadBalance();
    } catch (e) { Utils.showError(e.message); }
    finally { Utils.setBtnLoading(btn, false); }
}
