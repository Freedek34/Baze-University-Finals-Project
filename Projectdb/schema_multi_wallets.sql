-- CryptoVault - Multi-Coin Wallet Schema (Step 4 of 4)
-- Tables: supported_assets, fiat_wallets, wallet_ledger
-- Migrates account_balance → per-coin crypto_wallets; seeds demo holdings
-- Views: user_portfolio, user_portfolio_summary
-- Requires: steps 1–3
--
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_multi_wallets.sql

\c cryptovault_db

-- ══════════════════════════════════════════════════════════════
-- REFERENCE: Supported crypto assets
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS supported_assets (
    id SERIAL PRIMARY KEY,
    coin VARCHAR(20) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    decimals INTEGER DEFAULT 8,
    usd_price_estimate NUMERIC(20,8) NOT NULL DEFAULT 0,
    min_withdraw NUMERIC(20,8) DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    sort_order INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

INSERT INTO supported_assets (coin, name, symbol, decimals, usd_price_estimate, min_withdraw, sort_order) VALUES
('USDT', 'Tether USD', 'USDT', 2, 1.00, 10, 1),
('BTC',  'Bitcoin', 'BTC', 8, 68200.00, 0.0001, 2),
('ETH',  'Ethereum', 'ETH', 8, 3600.00, 0.001, 3),
('SOL',  'Solana', 'SOL', 8, 145.00, 0.1, 4),
('BNB',  'BNB', 'BNB', 8, 585.00, 0.01, 5),
('XRP',  'Ripple', 'XRP', 6, 0.52, 20, 6),
('ADA',  'Cardano', 'ADA', 6, 0.45, 10, 7),
('DOGE', 'Dogecoin', 'DOGE', 8, 0.12, 50, 8),
('AVAX', 'Avalanche', 'AVAX', 8, 28.75, 0.1, 9),
('USDC', 'USD Coin', 'USDC', 2, 1.00, 10, 10)
ON CONFLICT (coin) DO UPDATE SET
    usd_price_estimate = EXCLUDED.usd_price_estimate,
    name = EXCLUDED.name;

-- ══════════════════════════════════════════════════════════════
-- FIAT wallets (NGN / USD for P2P realism)
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS fiat_wallets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    currency_id VARCHAR(10) NOT NULL,
    available_balance NUMERIC(15,2) DEFAULT 0,
    locked_balance NUMERIC(15,2) DEFAULT 0,
    total_balance NUMERIC(15,2) DEFAULT 0,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    UNIQUE(user_id, currency_id)
);

CREATE INDEX IF NOT EXISTS idx_fiat_wallet_user ON fiat_wallets(user_id);

-- ══════════════════════════════════════════════════════════════
-- Wallet ledger (audit trail per coin)
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS wallet_ledger (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    coin VARCHAR(20) NOT NULL,
    amount NUMERIC(20,8) NOT NULL,
    balance_after NUMERIC(20,8) NOT NULL,
    entry_type VARCHAR(32) NOT NULL,
    reference_number VARCHAR(50),
    description VARCHAR(255),
    related_user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ledger_user ON wallet_ledger(user_id);
CREATE INDEX IF NOT EXISTS idx_ledger_coin ON wallet_ledger(coin);
CREATE INDEX IF NOT EXISTS idx_ledger_created ON wallet_ledger(created_at);

-- ══════════════════════════════════════════════════════════════
-- Enhance crypto_wallets
-- ══════════════════════════════════════════════════════════════
ALTER TABLE crypto_wallets ADD COLUMN IF NOT EXISTS wallet_label VARCHAR(50) DEFAULT 'Funding';
ALTER TABLE crypto_wallets ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE crypto_wallets ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT now();
ALTER TABLE crypto_wallets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT now();

-- ══════════════════════════════════════════════════════════════
-- Migrate legacy users.account_balance → USDT funding wallet
-- ══════════════════════════════════════════════════════════════
INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, 'USDT', 'FUND', 'Funding', u.account_balance, 0, u.account_balance, u.account_balance
FROM users u
WHERE COALESCE(u.account_balance, 0) > 0
ON CONFLICT (user_id, coin, account_type) DO UPDATE SET
    available_balance = GREATEST(crypto_wallets.available_balance, EXCLUDED.available_balance),
    total_balance = GREATEST(crypto_wallets.total_balance, EXCLUDED.total_balance),
    usd_value = GREATEST(crypto_wallets.usd_value, EXCLUDED.usd_value),
    updated_at = now();

-- Ensure every user has a zero wallet row for each supported asset
INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, a.coin, 'FUND', 'Funding', 0, 0, 0, 0
FROM users u
CROSS JOIN supported_assets a
WHERE a.is_active = TRUE
ON CONFLICT (user_id, coin, account_type) DO NOTHING;

-- ══════════════════════════════════════════════════════════════
-- Seed realistic multi-coin balances for demo users
-- ══════════════════════════════════════════════════════════════
-- demo_user (id may vary — match by username)
INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, v.coin, 'FUND', 'Funding', v.bal, 0, v.bal, v.bal * a.usd_price_estimate
FROM users u
CROSS JOIN (VALUES
    ('USDT', 2500.00::numeric),
    ('BTC',  0.05200000::numeric),
    ('ETH',  1.25000000::numeric),
    ('SOL',  18.50000000::numeric),
    ('BNB',  3.20000000::numeric),
    ('XRP',  5000.000000::numeric)
) AS v(coin, bal)
JOIN supported_assets a ON a.coin = v.coin
WHERE u.username = 'demo_user'
ON CONFLICT (user_id, coin, account_type) DO UPDATE SET
    available_balance = EXCLUDED.available_balance,
    total_balance = EXCLUDED.total_balance,
    usd_value = EXCLUDED.usd_value,
    updated_at = now();

INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, v.coin, 'FUND', 'Funding', v.bal, 0, v.bal, v.bal * a.usd_price_estimate
FROM users u
CROSS JOIN (VALUES
    ('USDT', 1200.00::numeric),
    ('BTC',  0.01500000::numeric),
    ('ETH',  0.45000000::numeric),
    ('SOL',  5.00000000::numeric)
) AS v(coin, bal)
JOIN supported_assets a ON a.coin = v.coin
WHERE u.username = 'test_user'
ON CONFLICT (user_id, coin, account_type) DO UPDATE SET
    available_balance = EXCLUDED.available_balance,
    total_balance = EXCLUDED.total_balance,
    usd_value = EXCLUDED.usd_value,
    updated_at = now();

INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, v.coin, 'FUND', 'Funding', v.bal, 0, v.bal, v.bal * a.usd_price_estimate
FROM users u
CROSS JOIN (VALUES
    ('USDT', 8000.00::numeric),
    ('BTC',  0.12000000::numeric),
    ('ETH',  4.50000000::numeric),
    ('BNB',  12.00000000::numeric)
) AS v(coin, bal)
JOIN supported_assets a ON a.coin = v.coin
WHERE u.username = 'crypto_trader_ng'
ON CONFLICT (user_id, coin, account_type) DO UPDATE SET
    available_balance = EXCLUDED.available_balance,
    total_balance = EXCLUDED.total_balance,
    usd_value = EXCLUDED.usd_value,
    updated_at = now();

INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, v.coin, 'FUND', 'Funding', v.bal, 0, v.bal, v.bal * a.usd_price_estimate
FROM users u
CROSS JOIN (VALUES
    ('USDT', 4200.00::numeric),
    ('ETH',  2.10000000::numeric),
    ('SOL',  25.00000000::numeric)
) AS v(coin, bal)
JOIN supported_assets a ON a.coin = v.coin
WHERE u.username = 'block_merchant'
ON CONFLICT (user_id, coin, account_type) DO UPDATE SET
    available_balance = EXCLUDED.available_balance,
    total_balance = EXCLUDED.total_balance,
    usd_value = EXCLUDED.usd_value,
    updated_at = now();

-- swift_pay_otc
INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, 'USDT', 'FUND', 'Funding', 12000, 0, 12000, 12000
FROM users u WHERE u.username = 'swift_pay_otc'
ON CONFLICT (user_id, coin, account_type) DO UPDATE SET
    available_balance = 12000, total_balance = 12000, usd_value = 12000, updated_at = now();

INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
SELECT u.id, 'BTC', 'FUND', 'Funding', 0.25, 0, 0.25, 0.25 * 68200
FROM users u WHERE u.username = 'swift_pay_otc'
ON CONFLICT (user_id, coin, account_type) DO UPDATE SET
    available_balance = 0.25, total_balance = 0.25, usd_value = 0.25 * 68200, updated_at = now();

-- Seed fiat wallets (NGN for P2P)
INSERT INTO fiat_wallets (user_id, currency_id, available_balance, locked_balance, total_balance)
SELECT u.id, 'NGN', 
    CASE u.username
        WHEN 'demo_user' THEN 850000.00
        WHEN 'test_user' THEN 320000.00
        WHEN 'crypto_trader_ng' THEN 2500000.00
        WHEN 'block_merchant' THEN 980000.00
        WHEN 'swift_pay_otc' THEN 5200000.00
        ELSE 100000.00
    END, 0,
    CASE u.username
        WHEN 'demo_user' THEN 850000.00
        WHEN 'test_user' THEN 320000.00
        WHEN 'crypto_trader_ng' THEN 2500000.00
        WHEN 'block_merchant' THEN 980000.00
        WHEN 'swift_pay_otc' THEN 5200000.00
        ELSE 100000.00
    END
FROM users u
ON CONFLICT (user_id, currency_id) DO UPDATE SET
    available_balance = EXCLUDED.available_balance,
    total_balance = EXCLUDED.total_balance,
    updated_at = now();

-- Sync users.account_balance to total portfolio USD (backward compatibility)
UPDATE users u SET account_balance = sub.total_usd, updated_at = now()
FROM (
    SELECT user_id, COALESCE(SUM(usd_value), 0) AS total_usd
    FROM crypto_wallets
    WHERE is_active = TRUE
    GROUP BY user_id
) sub
WHERE u.id = sub.user_id;

-- Portfolio view
CREATE OR REPLACE VIEW user_portfolio AS
SELECT
    cw.user_id,
    u.username,
    cw.coin,
    sa.name AS asset_name,
    cw.account_type,
    cw.wallet_label,
    cw.available_balance,
    cw.locked_balance,
    cw.total_balance,
    cw.usd_value,
    sa.usd_price_estimate,
    ROUND(cw.total_balance * sa.usd_price_estimate, 2) AS calculated_usd,
    cw.last_synced,
    cw.updated_at
FROM crypto_wallets cw
JOIN users u ON u.id = cw.user_id
LEFT JOIN supported_assets sa ON sa.coin = cw.coin
WHERE cw.is_active = TRUE AND cw.total_balance > 0
ORDER BY cw.usd_value DESC;

-- Portfolio summary view
CREATE OR REPLACE VIEW user_portfolio_summary AS
SELECT
    u.id AS user_id,
    u.username,
    COALESCE(SUM(cw.usd_value), 0) AS total_crypto_usd,
    COALESCE(SUM(cw.available_balance * sa.usd_price_estimate) FILTER (WHERE cw.coin = 'USDT'), 0) AS usdt_value,
    COUNT(DISTINCT cw.coin) FILTER (WHERE cw.total_balance > 0) AS coin_count,
    COALESCE(fw.available_balance, 0) AS ngn_balance
FROM users u
LEFT JOIN crypto_wallets cw ON cw.user_id = u.id AND cw.is_active = TRUE
LEFT JOIN supported_assets sa ON sa.coin = cw.coin
LEFT JOIN fiat_wallets fw ON fw.user_id = u.id AND fw.currency_id = 'NGN'
GROUP BY u.id, u.username, fw.available_balance;
