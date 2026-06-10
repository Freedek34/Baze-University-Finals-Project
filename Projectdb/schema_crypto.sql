-- CryptoVault - PostgreSQL Schema (Step 2 of 4)
-- Crypto tables: crypto_wallets, earn_positions, p2p_ads/orders, watchlist
-- Requires: schema_postgres.sql
--
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_crypto.sql

\c cryptovault_db

-- Drop old banking tables
DROP TABLE IF EXISTS tax_records CASCADE;
DROP TABLE IF EXISTS savings_plans CASCADE;
DROP VIEW IF EXISTS transaction_history CASCADE;

-- Keep users table but add crypto fields
ALTER TABLE users ADD COLUMN IF NOT EXISTS preferred_currency VARCHAR(10) DEFAULT 'USDT';
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(255);

-- Bybit API keys (encrypted at rest ideally)
CREATE TABLE IF NOT EXISTS bybit_api_keys (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    api_key VARCHAR(255) NOT NULL,
    api_secret_encrypted VARCHAR(512) NOT NULL,
    label VARCHAR(100) DEFAULT 'Default',
    permissions VARCHAR(255) DEFAULT 'read',
    is_testnet BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, label)
);

CREATE INDEX IF NOT EXISTS idx_bybit_keys_user ON bybit_api_keys(user_id);

-- Cached wallet balances (refreshed periodically from Bybit)
CREATE TABLE IF NOT EXISTS crypto_wallets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coin VARCHAR(20) NOT NULL,
    account_type VARCHAR(20) NOT NULL DEFAULT 'UNIFIED',
    available_balance NUMERIC(20,8) DEFAULT 0,
    locked_balance NUMERIC(20,8) DEFAULT 0,
    total_balance NUMERIC(20,8) DEFAULT 0,
    usd_value NUMERIC(15,2) DEFAULT 0,
    last_synced TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, coin, account_type)
);

CREATE INDEX IF NOT EXISTS idx_wallet_user ON crypto_wallets(user_id);

-- Bybit Earn positions (savings products)
CREATE TABLE IF NOT EXISTS earn_positions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bybit_order_id VARCHAR(100),
    product_id VARCHAR(100) NOT NULL,
    product_type VARCHAR(50) NOT NULL,
    coin VARCHAR(20) NOT NULL,
    amount NUMERIC(20,8) NOT NULL,
    apy NUMERIC(8,4) NOT NULL,
    accrued_interest NUMERIC(20,8) DEFAULT 0,
    status VARCHAR(32) DEFAULT 'active',
    subscribed_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    redeemed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_earn_user ON earn_positions(user_id);
CREATE INDEX IF NOT EXISTS idx_earn_status ON earn_positions(status);

-- P2P advertisements (cached/managed locally)
CREATE TABLE IF NOT EXISTS p2p_ads (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bybit_item_id VARCHAR(100),
    token_id VARCHAR(20) NOT NULL,
    currency_id VARCHAR(10) NOT NULL,
    side INTEGER NOT NULL,
    price NUMERIC(15,2) NOT NULL,
    quantity NUMERIC(20,8) NOT NULL,
    min_amount NUMERIC(15,2) NOT NULL,
    max_amount NUMERIC(15,2) NOT NULL,
    payment_methods TEXT,
    remark TEXT,
    status VARCHAR(32) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_p2p_ads_user ON p2p_ads(user_id);

-- P2P orders
CREATE TABLE IF NOT EXISTS p2p_orders (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    bybit_order_id VARCHAR(100),
    ad_id INTEGER REFERENCES p2p_ads(id),
    token_id VARCHAR(20) NOT NULL,
    currency_id VARCHAR(10) NOT NULL,
    side INTEGER NOT NULL,
    amount NUMERIC(20,8) NOT NULL,
    price NUMERIC(15,2) NOT NULL,
    total_price NUMERIC(15,2) NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',
    counterparty_name VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_p2p_orders_user ON p2p_orders(user_id);

-- Update transactions table for crypto
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS coin VARCHAR(20) DEFAULT 'USDT';
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS tx_hash VARCHAR(255);
ALTER TABLE transactions ADD COLUMN IF NOT EXISTS network VARCHAR(50);

-- Watchlist / favorite coins
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(30) NOT NULL,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, symbol)
);

-- Price alerts
CREATE TABLE IF NOT EXISTS price_alerts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    symbol VARCHAR(30) NOT NULL,
    target_price NUMERIC(20,8) NOT NULL,
    direction VARCHAR(10) NOT NULL,
    is_triggered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Update sample data
UPDATE users SET preferred_currency = 'USDT' WHERE preferred_currency IS NULL;

-- Transaction history view (updated)
CREATE OR REPLACE VIEW transaction_history AS
SELECT 
    t.id,
    t.amount,
    t.coin,
    t.timestamp,
    t.transaction_type,
    t.description,
    t.reference_number,
    t.status,
    t.tx_hash,
    s.username as sender_username,
    r.username as receiver_username
FROM transactions t
LEFT JOIN users s ON t.sender_id = s.id
LEFT JOIN users r ON t.receiver_id = r.id
ORDER BY t.timestamp DESC;
