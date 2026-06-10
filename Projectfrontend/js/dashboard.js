/**
 * CryptoVault - Dashboard
 */
let refreshInterval = null;

document.addEventListener('DOMContentLoaded', () => {
    if (!Utils.checkAuth()) return;
    initDashboard();
});

function setupDepositSheet() {
    const depositBtn = document.getElementById('depositBtn');
    const paymentSheet = document.getElementById('paymentSheet');
    const sheetPanel = paymentSheet?.querySelector('.payment-sheet');
    if (!depositBtn || !paymentSheet) return;

    depositBtn.type = 'button';
    depositBtn.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        paymentSheet.classList.add('active');
        document.body.style.overflow = 'hidden';
    });

    paymentSheet.addEventListener('click', (e) => {
        if (e.target === paymentSheet) closeDepositSheet();
    });
    sheetPanel?.addEventListener('click', (e) => e.stopPropagation());
}

function closeDepositSheet() {
    const paymentSheet = document.getElementById('paymentSheet');
    if (paymentSheet) paymentSheet.classList.remove('active');
    document.body.style.overflow = '';
}

async function initDashboard() {
    loadUserInfo();
    setupDepositSheet();

    document.getElementById('logoutBtn')?.addEventListener('click', async () => {
        await API.logout();
        window.location.href = 'login.html';
    });
    document.getElementById('refreshBtn')?.addEventListener('click', refreshAll);

    const searchToggleBtn = document.getElementById('searchToggleBtn');
    const searchBar = document.getElementById('searchBar');
    const searchInput = document.getElementById('searchInput');
    const searchCloseBtn = document.getElementById('searchCloseBtn');

    if (searchToggleBtn && searchBar) {
        searchToggleBtn.addEventListener('click', () => {
            searchBar.style.display = searchBar.style.display === 'none' ? 'block' : 'none';
            if (searchBar.style.display === 'block') searchInput.focus();
        });
    }
    if (searchCloseBtn) {
        searchCloseBtn.addEventListener('click', () => {
            searchBar.style.display = 'none';
            searchInput.value = '';
            document.getElementById('searchResults').innerHTML = '';
        });
    }
    if (searchInput) {
        searchInput.addEventListener('input', Utils.debounce(handleSearch, 400));
    }

    // Load dashboard data in background (don't block deposit button)
    await Promise.all([loadBalance(), loadWallets(), loadMarketPrices(), loadEarnSummary(), loadRecentTransactions()]);
    refreshInterval = setInterval(loadMarketPrices, 30000);
}

function loadUserInfo() {
    const user = API.getUser();
    if (user) {
        const avatar = document.getElementById('userAvatar');
        if (avatar) avatar.textContent = (user.username || 'U')[0].toUpperCase();
    }
}

async function loadBalance() {
    try {
        const data = await API.getBalance();
        const totalUsd = parseFloat(data.total_usd || data.account_balance || data.balance || 0);
        const wallets = data.wallets || [];
        const usdtWallet = wallets.find(w => w.coin === 'USDT');
        const usdtBal = usdtWallet ? parseFloat(usdtWallet.available || usdtWallet.total || 0) : 0;
        const coinCount = wallets.length;
        document.getElementById('totalBalance').textContent = Utils.formatCurrency(totalUsd);
        const subEl = document.getElementById('usdtBalance');
        if (subEl) {
            subEl.textContent = coinCount > 1
                ? `${coinCount} assets · ${Utils.formatCrypto(usdtBal, 2)} USDT`
                : Utils.formatCrypto(usdtBal, 2) + ' USDT';
        }
    } catch (e) {
        console.error('Balance error', e);
        document.getElementById('totalBalance').textContent = '$0.00';
        document.getElementById('usdtBalance').textContent = '0.00 USDT';
    }
}

async function loadWallets() {
    const container = document.getElementById('walletAssets');
    if (!container) return;
    try {
        const data = await API.getBalance();
        const wallets = (data.wallets || []).filter(w => parseFloat(w.total || w.available || 0) > 0);
        if (!wallets.length) {
            container.innerHTML = '<p class="text-muted text-center" style="padding:12px;">No assets yet — deposit to get started</p>';
            return;
        }
        let html = '<div class="coin-grid">';
        for (const w of wallets) {
            const coin = w.coin;
            const avail = parseFloat(w.available || w.total || 0);
            const usd = parseFloat(w.usd_value || 0);
            html += `
            <div class="coin-card">
                <div class="coin-icon" style="background:${Utils.getCoinColor(coin)}20;color:${Utils.getCoinColor(coin)}">
                    <i class="${Utils.getCoinIcon(coin)}"></i>
                </div>
                <div class="coin-info">
                    <div class="coin-name">${coin}</div>
                    <div class="coin-value">${Utils.formatCrypto(avail, coin === 'USDT' ? 2 : 6)}</div>
                    <div class="coin-change text-muted">${Utils.formatCurrency(usd)}</div>
                </div>
            </div>`;
        }
        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-center">Failed to load wallets</p>';
    }
}

async function loadMarketPrices() {
    const container = document.getElementById('marketList');
    if (!container) return;
    try {
        const data = await API.getMarketPrices();
        const pricesRaw = data.prices || [];
        // Handle both array and object formats
        const pricesList = Array.isArray(pricesRaw)
            ? pricesRaw
            : Object.values(pricesRaw);
        let html = '';
        for (const info of pricesList) {
            const symbol = info.symbol || '';
            const coin = symbol.replace('USDT', '');
            const price = parseFloat(info.lastPrice || 0);
            const pct = parseFloat(info.price24hPcnt || 0) * 100;
            const isUp = pct >= 0;
            html += `
            <div class="market-row">
                <div class="market-coin">
                    <div class="coin-icon" style="background:${Utils.getCoinColor(coin)}20;color:${Utils.getCoinColor(coin)}">
                        <i class="${Utils.getCoinIcon(coin)}"></i>
                    </div>
                    <div>
                        <div class="coin-name">${coin}</div>
                        <div class="coin-pair text-muted">${symbol}</div>
                    </div>
                </div>
                <div class="market-price">
                    <div class="price-value">$${Utils.formatCrypto(price, 2)}</div>
                    <div class="price-change ${isUp ? 'text-green' : 'text-red'}">
                        ${isUp ? '▲' : '▼'} ${Math.abs(pct).toFixed(2)}%
                    </div>
                </div>
            </div>`;
        }
        container.innerHTML = html || '<p class="text-muted text-center">No market data</p>';
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-center">Failed to load prices</p>';
    }
}

async function loadEarnSummary() {
    const el = document.getElementById('earnSummary');
    if (!el) return;
    try {
        const data = await API.getEarnPositions('active');
        const positions = data.positions || [];
        const totalEarning = positions.reduce((s, p) => s + parseFloat(p.amount || 0), 0);
        document.getElementById('earnTotal').textContent = Utils.formatCurrency(totalEarning);
        document.getElementById('earnCount').textContent = positions.length + ' active';
    } catch (e) {
        document.getElementById('earnTotal').textContent = '$0.00';
        document.getElementById('earnCount').textContent = '0 active';
    }
}

async function loadRecentTransactions() {
    const container = document.getElementById('recentTransactions');
    if (!container) return;
    try {
        const data = await API.getTransactions(5, 0);
        const txs = data.transactions || [];
        if (!txs.length) { container.innerHTML = '<p class="text-muted text-center">No transactions yet</p>'; return; }
        let html = '';
        for (const tx of txs) {
            const isCredit = tx.is_credit || tx.type === 'deposit';
            const icon = isCredit ? 'fa-arrow-down' : 'fa-arrow-up';
            const cls = isCredit ? 'text-green' : 'text-red';
            const sign = isCredit ? '+' : '-';
            html += `
            <div class="tx-row">
                <div class="tx-icon ${cls}"><i class="fas ${icon}"></i></div>
                <div class="tx-info">
                    <div class="tx-desc">${tx.description || tx.type}</div>
                    <div class="tx-date text-muted">${Utils.timeAgo(tx.timestamp)}</div>
                </div>
                <div class="tx-amount ${cls}">${sign}${Utils.formatAmount(Math.abs(tx.amount), tx.coin || 'USDT')}</div>
            </div>`;
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<p class="text-muted text-center">Failed to load transactions</p>';
    }
}

async function refreshAll() {
    Utils.setBtnLoading('#refreshBtn');
    await Promise.all([loadBalance(), loadWallets(), loadMarketPrices(), loadEarnSummary(), loadRecentTransactions()]);
    Utils.setBtnLoading('#refreshBtn', false);
    Utils.showSuccess('Dashboard refreshed');
}

async function handleSearch() {
    const query = document.getElementById('searchInput').value.trim();
    const container = document.getElementById('searchResults');
    if (!container) return;
    if (!query || query.length < 1) { container.innerHTML = ''; return; }

    container.innerHTML = '<div class="search-loading"><div class="spinner"></div></div>';
    try {
        const data = await API.searchMarket(query);
        const results = data.results || [];
        if (!results.length) {
            container.innerHTML = '<div class="search-empty">No results found</div>';
            return;
        }
        let html = '';
        for (const r of results.slice(0, 20)) {
            const symbol = r.symbol || '';
            const coin = symbol.replace(/USDT$/, '').replace(/USD$/, '').replace(/BTC$/, '');
            const price = parseFloat(r.lastPrice || 0);
            const pct = parseFloat(r.price24hPcnt || 0) * 100;
            const isUp = pct >= 0;
            html += `
            <div class="search-result-item">
                <div class="search-coin">
                    <div class="coin-icon-sm" style="background:${Utils.getCoinColor(coin)}20;color:${Utils.getCoinColor(coin)}">
                        <i class="${Utils.getCoinIcon(coin)}"></i>
                    </div>
                    <div>
                        <div class="search-coin-name">${coin}</div>
                        <div class="search-coin-pair">${symbol}</div>
                    </div>
                </div>
                <div class="search-price">
                    <div class="search-price-value">$${Utils.formatCrypto(price, 2)}</div>
                    <div class="search-price-change ${isUp ? 'text-green' : 'text-red'}">
                        ${isUp ? '▲' : '▼'} ${Math.abs(pct).toFixed(2)}%
                    </div>
                </div>
            </div>`;
        }
        container.innerHTML = html;
    } catch (e) {
        container.innerHTML = '<div class="search-empty">Search failed</div>';
    }
}

window.addEventListener('beforeunload', () => { if (refreshInterval) clearInterval(refreshInterval); });
