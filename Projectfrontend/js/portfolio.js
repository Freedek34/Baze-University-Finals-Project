/**
 * CryptoVault - Earn (Bybit Savings/Earn)
 */
document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    initEarn();
});

let allProducts = [];
let activePositions = [];

async function initEarn() {
    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            filterProducts(chip.dataset.coin || '');
        });
    });
    // Search bar
    const searchInput = document.getElementById('productSearch');
    if (searchInput) {
        searchInput.addEventListener('input', Utils.debounce(() => {
            searchProducts(searchInput.value.trim());
        }, 250));
    }
    document.getElementById('syncBtn')?.addEventListener('click', syncPositions);
    await Promise.all([loadWalletHoldings(), loadProducts(), loadPositions()]);
}

async function loadWalletHoldings() {
    const container = document.getElementById('walletHoldingsList');
    const totalEl = document.getElementById('portfolioTotal');
    if (!container) return;
    try {
        const data = await API.getBalance();
        const wallets = (data.wallets || []).filter(w => parseFloat(w.total || w.available || 0) > 0);
        const totalUsd = parseFloat(data.total_usd || 0);
        if (totalEl) totalEl.textContent = Utils.formatCurrency(totalUsd);
        if (!wallets.length) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-wallet"></i><p>No wallet balances yet</p></div>';
            return;
        }
        let html = '';
        for (const w of wallets) {
            const coin = w.coin;
            const avail = parseFloat(w.available || 0);
            const locked = parseFloat(w.locked || 0);
            const usd = parseFloat(w.usd_value || 0);
            html += `
            <div class="wallet-holding-row">
                <div class="holding-coin">
                    <div class="coin-icon" style="background:${Utils.getCoinColor(coin)}20;color:${Utils.getCoinColor(coin)}">
                        <i class="${Utils.getCoinIcon(coin)}"></i>
                    </div>
                    <div>
                        <div class="holding-name">${w.name || coin}</div>
                        <div class="holding-label text-muted">${w.wallet_label || 'Funding'} Wallet</div>
                    </div>
                </div>
                <div class="holding-balances">
                    <div class="holding-amount">${Utils.formatCrypto(avail, coin === 'USDT' ? 2 : 6)} ${coin}</div>
                    <div class="holding-usd text-muted">${Utils.formatCurrency(usd)}${locked > 0 ? ` · ${Utils.formatCrypto(locked, 2)} locked` : ''}</div>
                </div>
            </div>`;
        }
        const ngn = parseFloat(data.fiat?.NGN || 0);
        if (ngn > 0) {
            html += `
            <div class="wallet-holding-row">
                <div class="holding-coin">
                    <div class="coin-icon" style="background:rgba(52,211,153,0.15);color:#34d399">₦</div>
                    <div>
                        <div class="holding-name">Nigerian Naira</div>
                        <div class="holding-label text-muted">Fiat Wallet (P2P)</div>
                    </div>
                </div>
                <div class="holding-balances">
                    <div class="holding-amount">₦${ngn.toLocaleString('en-US', { minimumFractionDigits: 2 })}</div>
                    <div class="holding-usd text-muted">For P2P trading</div>
                </div>
            </div>`;
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-center">Failed to load wallets</p>';
    }
}

async function loadProducts() {
    const container = document.getElementById('productsList');
    if (!container) return;
    Utils.showLoading(container);
    try {
        const data = await API.getEarnProducts();
        allProducts = data.products || [];
        renderProducts(allProducts);
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Failed to load products. Make sure your Bybit API keys are configured in Settings.</p></div>';
    }
}

function filterProducts(coin) {
    if (typeof coin !== 'string') coin = '';
    // Clear search when using chip filter
    const searchInput = document.getElementById('productSearch');
    if (searchInput) searchInput.value = '';
    if (!coin) return renderProducts(allProducts);
    renderProducts(allProducts.filter(p => p.coin === coin));
}

function searchProducts(query) {
    if (!query) return renderProducts(allProducts);
    const q = query.toLowerCase();
    const filtered = allProducts.filter(p => {
        const coin = (p.coin || '').toLowerCase();
        const type = (p.productType || '').toLowerCase();
        return coin.includes(q) || type.includes(q);
    });
    // Reset active chip to "All" when searching
    document.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
    const allChip = document.querySelector('.filter-chip[data-coin=""]');
    if (allChip) allChip.classList.add('active');
    renderProducts(filtered);
}

function renderProducts(products) {
    const container = document.getElementById('productsList');
    if (!container) return;
    if (!products.length) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-coins"></i><p>No earn products available</p></div>';
        return;
    }
    let html = '';
    for (const p of products) {
        const apy = parseFloat(p.estimateApy || p.apy || 0) * 100;
        html += `
        <div class="earn-card">
            <div class="earn-header">
                <div class="earn-coin">
                    <span class="coin-icon-sm" style="color:${Utils.getCoinColor(p.coin)}"><i class="${Utils.getCoinIcon(p.coin)}"></i></span>
                    <span class="earn-coin-name">${p.coin}</span>
                </div>
                <span class="earn-type badge">${p.productType || 'Flexible'}</span>
            </div>
            <div class="earn-apy">
                <span class="apy-value text-green">${apy.toFixed(2)}%</span>
                <span class="apy-label">Est. APY</span>
            </div>
            <div class="earn-details">
                <div class="detail-row"><span>Min Amount</span><span>${p.minPurchaseAmount || '0'} ${p.coin}</span></div>
                <div class="detail-row"><span>Status</span><span class="badge badge-sm">${p.status || 'Available'}</span></div>
            </div>
            <button class="btn btn-primary btn-sm btn-block subscribe-btn" 
                data-product-id="${p.productId}" data-coin="${p.coin}" data-type="${p.productType || 'Flexible'}" data-apy="${apy}"
                data-min="${p.minPurchaseAmount || 0}">
                <i class="fas fa-plus-circle"></i> Subscribe
            </button>
        </div>`;
    }
    container.innerHTML = html;

    container.querySelectorAll('.subscribe-btn').forEach(btn => {
        btn.addEventListener('click', () => openSubscribeModal(btn.dataset));
    });
}

function openSubscribeModal(data) {
    let modal = document.getElementById('subscribeModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'subscribeModal';
        modal.className = 'modal-overlay';
        document.body.appendChild(modal);
    }
    modal.innerHTML = `
    <div class="modal-content">
        <div class="modal-header">
            <h3>Subscribe to ${data.coin} Earn</h3>
            <button class="modal-close" id="closeModal"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <div class="modal-info">
                <span>APY</span><span class="text-green">${parseFloat(data.apy).toFixed(2)}%</span>
            </div>
            <div class="modal-info">
                <span>Type</span><span>${data.type}</span>
            </div>
            <div class="modal-info">
                <span>Min Amount</span><span>${data.min} ${data.coin}</span>
            </div>
            <div class="form-group">
                <label>Amount (${data.coin})</label>
                <input type="number" id="subscribeAmount" class="form-input" placeholder="Enter amount" min="${data.min}" step="any">
            </div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-ghost" id="cancelSubscribe">Cancel</button>
            <button class="btn btn-primary" id="confirmSubscribe">Subscribe</button>
        </div>
    </div>`;
    modal.classList.add('active');

    document.getElementById('closeModal').onclick = () => modal.classList.remove('active');
    document.getElementById('cancelSubscribe').onclick = () => modal.classList.remove('active');
    document.getElementById('confirmSubscribe').onclick = async () => {
        const amount = parseFloat(document.getElementById('subscribeAmount').value);
        if (!amount || amount < parseFloat(data.min)) { Utils.showError(`Minimum amount is ${data.min} ${data.coin}`); return; }
        Utils.setBtnLoading('#confirmSubscribe');
        try {
            await API.subscribeEarn(data.productId, amount, data.coin, data.type, data.apy);
            Utils.showSuccess('Subscribed successfully!');
            modal.classList.remove('active');
            await loadPositions();
        } catch (e) { Utils.showError(e.message); }
        finally { Utils.setBtnLoading('#confirmSubscribe', false); }
    };
}

async function loadPositions() {
    const container = document.getElementById('positionsList');
    if (!container) return;
    try {
        const data = await API.getEarnPositions();
        activePositions = data.positions || [];
        renderPositions(activePositions);
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-center">Failed to load positions</p>';
    }
}

function renderPositions(positions) {
    const container = document.getElementById('positionsList');
    if (!container) return;
    if (!positions.length) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-wallet"></i><p>No active earn positions</p></div>';
        return;
    }
    let totalValue = 0;
    let html = '';
    for (const p of positions) {
        const amount = parseFloat(p.amount || 0);
        totalValue += amount;
        const apy = parseFloat(p.apy || 0);
        html += `
        <div class="position-card">
            <div class="position-header">
                <div class="position-coin">${Utils.getCoinBadge(p.coin)} <span class="position-type">${p.product_type || 'Flexible'}</span></div>
                <span class="badge badge-${p.status === 'active' ? 'green' : 'default'}">${p.status}</span>
            </div>
            <div class="position-details">
                <div class="detail-row"><span>Amount</span><span>${Utils.formatAmount(amount, p.coin)}</span></div>
                <div class="detail-row"><span>APY</span><span class="text-green">${apy.toFixed(2)}%</span></div>
                <div class="detail-row"><span>Since</span><span>${Utils.formatDate(p.created_at)}</span></div>
            </div>
            ${p.status === 'active' ? `<button class="btn btn-outline btn-sm btn-block redeem-btn" data-id="${p.id}"><i class="fas fa-undo"></i> Redeem</button>` : ''}
        </div>`;
    }
    container.innerHTML = html;
    const totalEl = document.getElementById('positionsTotal');
    if (totalEl) totalEl.textContent = Utils.formatCurrency(totalValue);

    container.querySelectorAll('.redeem-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            Utils.setBtnLoading(btn);
            try {
                await API.redeemEarn(btn.dataset.id);
                Utils.showSuccess('Redeemed successfully!');
                await loadPositions();
            } catch (e) { Utils.showError(e.message); }
            finally { Utils.setBtnLoading(btn, false); }
        });
    });
}

async function syncPositions() {
    Utils.setBtnLoading('#syncBtn');
    try {
        await API.syncEarnPositions();
        await loadPositions();
        Utils.showSuccess('Positions synced with Bybit');
    } catch (e) { Utils.showError(e.message); }
    finally { Utils.setBtnLoading('#syncBtn', false); }
}
