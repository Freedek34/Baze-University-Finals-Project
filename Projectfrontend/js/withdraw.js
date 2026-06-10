/**
 * CryptoVault - Withdraw Page
 */
let selectedCoin = 'USDT';
let selectedChain = '';
let selectedChainInfo = null;
let coinChains = [];

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    initWithdraw();
});

function initWithdraw() {
    // Asset selector
    document.querySelectorAll('.asset-option').forEach(opt => {
        opt.addEventListener('click', () => {
            document.querySelectorAll('.asset-option').forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            selectedCoin = opt.dataset.coin;
            selectedChain = '';
            selectedChainInfo = null;
            document.getElementById('withdrawFormCard').style.display = 'none';
            document.getElementById('coinLabel').textContent = `(${selectedCoin})`;
            loadNetworks(selectedCoin);
        });
    });

    document.getElementById('maxBtn')?.addEventListener('click', () => {
        // TODO: Load user's available balance for the coin and fill it in
        Utils.showInfo('MAX not available yet - enter amount manually');
    });

    document.getElementById('withdrawAmount')?.addEventListener('input', updateSummary);
    document.getElementById('withdrawBtn')?.addEventListener('click', handleWithdraw);

    loadNetworks(selectedCoin);
}

async function loadNetworks(coin) {
    const container = document.getElementById('networkSelector');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    try {
        const data = await API.getCoinInfo(coin);
        const coins = data.coins || [];
        const coinData = coins.find(c => c.coin === coin);

        if (coinData && coinData.chains && coinData.chains.length > 0) {
            coinChains = coinData.chains;
            let html = '';
            for (const chain of coinChains) {
                const withdrawEnabled = chain.chainWithdraw === '1' || chain.chainWithdraw === 1;
                html += `
                <div class="network-option ${!withdrawEnabled ? 'disabled' : ''}" 
                     data-chain="${chain.chainType}"
                     ${!withdrawEnabled ? 'title="Withdrawal suspended"' : ''}>
                    <div class="network-name">
                        <span class="chain-badge">${chain.chain}</span>
                        <span class="chain-type">${chain.chainType}</span>
                    </div>
                    <div class="network-meta">
                        <span class="meta-item">Fee: ${chain.withdrawFee} ${coin}</span>
                        <span class="meta-item">Min: ${chain.withdrawMin} ${coin}</span>
                    </div>
                    ${!withdrawEnabled ? '<span class="suspended-badge">Suspended</span>' : ''}
                </div>`;
            }
            container.innerHTML = html;

            container.querySelectorAll('.network-option:not(.disabled)').forEach(opt => {
                opt.addEventListener('click', () => {
                    container.querySelectorAll('.network-option').forEach(o => o.classList.remove('active'));
                    opt.classList.add('active');
                    selectedChain = opt.dataset.chain;
                    selectedChainInfo = coinChains.find(c => c.chainType === selectedChain);
                    showWithdrawForm();
                });
            });
        } else {
            coinChains = [];
            container.innerHTML = `
                <div class="empty-state-sm">
                    <i class="fas fa-info-circle"></i>
                    <p>No withdrawal networks available for ${coin}. Configure your Bybit API keys.</p>
                </div>`;
        }
    } catch (e) {
        console.error('Failed to load networks:', e);
        container.innerHTML = `
            <div class="empty-state-sm">
                <i class="fas fa-exclamation-circle"></i>
                <p>Could not load networks. Check your API keys.</p>
            </div>`;
    }
}

function showWithdrawForm() {
    const card = document.getElementById('withdrawFormCard');
    card.style.display = 'block';

    // Show/hide tag field for coins that need it (XRP, EOS, etc.)
    const needsTag = ['XRP', 'EOS', 'XLM', 'ATOM', 'HBAR'].includes(selectedCoin);
    document.getElementById('tagGroup').style.display = needsTag ? 'block' : 'none';

    // Update summary
    document.getElementById('summaryNetwork').textContent = selectedChain || 'Default';
    if (selectedChainInfo) {
        document.getElementById('summaryFee').textContent = `${selectedChainInfo.withdrawFee} ${selectedCoin}`;
        document.getElementById('summaryMin').textContent = `${selectedChainInfo.withdrawMin} ${selectedCoin}`;
    }
    updateSummary();
}

function updateSummary() {
    const amount = parseFloat(document.getElementById('withdrawAmount')?.value || 0);
    const fee = selectedChainInfo ? parseFloat(selectedChainInfo.withdrawFee || 0) : 0;
    const receive = Math.max(0, amount - fee);
    document.getElementById('summaryReceive').textContent = receive > 0 ? `${receive.toFixed(8)} ${selectedCoin}` : '—';
}

async function handleWithdraw() {
    const address = document.getElementById('withdrawAddress').value.trim();
    const tag = document.getElementById('withdrawTag')?.value?.trim() || '';
    const amount = parseFloat(document.getElementById('withdrawAmount').value);

    if (!address) { Utils.showError('Please enter a withdrawal address'); return; }
    if (!amount || amount <= 0) { Utils.showError('Please enter a valid amount'); return; }

    if (selectedChainInfo) {
        const minWithdraw = parseFloat(selectedChainInfo.withdrawMin || 0);
        if (amount < minWithdraw) {
            Utils.showError(`Minimum withdrawal is ${minWithdraw} ${selectedCoin}`);
            return;
        }
    }

    showWithdrawConfirmModal({ address, amount, tag });
}

function showWithdrawConfirmModal({ address, amount, tag }) {
    let modal = document.getElementById('withdrawConfirmModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'withdrawConfirmModal';
        modal.className = 'modal-overlay';
        document.body.appendChild(modal);
    }
    const fee = selectedChainInfo?.withdrawFee || '0';
    const network = selectedChain || 'Default';
    const receive = Math.max(0, amount - parseFloat(fee || 0));

    modal.innerHTML = `
    <div class="modal-content">
        <div class="modal-header">
            <h3>Confirm Withdrawal</h3>
            <button class="modal-close" id="closeWithdrawModal"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <div class="modal-info"><span>Asset</span><span>${selectedCoin}</span></div>
            <div class="modal-info"><span>Network</span><span>${network}</span></div>
            <div class="modal-info"><span>Address</span><span style="font-size:0.8rem;word-break:break-all;">${Utils.truncateAddress(address, 10)}</span></div>
            <div class="modal-info"><span>Amount</span><span>${amount} ${selectedCoin}</span></div>
            <div class="modal-info"><span>Network Fee</span><span>${fee} ${selectedCoin}</span></div>
            <div class="modal-info"><span>You Receive</span><span class="text-gold">≈ ${receive.toFixed(8)} ${selectedCoin}</span></div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-ghost" id="cancelWithdrawModal">Cancel</button>
            <button class="btn btn-primary" id="confirmWithdrawModal"><i class="fas fa-paper-plane"></i> Confirm Withdrawal</button>
        </div>
    </div>`;
    modal.classList.add('active');

    const close = () => modal.classList.remove('active');
    document.getElementById('closeWithdrawModal').onclick = close;
    document.getElementById('cancelWithdrawModal').onclick = close;
    document.getElementById('confirmWithdrawModal').onclick = async () => {
        Utils.setBtnLoading('#confirmWithdrawModal');
        try {
            const result = await API.withdraw(selectedCoin, selectedChain, address, amount, tag);
            Utils.showSuccess(result.message || 'Withdrawal submitted!');
            close();
            document.getElementById('withdrawAddress').value = '';
            document.getElementById('withdrawAmount').value = '';
            if (document.getElementById('withdrawTag')) document.getElementById('withdrawTag').value = '';
            updateSummary();
        } catch (e) {
            Utils.showError(e.message || 'Withdrawal failed');
        } finally {
            Utils.setBtnLoading('#confirmWithdrawModal', false);
        }
    };
}
