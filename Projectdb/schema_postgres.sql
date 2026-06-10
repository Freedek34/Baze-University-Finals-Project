-- CryptoVault - PostgreSQL Schema (Step 1 of 4)
-- Core tables: users, transactions, sessions
--
-- Full setup order:
--   1. schema_postgres.sql
--   2. schema_crypto.sql
--   3. schema_deposit_features.sql
--   4. schema_multi_wallets.sql
--
-- Or run: setup_database.ps1  /  schema_all.sql
--
-- CREATE DATABASE cryptovault_db;  -- run once as superuser if needed
\c cryptovault_db

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    email VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    account_balance NUMERIC(15,2) DEFAULT 0.00,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    is_active BOOLEAN DEFAULT TRUE
);

-- Transactions table
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    sender_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    receiver_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    amount NUMERIC(15,2) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT now(),
    transaction_type VARCHAR(32) NOT NULL,
    description VARCHAR(255),
    reference_number VARCHAR(50) UNIQUE,
    status VARCHAR(32) DEFAULT 'completed'
);

CREATE INDEX IF NOT EXISTS idx_sender ON transactions(sender_id);
CREATE INDEX IF NOT EXISTS idx_receiver ON transactions(receiver_id);
CREATE INDEX IF NOT EXISTS idx_timestamp ON transactions(timestamp);

-- Savings plans
CREATE TABLE IF NOT EXISTS savings_plans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_type VARCHAR(32) NOT NULL,
    locked_amount NUMERIC(15,2) NOT NULL,
    interest_rate NUMERIC(5,2) NOT NULL,
    lock_date TIMESTAMP WITH TIME ZONE DEFAULT now(),
    maturity_date TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(32) DEFAULT 'active',
    expected_interest NUMERIC(15,2) DEFAULT 0.00,
    actual_interest_paid NUMERIC(15,2) DEFAULT 0.00,
    target_amount NUMERIC(15,2),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user ON savings_plans(user_id);
CREATE INDEX IF NOT EXISTS idx_status ON savings_plans(status);
CREATE INDEX IF NOT EXISTS idx_maturity ON savings_plans(maturity_date);

-- Tax records
CREATE TABLE IF NOT EXISTS tax_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    estimated_tax NUMERIC(15,2) NOT NULL,
    tax_paid_from_savings NUMERIC(15,2) DEFAULT 0.00,
    calculation_date TIMESTAMP WITH TIME ZONE DEFAULT now(),
    tax_year INTEGER NOT NULL,
    income_amount NUMERIC(15,2) DEFAULT 0.00,
    suggested_lock_amount NUMERIC(15,2) DEFAULT 0.00,
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_user_tax ON tax_records(user_id);
CREATE INDEX IF NOT EXISTS idx_tax_year ON tax_records(tax_year);

-- Sessions
CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(255),
    is_valid BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_session_token ON user_sessions(session_token);

-- Sample data (password is 'password123' hashed with bcrypt)
INSERT INTO users (username, email, password_hash, account_balance) VALUES
('demo_user', 'demo@example.com', '$2b$12$ngH5T.JVcsjStTGzbrV9G.0HtMUxMLHDPeGiW4dXdTZUD3Wzlwf9e', 5000.00),
('test_user', 'test@example.com', '$2b$12$ngH5T.JVcsjStTGzbrV9G.0HtMUxMLHDPeGiW4dXdTZUD3Wzlwf9e', 2500.00)
ON CONFLICT (username) DO NOTHING;

-- View similar to transaction_history
CREATE OR REPLACE VIEW transaction_history AS
SELECT 
    t.id,
    t.amount,
    t.timestamp,
    t.transaction_type,
    t.description,
    t.reference_number,
    t.status,
    s.username AS sender_username,
    r.username AS receiver_username
FROM transactions t
LEFT JOIN users s ON t.sender_id = s.id
LEFT JOIN users r ON t.receiver_id = r.id;
