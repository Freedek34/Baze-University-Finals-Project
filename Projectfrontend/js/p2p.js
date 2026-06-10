/**
 * CryptoVault - P2P Trading
 */
let depositMode = false;
let activeAd = null;
let p2pOrderId = null;
let p2pVendorName = '';

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    depositMode = new URLSearchParams(window.location.search).get('mode') === 'deposit';
    if (depositMode) {
        document.getElementById('depositBanner').style.display = 'block';
        const sideFilter = document.getElementById('filterSide');
        if (sideFilter) sideFilter.value = '0';
    }
    initP2P();
});

async function initP2P() {
    document.querySelectorAll('.p2p-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.p2p-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.p2p-panel').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById(tab.dataset.panel)?.classList.add('active');
        });
    });

    document.getElementById('filterSide')?.addEventListener('change', loadAds);
    document.getElementById('filterToken')?.addEventListener('change', loadAds);
    document.getElementById('filterCurrency')?.addEventListener('change', loadAds);
    document.getElementById('createAdBtn')?.addEventListener('click', openCreateAdModal);

    document.getElementById('closeP2pModal')?.addEventListener('click', closeP2pModal);
    document.getElementById('p2pCreateOrderBtn')?.addEventListener('click', createP2pOrder);
    document.getElementById('p2pMarkPaidBtn')?.addEventListener('click', markP2pPaid);
    document.getElementById('p2pReleaseBtn')?.addEventListener('click', releaseP2pCrypto);
    document.getElementById('p2pAmount')?.addEventListener('input', updateP2pTotal);

    await Promise.all([loadAds(), loadMyOrders()]);
}

async function loadAds() {
    const container = document.getElementById('adsList');
    if (!container) return;
    Utils.showLoading(container);
    const side = document.getElementById('filterSide')?.value || '0';
    const token = document.getElementById('filterToken')?.value || 'USDT';
    const currency = document.getElementById('filterCurrency')?.value || 'NGN';
    try {
        const data = await API.getP2PAds(token, currency, side);
        if (data.error) {
            container.innerHTML = `<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>${data.error}</p></div>`;
            return;
        }
        const ads = data.ads || [];
        renderAds(ads, side);
    } catch (e) {
        console.error('P2P ads error:', e);
        container.innerHTML = '<div class="empty-state"><i class="fas fa-exclamation-circle"></i><p>Failed to load P2P ads.</p></div>';
    }
}

function renderAds(ads, side) {
    const container = document.getElementById('adsList');
    if (!ads.length) {
        container.innerHTML = '<div class="empty-state"><i class="fas fa-store"></i><p>No ads found</p></div>';
        return;
    }
    const isBuy = side === '0';
    let html = '';
    for (const raw of ads) {
        const ad = raw.advertiser ? { ...raw, ...raw.advertiser } : raw;
        const nickName = ad.nickName || ad.nick_name || ad.nickname || 'Trader';
        const price = parseFloat(ad.price || ad.unitPrice || 0);
        const currency = ad.currencyId || ad.currency_id || ad.fiatCurrency || 'NGN';
        const token = ad.tokenId || ad.token_id || document.getElementById('filterToken')?.value || 'USDT';
        const minAmt = ad.minAmount || ad.min_amount || ad.minOrderAmount || '0';
        const maxAmt = ad.maxAmount || ad.max_amount || ad.maxOrderAmount || '0';
        const orderCount = ad.orderCount || ad.recentOrderNum || ad.order_count || 0;
        const completionRate = ad.completionRate || ad.recentFinishRate || ad.completion_rate || '0';
        const rateDisplay = parseFloat(completionRate) > 1 ? completionRate : (parseFloat(completionRate) * 100).toFixed(1);
        const paymentList = ad.payments || ad.paymentMethods || ad.tradeMethods || [];
        const payments = paymentList.map(p => {
            const name = typeof p === 'string' ? p : (p.name || p.paymentName || p.paymentType || 'N/A');
            return `<span class="payment-badge">${name}</span>`;
        }).join('');

        const adData = encodeURIComponent(JSON.stringify({
            nickName, price, currency, token, minAmt, maxAmt
        }));

        html += `
        <div class="p2p-ad-card" data-ad="${adData}" style="cursor:pointer;">
            <div class="p2p-ad-top">
                <div class="ad-avatar">${nickName[0].toUpperCase()}</div>
                <div class="ad-info">
                    <div class="ad-nick">${nickName}</div>
                    <div class="ad-stats">${orderCount} orders | ${rateDisplay}%</div>
                </div>
            </div>
            <div class="p2p-ad-body">
                <div class="info-item">
                    <span class="info-label">Price</span>
                    <span class="info-value">${Utils.formatCrypto(price, 2)} ${currency}</span>
                </div>
                <div class="info-item">
                    <span class="info-label">Limit</span>
                    <span class="info-value">${minAmt} - ${maxAmt}</span>
                </div>
            </div>
            <div class="p2p-ad-payments">${payments || '<span class="text-muted" style="font-size:0.75rem;">N/A</span>'}</div>
            ${depositMode || isBuy ? `<button class="btn btn-primary btn-sm btn-block" style="margin-top:12px;" data-ad="${adData}">${isBuy ? 'Buy' : 'Sell'} ${token}</button>` : ''}
        </div>`;
    }
    container.innerHTML = html;

    container.querySelectorAll('.p2p-ad-card').forEach(card => {
        const openOrder = () => {
            try {
                activeAd = JSON.parse(decodeURIComponent(card.dataset.ad));
                openP2pOrderModal();
            } catch (_) {}
        };
        if (depositMode) card.addEventListener('click', openOrder);
        card.querySelector('button')?.addEventListener('click', (e) => {
            e.stopPropagation();
            openOrder();
        });
    });
}

function openP2pOrderModal() {
    if (!activeAd) return;
    p2pOrderId = null;
    p2pVendorName = activeAd.nickName;
    showP2pStep(1);
    document.getElementById('p2pTokenLabel').textContent = activeAd.token;
    document.getElementById('p2pPriceDisplay').textContent = `${Utils.formatCrypto(activeAd.price, 2)} ${activeAd.currency}`;
    document.getElementById('p2pVendorDisplay').textContent = p2pVendorName;
    document.getElementById('p2pAmount').value = '';
    document.getElementById('p2pTotalDisplay').textContent = '—';
    document.getElementById('p2pModalTitle').textContent = `Buy ${activeAd.token}`;
    document.getElementById('p2pOrderModal').classList.add('active');
}

function closeP2pModal() {
    document.getElementById('p2pOrderModal').classList.remove('active');
}

function showP2pStep(n) {
    document.querySelectorAll('#p2pOrderFlow .flow-step').forEach((s, i) => {
        s.classList.toggle('active', i + 1 === n);
    });
}

function updateP2pTotal() {
    const amount = parseFloat(document.getElementById('p2pAmount').value) || 0;
    const total = amount * (activeAd?.price || 0);
    document.getElementById('p2pTotalDisplay').textContent =
        amount > 0 ? `${Utils.formatCrypto(total, 2)} ${activeAd?.currency || 'NGN'}` : '—';
}

async function createP2pOrder() {
    const amount = parseFloat(document.getElementById('p2pAmount').value);
    if (!amount || amount <= 0) { Utils.showError('Enter a valid amount'); return; }
    Utils.setBtnLoading('#p2pCreateOrderBtn');
    try {
        const data = await API.createP2PDepositOrder({
            token: activeAd.token,
            currency: activeAd.currency,
            amount,
            price: activeAd.price,
            vendor_nickname: p2pVendorName,
        });
        p2pOrderId = data.order_id;
        const payMethod = 'Bank Transfer';
        document.getElementById('p2pPayInstructions').textContent =
            `Send ${Utils.formatCrypto(data.total_price, 2)} ${activeAd.currency} to ${p2pVendorName} via ${payMethod}`;
        showP2pStep(2);
    } catch (e) {
        Utils.showError(e.message);
    } finally {
        Utils.setBtnLoading('#p2pCreateOrderBtn', false);
    }
}

async function markP2pPaid() {
    if (!p2pOrderId) return;
    Utils.setBtnLoading('#p2pMarkPaidBtn');
    try {
        await API.markP2POrderPaid(p2pOrderId);
        showP2pStep(3);
        document.getElementById('p2pReleaseText').textContent = `${p2pVendorName} Has Released Crypto`;
        setTimeout(() => {
            document.querySelector('#p2pStep3 .loading').style.display = 'none';
            document.getElementById('p2pReleaseBtn').style.display = 'flex';
        }, 2000);
    } catch (e) {
        Utils.showError(e.message);
    } finally {
        Utils.setBtnLoading('#p2pMarkPaidBtn', false);
    }
}

async function releaseP2pCrypto() {
    if (!p2pOrderId) return;
    Utils.setBtnLoading('#p2pReleaseBtn');
    try {
        const result = await API.releaseP2PDeposit(p2pOrderId);
        document.getElementById('p2pSuccessMsg').textContent =
            `${Utils.formatAmount(result.amount, result.coin)} credited. Ref: ${result.reference}`;
        showP2pStep(4);
        Utils.showSuccess('P2P deposit complete!');
        await loadMyOrders();
    } catch (e) {
        Utils.showError(e.message);
    } finally {
        Utils.setBtnLoading('#p2pReleaseBtn', false);
    }
}

async function loadMyOrders() {
    const container = document.getElementById('ordersList');
    if (!container) return;
    try {
        const data = await API.getP2POrders();
        const orders = data.orders || [];
        if (!orders.length) {
            container.innerHTML = '<div class="empty-state"><i class="fas fa-receipt"></i><p>No P2P orders yet</p></div>';
            return;
        }
        let html = '';
        for (const o of orders) {
            const sideLabel = o.side === 0 || o.side === '0' || o.side === 'buy' ? 'BUY' : 'SELL';
            const statusCls = o.status === 'completed' ? 'badge-green' : o.status === 'pending' ? 'badge-yellow' : 'badge-default';
            const token = o.token_id || o.token || 'USDT';
            html += `
            <div class="order-card">
                <div class="order-header">
                    <span class="order-type badge ${sideLabel === 'BUY' ? 'badge-green' : 'badge-red'}">${sideLabel}</span>
                    <span class="badge ${statusCls}">${o.status}</span>
                </div>
                <div class="order-details">
                    <div class="detail-row"><span>Amount</span><span>${Utils.formatAmount(o.amount, token)}</span></div>
                    <div class="detail-row"><span>Price</span><span>${Utils.formatCrypto(o.price, 2)} ${o.currency_id || o.currency || 'NGN'}</span></div>
                    <div class="detail-row"><span>Date</span><span>${Utils.formatDateTime(o.created_at)}</span></div>
                </div>
            </div>`;
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-center">Failed to load orders</p>';
    }
}

function openCreateAdModal() {
    let modal = document.getElementById('createAdModal');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'createAdModal';
        modal.className = 'modal-overlay';
        document.body.appendChild(modal);
    }
    modal.innerHTML = `
    <div class="modal-content modal-lg">
        <div class="modal-header">
            <h3>Create P2P Ad</h3>
            <button class="modal-close" id="closeAdModal"><i class="fas fa-times"></i></button>
        </div>
        <div class="modal-body">
            <div class="form-row">
                <div class="form-group"><label>Side</label><select id="adSide" class="form-input"><option value="1">Buy</option><option value="0">Sell</option></select></div>
                <div class="form-group"><label>Token</label><select id="adToken" class="form-input"><option>USDT</option><option>BTC</option><option>ETH</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Price</label><input type="number" id="adPrice" class="form-input" placeholder="Price per token" step="any"></div>
                <div class="form-group"><label>Currency</label><select id="adCurrency" class="form-input"><option>NGN</option><option>USD</option><option>EUR</option><option>GBP</option></select></div>
            </div>
            <div class="form-row">
                <div class="form-group"><label>Quantity</label><input type="number" id="adQuantity" class="form-input" placeholder="Total quantity" step="any"></div>
                <div class="form-group"><label>Min Order</label><input type="number" id="adMinOrder" class="form-input" placeholder="Min order amount" step="any"></div>
            </div>
            <div class="form-group"><label>Max Order</label><input type="number" id="adMaxOrder" class="form-input" placeholder="Max order amount" step="any"></div>
        </div>
        <div class="modal-footer">
            <button class="btn btn-ghost" id="cancelAd">Cancel</button>
            <button class="btn btn-primary" id="submitAd">Create Ad</button>
        </div>
    </div>`;
    modal.classList.add('active');

    document.getElementById('closeAdModal').onclick = () => modal.classList.remove('active');
    document.getElementById('cancelAd').onclick = () => modal.classList.remove('active');
    document.getElementById('submitAd').onclick = async () => {
        const payload = {
            token: document.getElementById('adToken').value,
            currency: document.getElementById('adCurrency').value,
            side: document.getElementById('adSide').value,
            price: document.getElementById('adPrice').value,
            quantity: document.getElementById('adQuantity').value,
            min_amount: document.getElementById('adMinOrder').value,
            max_amount: document.getElementById('adMaxOrder').value,
        };
        if (!payload.price || !payload.quantity) { Utils.showError('Fill in price and quantity'); return; }
        Utils.setBtnLoading('#submitAd');
        try {
            await API.createP2PAd(payload);
            Utils.showSuccess('Ad created!');
            modal.classList.remove('active');
            await loadAds();
        } catch (e) { Utils.showError(e.message); }
        finally { Utils.setBtnLoading('#submitAd', false); }
    };
}
