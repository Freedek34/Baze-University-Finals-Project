/**
 * CryptoVault - Receive / Deposit Address Page
 */
let selectedCoin = 'USDT';
let selectedChain = '';
let coinChains = [];

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    initReceive();
});

function initReceive() {
    // Asset selector
    document.querySelectorAll('.asset-option').forEach(opt => {
        opt.addEventListener('click', () => {
            document.querySelectorAll('.asset-option').forEach(o => o.classList.remove('active'));
            opt.classList.add('active');
            selectedCoin = opt.dataset.coin;
            selectedChain = '';
            document.getElementById('addressCard').style.display = 'none';
            loadNetworks(selectedCoin);
        });
    });

    document.getElementById('copyAddressBtn')?.addEventListener('click', () => {
        const addr = document.getElementById('depositAddress').textContent;
        if (addr && addr !== '—') Utils.copyToClipboard(addr);
    });

    document.getElementById('copyTagBtn')?.addEventListener('click', () => {
        const tag = document.getElementById('depositTag').textContent;
        if (tag && tag !== '—') Utils.copyToClipboard(tag);
    });

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
                const depositEnabled = chain.chainDeposit === '1' || chain.chainDeposit === 1;
                html += `
                <div class="network-option ${!depositEnabled ? 'disabled' : ''}" 
                     data-chain="${chain.chainType}" 
                     ${!depositEnabled ? 'title="Deposit suspended"' : ''}>
                    <div class="network-name">
                        <span class="chain-badge">${chain.chain}</span>
                        <span class="chain-type">${chain.chainType}</span>
                    </div>
                    <div class="network-meta">
                        <span class="meta-item">Min: ${chain.depositMin} ${coin}</span>
                        <span class="meta-item">Confirm: ${chain.confirmation}</span>
                    </div>
                    ${!depositEnabled ? '<span class="suspended-badge">Suspended</span>' : ''}
                </div>`;
            }
            container.innerHTML = html;

            container.querySelectorAll('.network-option:not(.disabled)').forEach(opt => {
                opt.addEventListener('click', () => {
                    container.querySelectorAll('.network-option').forEach(o => o.classList.remove('active'));
                    opt.classList.add('active');
                    selectedChain = opt.dataset.chain;
                    loadDepositAddress(coin, selectedChain);
                });
            });
        } else {
            // Fallback: try loading deposit address directly (some coins have single chain)
            coinChains = [];
            container.innerHTML = `
                <div class="network-option active" data-chain="">
                    <div class="network-name">
                        <span class="chain-badge">${coin}</span>
                        <span class="chain-type">Default Network</span>
                    </div>
                </div>`;
            loadDepositAddress(coin, '');
        }
    } catch (e) {
        console.error('Failed to load networks:', e);
        container.innerHTML = `
            <div class="empty-state-sm">
                <i class="fas fa-exclamation-circle"></i>
                <p>Could not load networks. Make sure your Bybit API keys are configured.</p>
            </div>`;
    }
}

async function loadDepositAddress(coin, chain) {
    const card = document.getElementById('addressCard');
    const addrEl = document.getElementById('depositAddress');
    const tagEl = document.getElementById('depositTag');
    const tagSection = document.getElementById('tagSection');
    const infoEl = document.getElementById('addressInfo');
    const qrEl = document.getElementById('qrCode');

    card.style.display = 'block';
    addrEl.textContent = 'Loading...';
    tagSection.style.display = 'none';
    infoEl.innerHTML = '';

    try {
        const data = await API.getDepositAddress(coin, chain);

        if (data.error) {
            addrEl.textContent = '—';
            infoEl.innerHTML = `<div class="info-error"><i class="fas fa-exclamation-circle"></i> ${data.error}</div>`;
            qrEl.innerHTML = '<i class="fas fa-qrcode" style="font-size:3rem;color:var(--text-muted)"></i>';
            return;
        }

        const chains = data.chains || [];
        let targetChain = null;

        if (chain) {
            targetChain = chains.find(c => c.chainType === chain || c.chain === chain);
        }
        if (!targetChain && chains.length > 0) {
            targetChain = chains[0];
        }

        if (targetChain && targetChain.addressDeposit) {
            const address = targetChain.addressDeposit;
            addrEl.textContent = address;

            qrEl.innerHTML = `<img src="https://api.qrserver.com/v1/create-qr-code/?size=180x180&data=${encodeURIComponent(address)}&bgcolor=0a0a0f&color=d4a843" alt="QR Code" class="qr-img">`;

            if (targetChain.tagDeposit) {
                tagSection.style.display = 'block';
                tagEl.textContent = targetChain.tagDeposit;
            }

            let infoHtml = '';
            if (data.demo) {
                infoHtml += '<div class="info-row"><span>Mode</span><span class="badge badge-yellow">Demo Address</span></div>';
            }
            infoHtml += `<div class="info-row"><span>Network</span><span>${targetChain.chainType || targetChain.chain}</span></div>`;
            if (targetChain.minAmount && targetChain.minAmount !== '0') {
                infoHtml += `<div class="info-row"><span>Min Deposit</span><span>${targetChain.minAmount} ${coin}</span></div>`;
            }
            if (targetChain.confirmation && targetChain.confirmation !== '0') {
                infoHtml += `<div class="info-row"><span>Confirmations</span><span>${targetChain.confirmation}</span></div>`;
            }
            infoEl.innerHTML = infoHtml;
        } else {
            addrEl.textContent = '—';
            infoEl.innerHTML = '<div class="info-error"><i class="fas fa-info-circle"></i> No deposit address available for this network. Please configure your Bybit API keys in Settings.</div>';
            qrEl.innerHTML = '<i class="fas fa-qrcode" style="font-size:3rem;color:var(--text-muted)"></i>';
        }
    } catch (e) {
        console.error('Deposit address error:', e);
        addrEl.textContent = '—';
        infoEl.innerHTML = `<div class="info-error"><i class="fas fa-exclamation-circle"></i> ${e.message || 'Failed to load address'}</div>`;
        qrEl.innerHTML = '<i class="fas fa-qrcode" style="font-size:3rem;color:var(--text-muted)"></i>';
    }
}
