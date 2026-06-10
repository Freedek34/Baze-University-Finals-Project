/**
 * CryptoVault - Configuration
 * Third-party crypto banking powered by Bybit
 */
const CONFIG = {
    /** Bump when JS changes so browsers reload cached scripts */
    ASSET_VERSION: '20250609b',
    API_BASE_URL: 'http://localhost:5000/api',

    STORAGE_KEYS: {
        TOKEN: 'cv_token',
        SESSION_TOKEN: 'cv_session',
        USER: 'cv_user',
        REMEMBER_ME: 'cv_remember'
    },

    // Supported coins
    COINS: ['BTC', 'ETH', 'USDT', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX'],

    // Popular trading pairs
    PAIRS: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT'],

    // Coin icons (Font Awesome class mapping)
    COIN_ICONS: {
        BTC: 'fab fa-bitcoin',
        ETH: 'fab fa-ethereum',
        USDT: 'fas fa-dollar-sign',
        SOL: 'fas fa-sun',
        BNB: 'fas fa-coins',
        XRP: 'fas fa-water',
        ADA: 'fas fa-cube',
        DOGE: 'fas fa-dog',
        AVAX: 'fas fa-mountain',
    },

    // Coin colors
    COIN_COLORS: {
        BTC: '#f7931a',
        ETH: '#627eea',
        USDT: '#26a17b',
        SOL: '#9945ff',
        BNB: '#f0b90b',
        XRP: '#23292f',
        ADA: '#0033ad',
        DOGE: '#c3a634',
        AVAX: '#e84142',
    },

    CURRENCY: {
        symbol: '$',
        code: 'USD',
        locale: 'en-US'
    },

    PAGINATION: {
        defaultLimit: 20,
        maxLimit: 100
    }
};

Object.freeze(CONFIG);
