-- CryptoVault - Complete Database Setup
-- Run all migrations in the correct order (fresh install or re-run safe migrations).
--
-- Windows (PowerShell, from Projectdb folder):
--   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_all.sql
--
-- Or run setup_database.ps1 from this folder.
--
-- Order:
--   1. schema_postgres.sql   — users, transactions, sessions
--   2. schema_crypto.sql     — crypto wallets, earn, P2P, watchlist
--   3. schema_deposit_features.sql — deposit flows, Bybit user search
--   4. schema_multi_wallets.sql   — per-coin wallets, fiat, ledger, seeds

\c cryptovault_db

\echo '=== [1/4] Core schema ==='
\ir schema_postgres.sql

\echo '=== [2/4] Crypto & Bybit tables ==='
\ir schema_crypto.sql

\echo '=== [3/4] Deposit feature tables ==='
\ir schema_deposit_features.sql

\echo '=== [4/4] Multi-coin wallets ==='
\ir schema_multi_wallets.sql

\echo '=== Database setup complete ==='
