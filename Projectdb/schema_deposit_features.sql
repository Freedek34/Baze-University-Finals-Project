-- CryptoVault - Deposit Features Schema (Step 3 of 4)
-- Tables: crypto_deposit_requests, fiat_purchase_requests, bybit_internal_transfers
-- Extends: p2p_orders, users (bybit_uid, display_name)
-- Requires: schema_postgres.sql, schema_crypto.sql
--
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_deposit_features.sql

\c cryptovault_db

-- On-chain crypto deposit requests (Deposit Crypto flow)
CREATE TABLE IF NOT EXISTS crypto_deposit_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coin VARCHAR(20) NOT NULL,
    network VARCHAR(50) NOT NULL,
    amount NUMERIC(20,8),
    deposit_address VARCHAR(255),
    tag_memo VARCHAR(100),
    status VARCHAR(32) DEFAULT 'awaiting_transfer',
    reference_number VARCHAR(50) UNIQUE,
    tx_hash VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_crypto_deposit_user ON crypto_deposit_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_crypto_deposit_status ON crypto_deposit_requests(status);

-- Fiat card purchases (Buy with NGN flow)
CREATE TABLE IF NOT EXISTS fiat_purchase_requests (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coin VARCHAR(20) NOT NULL DEFAULT 'USDT',
    fiat_currency VARCHAR(10) NOT NULL DEFAULT 'NGN',
    fiat_amount NUMERIC(15,2) NOT NULL,
    crypto_amount NUMERIC(20,8) NOT NULL,
    exchange_rate NUMERIC(15,4),
    card_last_four VARCHAR(4),
    status VARCHAR(32) DEFAULT 'pending',
    reference_number VARCHAR(50) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_fiat_purchase_user ON fiat_purchase_requests(user_id);

-- Internal transfers from another Bybit/CryptoVault user
CREATE TABLE IF NOT EXISTS bybit_internal_transfers (
    id SERIAL PRIMARY KEY,
    receiver_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    sender_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    amount NUMERIC(20,8) NOT NULL,
    coin VARCHAR(20) NOT NULL DEFAULT 'USDT',
    status VARCHAR(32) DEFAULT 'pending',
    reference_number VARCHAR(50) UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_bybit_transfer_receiver ON bybit_internal_transfers(receiver_id);
CREATE INDEX IF NOT EXISTS idx_bybit_transfer_sender ON bybit_internal_transfers(sender_id);

-- Extend P2P orders for deposit flow
ALTER TABLE p2p_orders ADD COLUMN IF NOT EXISTS payment_status VARCHAR(32) DEFAULT 'unpaid';
ALTER TABLE p2p_orders ADD COLUMN IF NOT EXISTS vendor_nickname VARCHAR(100);
ALTER TABLE p2p_orders ADD COLUMN IF NOT EXISTS reference_number VARCHAR(50);

-- Demo Bybit display names (optional alias for users)
ALTER TABLE users ADD COLUMN IF NOT EXISTS bybit_uid VARCHAR(50);
ALTER TABLE users ADD COLUMN IF NOT EXISTS display_name VARCHAR(100);

-- Seed demo Bybit UIDs for sample users
UPDATE users SET bybit_uid = 'BYB' || LPAD(id::text, 8, '0'),
                 display_name = username
WHERE bybit_uid IS NULL;

-- Additional demo users for "Receive from Bybit User" search
INSERT INTO users (username, email, password_hash, account_balance, bybit_uid, display_name) VALUES
('crypto_trader_ng', 'trader.ng@example.com', '$2b$12$ngH5T.JVcsjStTGzbrV9G.0HtMUxMLHDPeGiW4dXdTZUD3Wzlwf9e', 15000.00, 'BYB00001001', 'CryptoTrader_NG'),
('block_merchant', 'merchant@example.com', '$2b$12$ngH5T.JVcsjStTGzbrV9G.0HtMUxMLHDPeGiW4dXdTZUD3Wzlwf9e', 8500.00, 'BYB00001002', 'BlockMerchant'),
('swift_pay_otc', 'swift@example.com', '$2b$12$ngH5T.JVcsjStTGzbrV9G.0HtMUxMLHDPeGiW4dXdTZUD3Wzlwf9e', 22000.00, 'BYB00001003', 'SwiftPay_OTC')
ON CONFLICT (username) DO NOTHING;
