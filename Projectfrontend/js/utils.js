/**
 * CryptoVault - Utility Functions
 */
const Utils = {
    formatCurrency(amount, currency = 'USD') {
        const num = parseFloat(amount);
        if (isNaN(num)) return '$0.00';
        return new Intl.NumberFormat('en-US', { style: 'currency', currency }).format(num);
    },

    formatCrypto(amount, decimals = 6) {
        const num = parseFloat(amount);
        if (isNaN(num)) return '0';
        if (num === 0) return '0';
        if (num < 0.000001) return num.toExponential(2);
        return num.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: decimals });
    },

    formatPercent(value, decimals = 2) {
        const num = parseFloat(value);
        if (isNaN(num)) return '0%';
        return num.toFixed(decimals) + '%';
    },

    formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
    },

    formatDateTime(dateStr) {
        if (!dateStr) return 'N/A';
        const d = new Date(dateStr);
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    },

    timeAgo(dateStr) {
        const now = new Date();
        const d = new Date(dateStr);
        const diff = Math.floor((now - d) / 1000);
        if (diff < 60) return 'just now';
        if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
        if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
        if (diff < 604800) return Math.floor(diff / 86400) + 'd ago';
        return Utils.formatDate(dateStr);
    },

    getCoinIcon(coin) {
        return CONFIG.COIN_ICONS[coin] || CONFIG.COIN_ICONS.DEFAULT;
    },

    getCoinColor(coin) {
        return CONFIG.COIN_COLORS[coin] || CONFIG.COIN_COLORS.DEFAULT;
    },

    getCoinBadge(coin) {
        const icon = Utils.getCoinIcon(coin);
        const color = Utils.getCoinColor(coin);
        return `<span class="coin-badge" style="color:${color}"><i class="${icon}"></i> ${coin}</span>`;
    },

    formatAmount(amount, coin = 'USDT') {
        if (['USDT', 'USDC'].includes(coin)) return '$' + Utils.formatCrypto(amount, 2);
        return Utils.formatCrypto(amount, 6) + ' ' + coin;
    },

    priceChange(current, previous) {
        if (!previous || previous == 0) return { value: 0, percent: 0, direction: 'neutral' };
        const change = current - previous;
        const pct = (change / previous) * 100;
        return { value: change, percent: pct, direction: change > 0 ? 'up' : change < 0 ? 'down' : 'neutral' };
    },

    priceChangeHTML(change) {
        const cls = change.direction === 'up' ? 'text-green' : change.direction === 'down' ? 'text-red' : 'text-muted';
        const arrow = change.direction === 'up' ? '▲' : change.direction === 'down' ? '▼' : '';
        return `<span class="${cls}">${arrow} ${Utils.formatPercent(Math.abs(change.percent))}</span>`;
    },

    truncateAddress(addr, len = 6) {
        if (!addr || addr.length <= len * 2) return addr || '';
        return addr.slice(0, len) + '...' + addr.slice(-len);
    },

    showToast(message, type = 'info', duration = 3500) {
        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            document.body.appendChild(container);
        }
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        const icons = { success: 'fa-check-circle', error: 'fa-exclamation-circle', warning: 'fa-exclamation-triangle', info: 'fa-info-circle' };
        toast.innerHTML = `<i class="fas ${icons[type] || icons.info}"></i><span>${message}</span>`;
        container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('show'));
        setTimeout(() => { toast.classList.remove('show'); setTimeout(() => toast.remove(), 300); }, duration);
    },

    showSuccess(msg) { Utils.showToast(msg, 'success'); },
    showError(msg) { Utils.showToast(msg, 'error'); },
    showWarning(msg) { Utils.showToast(msg, 'warning'); },
    showInfo(msg) { Utils.showToast(msg, 'info'); },

    showLoading(el) {
        if (typeof el === 'string') el = document.querySelector(el);
        if (!el) return;
        el.classList.add('loading');
        el.innerHTML = '<div class="spinner"></div>';
    },

    hideLoading(el) {
        if (typeof el === 'string') el = document.querySelector(el);
        if (!el) return;
        el.classList.remove('loading');
    },

    setBtnLoading(btn, loading = true) {
        if (typeof btn === 'string') btn = document.querySelector(btn);
        if (!btn) return;
        if (loading) { btn.disabled = true; btn.dataset.originalText = btn.innerHTML; btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Loading...'; }
        else { btn.disabled = false; btn.innerHTML = btn.dataset.originalText || btn.innerHTML; }
    },

    checkAuth() {
        if (!API.isAuthenticated()) { window.location.href = 'login.html'; return false; }
        return true;
    },

    debounce(fn, delay = 300) {
        let timer;
        return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn.apply(null, args), delay); };
    },

    copyToClipboard(text) {
        navigator.clipboard.writeText(text).then(() => Utils.showSuccess('Copied!'));
    },

    miniChart(data, width = 80, height = 30) {
        if (!data || data.length < 2) return '';
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min || 1;
        const step = width / (data.length - 1);
        const points = data.map((v, i) => `${(i * step).toFixed(1)},${(height - ((v - min) / range) * height).toFixed(1)}`).join(' ');
        const isUp = data[data.length - 1] >= data[0];
        const color = isUp ? '#00c853' : '#ff1744';
        return `<svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}"><polyline fill="none" stroke="${color}" stroke-width="1.5" points="${points}"/></svg>`;
    }
};
