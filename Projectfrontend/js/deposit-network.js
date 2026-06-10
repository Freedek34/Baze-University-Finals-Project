/**
 * CryptoVault - Deposit Crypto: network selection & confirmation
 */
let selectedCoin = 'USDT';
let selectedNetwork = '';
let depositRequestId = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    const params = new URLSearchParams(window.location.search);
    selectedCoin = (params.get('coin') || 'USDT').toUpperCase();
    document.getElementById('coinLabel').textContent = selectedCoin;
    document.getElementById('amountCoin').textContent = selectedCoin;

    document.getElementById('copyAddressBtn')?.addEventListener('click', () => {
        const addr = document.getElementById('depositAddress').textContent;
        if (addr && addr !== '—') Utils.copyToClipboard(addr);
    });
    document.getElementById('copyTagBtn')?.addEventListener('click', () => {
        const tag = document.getElementById('depositTag').textContent;
        if (tag && tag !== '—') Utils.copyToClipboard(tag);
    });
    document.getElementById('confirmSentBtn')?.addEventListener('click', confirmDeposit);

    loadNetworks();
});

async function loadNetworks() {
    const container = document.getElementById('networkSelector');
    container.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    const fallbackNetworks = {
        USDT: ['TRC20', 'ERC20', 'BEP20', 'SOL'],
        BTC: ['Bitcoin', 'Lightning'],
        ETH: ['ERC20', 'Arbitrum', 'Optimism'],
        SOL: ['Solana'],
        BNB: ['BEP20', 'BEP2'],
        XRP: ['XRP Ledger'],
        ADA: ['Cardano'],
        DOGE: ['Dogecoin'],
        AVAX: ['C-Chain'],
    };

    try {
        const data = await API.getCoinInfo(selectedCoin);
        const coins = data.coins || [];
        const coinData = coins.find(c => c.coin === selectedCoin);
        let chains = coinData?.chains?.length ? coinData.chains : null;

        if (!chains) {
            const nets = fallbackNetworks[selectedCoin] || [selectedCoin];
            chains = nets.map(n => ({ chain: n, chainType: n, chainDeposit: '1', depositMin: '0', confirmation: '12' }));
        }

        let html = '';
        for (const chain of chains) {
            const enabled = chain.chainDeposit === '1' || chain.chainDeposit === 1 || chain.chainDeposit === undefined;
            html += `
            <div class="network-option ${!enabled ? 'disabled' : ''}" data-chain="${chain.chainType || chain.chain}">
                <div class="network-name">
                    <span class="chain-badge">${chain.chain || chain.chainType}</span>
                    <span class="chain-type">${chain.chainType || chain.chain}</span>
                </div>
                <div class="network-meta">
                    <span class="meta-item">Min: ${chain.depositMin || '0'} ${selectedCoin}</span>
                    <span class="meta-item">Confirm: ${chain.confirmation || '—'}</span>
                </div>
            </div>`;
        }
        container.innerHTML = html;

        container.querySelectorAll('.network-option:not(.disabled)').forEach(opt => {
            opt.addEventListener('click', () => {
                container.querySelectorAll('.network-option').forEach(o => o.classList.remove('active'));
                opt.classList.add('active');
                selectedNetwork = opt.dataset.chain;
                initDepositAddress();
            });
        });
    } catch (e) {
        const nets = fallbackNetworks[selectedCoin] || [selectedCoin];
        container.innerHTML = nets.map(n => `
            <div class="network-option" data-chain="${n}">
                <div class="network-name"><span class="chain-badge">${n}</span></div>
            </div>`).join('');
        container.querySelectorAll('.network-option').forEach(opt => {
            opt.addEventListener('click', () => {
                container.querySelectorAll('.network-option').forEach(o => o.classList.remove('active'));
                opt.classList.add('active');
                selectedNetwork = opt.dataset.chain;
                initDepositAddress();
            });
        });
    }
}

function ensureDepositApi() {
    if (typeof API?.initCryptoDeposit !== 'function') {
        throw new Error('App scripts are outdated. Hard-refresh this page (Ctrl+Shift+R).');
    }
}

async function initDepositAddress() {
    ensureDepositApi();
    const card = document.getElementById('addressCard');
    const amountSection = document.getElementById('amountSection');
    const addrEl = document.getElementById('depositAddress');
    const demoBadge = document.getElementById('demoBadge');

    card.style.display = 'block';
    amountSection.style.display = 'none';
    addrEl.textContent = 'Loading...';
    depositRequestId = null;

    try {
        const data = await API.initCryptoDeposit(selectedCoin, selectedNetwork);
        depositRequestId = data.request_id;
        const address = data.address;
        addrEl.textContent = address;

        if (data.demo) demoBadge.style.display = 'inline-block';
        else demoBadge.style.display = 'none';

        document.getElementById('qrCode').innerHTML =
            `<img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(address)}&bgcolor=0a0a0f&color=d4a843" alt="QR" class="qr-img">`;

        const tagSection = document.getElementById('tagSection');
        if (data.tag_memo) {
            tagSection.style.display = 'block';
            document.getElementById('depositTag').textContent = data.tag_memo;
        } else {
            tagSection.style.display = 'none';
        }

        document.getElementById('addressInfo').innerHTML = `
            <div class="info-row"><span>Network</span><span>${selectedNetwork}</span></div>
            <div class="info-row"><span>Reference</span><span>${data.reference || '—'}</span></div>`;

        amountSection.style.display = 'block';
    } catch (e) {
        addrEl.textContent = '—';
        Utils.showError(e.message || 'Failed to load deposit address');
    }
}

async function confirmDeposit() {
    const amount = parseFloat(document.getElementById('depositAmount').value);
    if (!amount || amount <= 0) { Utils.showError('Enter the amount you sent'); return; }
    if (!depositRequestId) { Utils.showError('Select a network first'); return; }

    Utils.setBtnLoading('#confirmSentBtn');
    try {
        const data = await API.confirmCryptoDeposit(depositRequestId, amount);
        document.getElementById('addressCard').style.display = 'none';
        document.getElementById('amountSection').style.display = 'none';
        document.querySelector('.warning-card').style.display = 'none';
        document.getElementById('successSection').style.display = 'block';
        document.getElementById('successMessage').textContent =
            `${Utils.formatAmount(amount, selectedCoin)} has been credited to your account. Ref: ${data.reference}`;
        Utils.showSuccess('Deposit credited!');
    } catch (e) {
        Utils.showError(e.message);
    } finally {
        Utils.setBtnLoading('#confirmSentBtn', false);
    }
}
