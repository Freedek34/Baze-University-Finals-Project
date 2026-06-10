/**
 * CryptoVault - API Service
 * Handles all communication with the backend
 */
const API = {
    getToken() { return localStorage.getItem(CONFIG.STORAGE_KEYS.TOKEN); },
    getSessionToken() { return localStorage.getItem(CONFIG.STORAGE_KEYS.SESSION_TOKEN); },
    setTokens(token, sessionToken) {
        if (token) localStorage.setItem(CONFIG.STORAGE_KEYS.TOKEN, token);
        if (sessionToken) localStorage.setItem(CONFIG.STORAGE_KEYS.SESSION_TOKEN, sessionToken);
    },
    clearAuth() {
        localStorage.removeItem(CONFIG.STORAGE_KEYS.TOKEN);
        localStorage.removeItem(CONFIG.STORAGE_KEYS.SESSION_TOKEN);
        localStorage.removeItem(CONFIG.STORAGE_KEYS.USER);
    },
    setUser(user) { localStorage.setItem(CONFIG.STORAGE_KEYS.USER, JSON.stringify(user)); },
    getUser() { const u = localStorage.getItem(CONFIG.STORAGE_KEYS.USER); return u ? JSON.parse(u) : null; },
    isAuthenticated() { return !!this.getToken() || !!this.getSessionToken(); },

    async request(endpoint, options = {}) {
        const url = `${CONFIG.API_BASE_URL}${endpoint}`;
        const headers = { 'Content-Type': 'application/json', ...options.headers };
        const token = this.getToken();
        const sessionToken = this.getSessionToken();
        console.log('API Request:', { url, hasToken: !!token, hasSession: !!sessionToken });
        if (token) headers['Authorization'] = `Bearer ${token}`;
        if (sessionToken) headers['X-Session-Token'] = sessionToken;
        try {
            const response = await fetch(url, { ...options, headers, mode: 'cors' });
            console.log('API Response status:', response.status);
            const data = await response.json();
            if (!response.ok) {
                if (response.status === 401) { 
                    console.warn('Unauthorized, clearing auth and redirecting');
                    this.clearAuth(); 
                    window.location.href = 'login.html'; 
                    return; 
                }
                throw new Error(data.error || 'An error occurred');
            }
            return data;
        } catch (error) { console.error('API Error:', error); throw error; }
    },

    async get(endpoint) { return this.request(endpoint, { method: 'GET' }); },
    async post(endpoint, data) { return this.request(endpoint, { method: 'POST', body: JSON.stringify(data) }); },
    async put(endpoint, data) { return this.request(endpoint, { method: 'PUT', body: JSON.stringify(data) }); },
    async del(endpoint) { return this.request(endpoint, { method: 'DELETE' }); },

    // ── Auth ──
    async login(username, password) {
        const data = await this.post('/auth/login', { username, password });
        if (data.token) { this.setTokens(data.token, data.session_token); this.setUser(data.user); }
        return data;
    },
    async register(username, email, password) { return this.post('/auth/register', { username, email, password }); },
    async logout() { try { await this.post('/auth/logout', {}); } finally { this.clearAuth(); } },
    async getCurrentUser() { return this.get('/auth/me'); },

    // ── Account ──
    async getBalance(coin = null) {
        return this.get(`/account/balance${coin ? '?coin=' + encodeURIComponent(coin) : ''}`);
    },
    async deposit(amount, coin = 'USDT') { return this.post('/account/deposit', { amount, coin }); },

    // ── Deposit Flows ──
    async initCryptoDeposit(coin, network, amount = null) {
        return this.post('/deposit/crypto/init', { coin, network, amount });
    },
    async confirmCryptoDeposit(requestId, amount) {
        return this.post(`/deposit/crypto/${requestId}/confirm`, { amount });
    },
    async initFiatPurchase(coin, fiatAmount, cardNumber, fiatCurrency = 'NGN') {
        return this.post('/deposit/fiat/init', { coin, fiat_amount: fiatAmount, card_number: cardNumber, fiat_currency: fiatCurrency });
    },
    async completeFiatPurchase(requestId) {
        return this.post(`/deposit/fiat/${requestId}/complete`, {});
    },
    async searchBybitUsers(query) {
        return this.get(`/deposit/bybit-user/search?q=${encodeURIComponent(query)}`);
    },
    async initBybitUserTransfer(senderUsername, amount, coin = 'USDT') {
        return this.post('/deposit/bybit-user/init', { sender_username: senderUsername, amount, coin });
    },
    async approveBybitUserTransfer(transferId) {
        return this.post(`/deposit/bybit-user/${transferId}/approve`, {});
    },
    async createP2PDepositOrder(data) {
        return this.post('/deposit/p2p/order', data);
    },
    async markP2POrderPaid(orderId) {
        return this.post(`/deposit/p2p/order/${orderId}/mark-paid`, {});
    },
    async releaseP2PDeposit(orderId) {
        return this.post(`/deposit/p2p/order/${orderId}/release`, {});
    },

    // ── Wallet ──
    async getWalletBalances() { return this.get('/wallet/balances'); },
    async syncWallet() { return this.post('/wallet/sync', {}); },

    // ── Transfer ──
    async lookupUser(username) { return this.get(`/transfer/lookup?username=${encodeURIComponent(username)}`); },
    async sendMoney(receiverUsername, amount, description, coin = 'USDT') {
        return this.post('/transfer/send', { receiver_username: receiverUsername, amount, description, coin });
    },

    // ── Transactions ──
    async getTransactions(limit = 50, offset = 0) { return this.get(`/transactions?limit=${limit}&offset=${offset}`); },

    // ── Market ──
    async getMarketPrices() { return this.get('/market/prices'); },
    async getMarketTickers(category = 'spot', symbol = '') {
        return this.get(`/market/tickers?category=${category}${symbol ? '&symbol=' + symbol : ''}`);
    },
    async getKline(symbol, interval = '60', limit = 100) {
        return this.get(`/market/kline?symbol=${symbol}&interval=${interval}&limit=${limit}`);
    },
    async searchMarket(query, category = 'spot') {
        return this.get(`/market/search?q=${encodeURIComponent(query)}&category=${category}`);
    },

    // ── Wallet / Deposit / Withdraw ──
    async getDepositAddress(coin, chain = '') {
        return this.get(`/wallet/deposit-address?coin=${coin}${chain ? '&chain=' + chain : ''}`);
    },
    async getCoinInfo(coin = '') {
        return this.get(`/wallet/coin-info${coin ? '?coin=' + coin : ''}`);
    },
    async withdraw(coin, chain, address, amount, tag = '') {
        return this.post('/wallet/withdraw', { coin, chain, address, amount, tag });
    },

    // ── Earn (Bybit Savings) ──
    async getEarnProducts(coin = '') { return this.get(`/earn/products${coin ? '?coin=' + coin : ''}`); },
    async subscribeEarn(productId, amount, coin, productType, apy) {
        return this.post('/earn/subscribe', { product_id: productId, amount, coin, product_type: productType, apy });
    },
    async getEarnPositions(status = '') { return this.get(`/earn/positions${status ? '?status=' + status : ''}`); },
    async redeemEarn(positionId) { return this.post(`/earn/redeem/${positionId}`, {}); },
    async syncEarnPositions() { return this.post('/earn/sync', {}); },

    // ── P2P ──
    async getP2PAds(token = 'USDT', currency = 'NGN', side = '0', page = 1) {
        return this.get(`/p2p/ads?token=${token}&currency=${currency}&side=${side}&page=${page}`);
    },
    async getMyP2PAds() { return this.get('/p2p/my-ads'); },
    async createP2PAd(data) { return this.post('/p2p/create-ad', data); },
    async getP2POrders(page = 1) { return this.get(`/p2p/orders?page=${page}`); },
    async getP2PPending() { return this.get('/p2p/pending'); },
    async getP2PPaymentMethods() { return this.get('/p2p/payment-methods'); },

    // ── Settings ──
    async getApiKeys() { return this.get('/settings/api-keys'); },
    async saveApiKey(apiKey, apiSecret, label, isTestnet) {
        return this.post('/settings/api-keys', { api_key: apiKey, api_secret: apiSecret, label, is_testnet: isTestnet });
    },
    async deleteApiKey(keyId) { return this.del(`/settings/api-keys/${keyId}`); },

    // ── Watchlist ──
    async getWatchlist() { return this.get('/watchlist'); },
    async addToWatchlist(symbol) { return this.post('/watchlist', { symbol }); },
    async removeFromWatchlist(symbol) { return this.del(`/watchlist/${symbol}`); },
};

// Guard: surface missing methods clearly (usually stale cached api.js)
if (typeof API.initCryptoDeposit !== 'function') {
    console.error('CryptoVault: api.js is outdated. Hard-refresh the page (Ctrl+Shift+R).');
}
