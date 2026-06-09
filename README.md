# CryptoVault - Crypto Banking Platform

A full-stack crypto banking application powered by Bybit, built with Python Flask, PostgreSQL, and vanilla JavaScript. Supports **multi-coin wallets**, deposit flows, P2P trading, Bybit Earn, on-chain receive/withdraw, and internal transfers.

## Features

### User Authentication
- Secure registration with bcrypt password hashing
- JWT + session token authentication
- Auto-provisioned per-coin wallets on signup

### Multi-Coin Wallets
- Separate funding wallets per asset (USDT, BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, USDC)
- Fiat NGN wallet for P2P trading
- Wallet ledger audit trail for all credits/debits
- Portfolio total in USD synced across dashboard and API

### Dashboard
- Total portfolio value (USD) and per-asset breakdown
- Live market prices (Bybit API with demo fallback)
- Deposit payment-method sheet (Bybit-style)
- Recent transactions and earn summary

### Deposit Flows (Demo)
| Method | Description |
|--------|-------------|
| **Deposit Crypto** | Select coin → network → deposit address + QR → confirm sent |
| **P2P Trading** | Buy from marketplace sellers → pay fiat → receive crypto |
| **Buy with NGN** | Card purchase demo (Visa/Mastercard) |
| **Receive from Bybit User** | Search users → request transfer → approve |

### Send & Receive
- Internal transfers between users (per-coin balance checks)
- On-chain receive page with network selection and QR codes
- On-chain withdraw with in-app confirmation modal

### Portfolio & Earn
- Multi-coin wallet holdings + NGN fiat balance
- Bybit Earn products (demo fallback when API unavailable)
- Subscribe/redeem with per-coin balance deduction

### P2P Trading
- Marketplace with demo vendors when Bybit API times out
- Full buy flow: select seller → pay → verify → release crypto

## Technology Stack

| Layer | Stack |
|-------|-------|
| Backend | Python 3.8+, Flask, Flask-CORS, PyJWT, psycopg2, bcrypt, pybit |
| Frontend | HTML5, CSS3, Vanilla JavaScript, Font Awesome |
| Database | PostgreSQL 14+ (tested on PostgreSQL 18) |

## Project Structure

```
ClintonFinals/
├── Projectbackend/
│   ├── app.py              # Flask API routes
│   ├── models.py           # User, CryptoWallet, Transaction, Earn, P2P
│   ├── bybit_service.py    # Bybit V5 API integration
│   ├── config.py           # DB connection pooling
│   ├── requirements.txt
│   └── .env                # Environment variables (create from .env.example)
├── Projectfrontend/
│   ├── html/
│   │   ├── login.html, register.html
│   │   ├── dashboard.html
│   │   ├── deposit-crypto.html, deposit-network.html
│   │   ├── deposit-ngn.html, deposit-bybit-user.html
│   │   ├── receive.html, withdraw.html, transfer.html
│   │   ├── portfolio.html, p2p.html, transactions.html
│   ├── css/
│   └── js/
└── Projectdb/
    ├── schema_postgres.sql         # Step 1: core tables
    ├── schema_crypto.sql           # Step 2: crypto & earn & P2P
    ├── schema_deposit_features.sql # Step 3: deposit flows
    ├── schema_multi_wallets.sql    # Step 4: multi-coin wallets
    ├── schema_all.sql              # Runs all 4 in order
    └── setup_database.ps1          # Windows one-click setup
```

## Setup Instructions

### Prerequisites
- Python 3.8+
- PostgreSQL 14+ (pgAdmin or psql)
- Web browser

### Step 1: Database Setup

1. Create the database (once):
   ```sql
   CREATE DATABASE cryptovault_db;
   ```

2. Run all schemas — **choose one method:**

   **Option A — PowerShell script (recommended on Windows):**
   ```powershell
   cd C:\Users\ronni\Desktop\ClintonFinals\Projectdb
   .\setup_database.ps1
   ```

   **Option B — Run each file in order:**
   ```powershell
   cd C:\Users\ronni\Desktop\ClintonFinals\Projectdb
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_postgres.sql
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_crypto.sql
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_deposit_features.sql
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_multi_wallets.sql
   ```

   **Option C — Single master file (from `Projectdb` folder):**
   ```powershell
   & "C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -d cryptovault_db -f schema_all.sql
   ```

### Step 2: Backend Setup

```powershell
cd Projectbackend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Create `.env`:
```env
DB_ENGINE=postgres
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=your_password_here
DB_NAME=cryptovault_db
SECRET_KEY=your_secret_key_here
BYBIT_API_KEY=your_bybit_api_key
BYBIT_API_SECRET=your_bybit_api_secret
BYBIT_TESTNET=true
```

Start the server:
```powershell
python app.py
```
API runs at `http://localhost:5000`

### Step 3: Frontend

```powershell
cd Projectfrontend
python -m http.server 8080
```

Open: `http://localhost:8080/html/login.html`

### Demo Accounts

| Username | Password | Notes |
|----------|------------|-------|
| `demo_user` | `password123` | USDT, BTC, ETH, SOL, BNB, XRP + ₦850,000 |
| `test_user` | `password123` | USDT, BTC, ETH, SOL + ₦320,000 |
| `crypto_trader_ng` | `password123` | Searchable for "Receive from Bybit User" |

## Database Schema Overview

### Core (`schema_postgres.sql`)
- `users` — accounts (`account_balance` = total USD, synced from wallets)
- `transactions` — all money movements
- `user_sessions` — session tokens

### Crypto (`schema_crypto.sql`)
- `crypto_wallets` — per-coin balances (source of truth)
- `bybit_api_keys` — user API key storage
- `earn_positions` — Bybit Earn / savings
- `p2p_ads`, `p2p_orders` — P2P marketplace
- `watchlist`, `price_alerts`

### Deposit Features (`schema_deposit_features.sql`)
- `crypto_deposit_requests` — on-chain deposit tracking
- `fiat_purchase_requests` — Buy with NGN card flow
- `bybit_internal_transfers` — receive from another user

### Multi-Wallet (`schema_multi_wallets.sql`)
- `supported_assets` — coin metadata and USD price estimates
- `fiat_wallets` — NGN/USD balances for P2P
- `wallet_ledger` — per-coin audit log
- `user_portfolio` / `user_portfolio_summary` — views

## API Endpoints

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/register` | Register (auto-creates coin wallets) |
| POST | `/api/auth/login` | Login |
| POST | `/api/auth/logout` | Logout |
| GET | `/api/auth/me` | Current user |

### Account & Wallets
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/account/balance` | Portfolio total + all coin wallets |
| GET | `/api/account/balance?coin=BTC` | Single coin balance |
| GET | `/api/wallet/balances` | Detailed wallet list |
| GET | `/api/wallet/coin-info` | Networks per coin |
| GET | `/api/wallet/deposit-address` | Deposit address + QR data |
| POST | `/api/wallet/withdraw` | Withdraw (demo fallback) |

### Deposit Flows
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/deposit/crypto/init` | Start on-chain deposit |
| POST | `/api/deposit/crypto/:id/confirm` | Confirm deposit sent |
| POST | `/api/deposit/fiat/init` | Start NGN card purchase |
| POST | `/api/deposit/fiat/:id/complete` | Complete card purchase |
| GET | `/api/deposit/bybit-user/search` | Search users |
| POST | `/api/deposit/bybit-user/init` | Request from user |
| POST | `/api/deposit/bybit-user/:id/approve` | Approve transfer |
| POST | `/api/deposit/p2p/order` | Create P2P buy order |
| POST | `/api/deposit/p2p/order/:id/mark-paid` | Mark fiat paid |
| POST | `/api/deposit/p2p/order/:id/release` | Release crypto |

### Transfers & Transactions
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/transfer/send` | Send crypto to user (per coin) |
| GET | `/api/transfer/lookup` | Find recipient |
| GET | `/api/transactions` | Transaction history |

### Market & Earn
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/market/prices` | Popular coin prices |
| GET | `/api/market/tickers` | Bybit tickers |
| GET | `/api/earn/products` | Earn products |
| POST | `/api/earn/subscribe` | Subscribe (per-coin debit) |
| POST | `/api/earn/redeem/:id` | Redeem position |
| GET | `/api/earn/positions` | Active positions |

### P2P
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/p2p/ads` | Marketplace ads |
| GET | `/api/p2p/orders` | User orders |

## Supported Coins & Networks

| Coin | Networks |
|------|----------|
| USDT | TRC20, ERC20, BEP20, SOL |
| BTC | Bitcoin, Lightning |
| ETH | ERC20, Arbitrum, Optimism |
| SOL | Solana |
| BNB | BEP20, BEP2 |
| XRP | XRP Ledger |
| ADA | Cardano |
| DOGE | Dogecoin |
| AVAX | C-Chain |
| USDC | ERC20 |

## Demo Mode

When the Bybit testnet API is unreachable (timeout, no network), the app automatically falls back to:
- Static market prices
- Demo deposit addresses and networks
- Local withdraw/earn/P2P processing against PostgreSQL wallets

No real funds are moved. This is intentional for development and demos.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Empty market prices | Restart backend; demo prices load after Bybit timeout (~4s) |
| Deposit/withdraw errors | Run all 4 schema files (especially `schema_multi_wallets.sql`) |
| `API.initCryptoDeposit is not a function` | Hard refresh browser (`Ctrl+Shift+R`) |
| Database connection failed | Check `.env` credentials; ensure PostgreSQL is running |
| CORS errors | Ensure Flask is on port 5000; check `config.js` API URL |

## Development Notes

1. Backend route → `Projectbackend/app.py`
2. Model logic → `Projectbackend/models.py`
3. API client → `Projectfrontend/js/api.js`
4. New schema → add file in `Projectdb/`, update `setup_database.ps1` and this README

## License

Educational / demo use only. Not intended for production with real funds.

---

**Note:** Use Bybit testnet keys during development. Never commit `.env` or real API secrets to version control.
#   F i n a l s P r o j e c t  
 