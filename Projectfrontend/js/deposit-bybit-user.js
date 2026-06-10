/**
 * CryptoVault - Receive from Bybit User
 */
let selectedUser = null;
let transferId = null;
let senderName = '';

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;

    document.getElementById('userSearch')?.addEventListener('input', Utils.debounce(searchUsers, 400));
    document.getElementById('requestBtn')?.addEventListener('click', submitRequest);
    document.getElementById('simulateApproveBtn')?.addEventListener('click', approveTransfer);
});

async function searchUsers() {
    const query = document.getElementById('userSearch').value.trim();
    const container = document.getElementById('searchResults');
    if (query.length < 2) { container.innerHTML = ''; return; }

    container.innerHTML = '<div class="loading" style="padding:12px;"><div class="spinner"></div></div>';
    try {
        const data = await API.searchBybitUsers(query);
        const users = data.users || [];
        if (!users.length) {
            container.innerHTML = '<p class="text-muted" style="font-size:0.85rem;padding:8px 0;">No users found</p>';
            return;
        }
        container.innerHTML = users.map(u => `
            <div class="user-search-result" data-username="${u.username}" data-name="${u.display_name}" data-uid="${u.bybit_uid || ''}">
                <div class="user-avatar-sm">${(u.display_name || u.username)[0].toUpperCase()}</div>
                <div class="user-search-info">
                    <div class="user-search-name">${u.display_name || u.username}</div>
                    <div class="user-search-meta">@${u.username}${u.bybit_uid ? ' · ' + u.bybit_uid : ''}</div>
                </div>
            </div>`).join('');

        container.querySelectorAll('.user-search-result').forEach(el => {
            el.addEventListener('click', () => selectUser(el));
        });
    } catch (e) {
        container.innerHTML = '<p class="text-muted">Search failed</p>';
    }
}

function selectUser(el) {
    document.querySelectorAll('.user-search-result').forEach(r => r.classList.remove('selected'));
    el.classList.add('selected');
    selectedUser = el.dataset.username;
    senderName = el.dataset.name;
    document.getElementById('selectedUser').style.display = 'block';
    document.getElementById('selectedAvatar').textContent = senderName[0].toUpperCase();
    document.getElementById('selectedName').textContent = senderName;
    document.getElementById('selectedMeta').textContent = `@${selectedUser}${el.dataset.uid ? ' · ' + el.dataset.uid : ''}`;
    document.getElementById('requestBtn').disabled = false;
}

async function submitRequest() {
    const amount = parseFloat(document.getElementById('expectedAmount').value);
    const coin = document.getElementById('transferCoin').value;
    if (!selectedUser) { Utils.showError('Select a sender'); return; }
    if (!amount || amount <= 0) { Utils.showError('Enter expected amount'); return; }

    const modal = document.getElementById('loadingModal');
    document.getElementById('loadingText').textContent = 'Sending request to ' + senderName + '...';
    modal.classList.add('active');
    Utils.setBtnLoading('#requestBtn');

    try {
        const data = await API.initBybitUserTransfer(selectedUser, amount, coin);
        transferId = data.transfer_id;
        senderName = data.sender_name || data.sender_username;
        await new Promise(r => setTimeout(r, 1800));
        modal.classList.remove('active');

        document.getElementById('formSection').style.display = 'none';
        document.getElementById('approvalSection').style.display = 'block';
        document.getElementById('simulateApproveBtn').style.display = 'flex';
        document.getElementById('approveBtnText').textContent = `${senderName} Has Sent the Crypto`;
        document.getElementById('processingText').textContent = `Awaiting confirmation from ${senderName}...`;
    } catch (e) {
        modal.classList.remove('active');
        Utils.showError(e.message);
    } finally {
        Utils.setBtnLoading('#requestBtn', false);
    }
}

async function approveTransfer() {
    if (!transferId) return;
    const modal = document.getElementById('loadingModal');
    document.getElementById('loadingText').textContent = 'Verifying transfer...';
    modal.classList.add('active');
    Utils.setBtnLoading('#simulateApproveBtn');

    try {
        await new Promise(r => setTimeout(r, 1500));
        const result = await API.approveBybitUserTransfer(transferId);
        modal.classList.remove('active');

        document.getElementById('stepProcessing').classList.remove('active');
        document.getElementById('stepProcessing').classList.add('done');
        document.getElementById('stepApproved').classList.add('done', 'active');
        document.getElementById('simulateApproveBtn').style.display = 'none';

        setTimeout(() => {
            document.getElementById('approvalSection').style.display = 'none';
            document.getElementById('successSection').style.display = 'block';
            document.getElementById('successMessage').textContent =
                `${senderName} sent ${Utils.formatAmount(result.amount, result.coin)}. Ref: ${result.reference}`;
            Utils.showSuccess('Transfer approved!');
        }, 800);
    } catch (e) {
        modal.classList.remove('active');
        Utils.showError(e.message);
    } finally {
        Utils.setBtnLoading('#simulateApproveBtn', false);
    }
}
