"""
CryptoVault - Flask Backend Application
Third-party crypto banking app powered by Bybit
"""

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from functools import wraps
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

from models import (
    User, Transaction, EarnPosition, P2POrder, CryptoWallet, BybitApiKey, Watchlist,
    CryptoDepositRequest, FiatPurchaseRequest, BybitInternalTransfer
)
import hashlib
from config import db_config
from bybit_service import BybitService, BybitServiceFactory

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

CORS(app,
     supports_credentials=False,
     origins="*",
     allow_headers=["Content-Type", "Authorization", "X-Session-Token"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     max_age=3600,
     expose_headers=["Content-Type", "X-Session-Token"])

app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)

# ── Rate Limiting Configuration ───────────────────────────────
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
    strategy="fixed-window",
    headers_enabled=True
)


# ── Auth Decorator ────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            user_id = User.verify_token(token)
            if user_id:
                request.user_id = user_id
                return f(*args, **kwargs)
        session_token = request.headers.get('X-Session-Token') or session.get('session_token')
        if session_token:
            user_id = User.validate_session(session_token)
            if user_id:
                request.user_id = user_id
                return f(*args, **kwargs)
        return jsonify({'error': 'Authentication required'}), 401
    return decorated_function


def get_bybit_service(user_id=None):
    """Get Bybit service, using user's own API keys if available"""
    if user_id:
        key_data = BybitApiKey.get_active_key(user_id)
        if key_data:
            return BybitServiceFactory.get_for_user(
                key_data['api_key'],
                key_data['api_secret_encrypted'],
                key_data.get('is_testnet', True)
            )
    return BybitServiceFactory.get_default()


# ── Error Handlers ────────────────────────────────────────────
@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ── Health ────────────────────────────────────────────────────
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'CryptoVault API',
        'version': '2.1.0',
        'deposit_routes': [
            'POST /api/deposit/crypto/init',
            'POST /api/deposit/crypto/<id>/confirm',
            'POST /api/deposit/fiat/init',
            'POST /api/deposit/fiat/<id>/complete',
            'GET  /api/deposit/bybit-user/search',
            'POST /api/deposit/bybit-user/init',
            'POST /api/deposit/bybit-user/<id>/approve',
            'POST /api/deposit/p2p/order',
            'POST /api/deposit/p2p/order/<id>/mark-paid',
            'POST /api/deposit/p2p/order/<id>/release',
        ],
    })


# ══════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════
@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per hour")  # Strict limit for registration to prevent abuse
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    # Trim accidental leading/trailing whitespace from passwords to avoid
    # login/register confusion when users copy/paste with spaces.
    password = data.get('password', '')
    if isinstance(password, str):
        password = password.strip()
    if not username or len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email is required'}), 400
    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    result = User.create_user(username, email, password)
    if result['success']:
        return jsonify({'message': 'Registration successful', 'user_id': result['user_id']}), 201
    return jsonify({'error': result['error']}), 400


@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
@limiter.limit("10 per minute")  # Prevent brute force attacks
def login():
    if request.method == 'OPTIONS':
        return '', 200
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    username_or_email = data.get('username', '').strip()
    password = data.get('password', '')
    if isinstance(password, str):
        password = password.strip()
    print(f"[DEBUG] Login attempt - username: '{username_or_email}', password length: {len(password)}")
    if not username_or_email or not password:
        return jsonify({'error': 'Username/email and password are required'}), 400
    user = User.authenticate(username_or_email, password)
    print(f"[DEBUG] Authentication result: {user}")
    if user:
        jwt_token = User.generate_token(user.id)
        session_token = User.create_session(user.id, request.remote_addr, request.user_agent.string)
        session['session_token'] = session_token
        session['user_id'] = user.id
        session.permanent = True
        return jsonify({
            'message': 'Login successful',
            'token': jwt_token,
            'session_token': session_token,
            'user': user.to_dict()
        })
    print("[DEBUG] Login failed - invalid credentials")
    return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    session_token = request.headers.get('X-Session-Token') or session.get('session_token')
    if session_token:
        User.invalidate_session(session_token)
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    user = User.find_by_id(request.user_id)
    if user:
        locked_funds = user.get_locked_funds()
        return jsonify({
            'user': user.to_dict(),
            'locked_funds': locked_funds,
            'available_balance': user.account_balance - locked_funds
        })
    return jsonify({'error': 'User not found'}), 404


# ══════════════════════════════════════════════════════════════
# ACCOUNT / WALLET
# ══════════════════════════════════════════════════════════════
@app.route('/api/account/balance', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def get_balance():
    user = User.find_by_id(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    coin = request.args.get('coin')
    if coin:
        bal = CryptoWallet.get_coin_balance(request.user_id, coin.upper())
        return jsonify({
            'coin': coin.upper(),
            'balance': bal,
            'available_balance': bal,
        })
    wallets_raw = CryptoWallet.get_balances(request.user_id)
    wallets = []
    for w in wallets_raw:
        wallets.append({
            'coin': w['coin'],
            'name': w.get('asset_name') or w['coin'],
            'account_type': w['account_type'],
            'wallet_label': w.get('wallet_label', 'Funding'),
            'available': float(w['available_balance']),
            'locked': float(w['locked_balance']),
            'total': float(w['total_balance']),
            'usd_value': float(w['usd_value']),
            'price_usd': float(w.get('usd_price_estimate') or 0),
        })
    total_usd = CryptoWallet.get_total_usd(request.user_id)
    locked = user.get_locked_funds()
    ngn = CryptoWallet.get_fiat_balance(request.user_id, 'NGN')
    return jsonify({
        'account_balance': total_usd,
        'total_usd': total_usd,
        'balance': total_usd,
        'locked_funds': locked,
        'available_balance': total_usd,
        'wallets': wallets,
        'fiat': {'NGN': ngn},
    })


@app.route('/api/account/deposit', methods=['POST'])
@login_required
@limiter.limit("10 per hour")  # Limit deposits
def deposit():
    data = request.get_json()
    amount = float(data.get('amount', 0))
    coin = data.get('coin', 'USDT')
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    if amount > 1000000:
        return jsonify({'error': 'Demo deposit limit is 1,000,000'}), 400
    result = Transaction.create_deposit(request.user_id, amount, coin=coin)
    if result['success']:
        user = User.find_by_id(request.user_id)
        return jsonify({
            'message': 'Deposit successful',
            'reference': result['reference'],
            'new_balance': user.get_balance() if user else 0
        })
    return jsonify({'error': result['error']}), 400


def _demo_chain_meta(coin, network):
    """Per-coin demo fees for withdraw/receive UI."""
    fees = {
        'USDT': {'withdrawFee': '1', 'withdrawMin': '10', 'depositMin': '10'},
        'BTC': {'withdrawFee': '0.0005', 'withdrawMin': '0.0001', 'depositMin': '0.0001'},
        'ETH': {'withdrawFee': '0.005', 'withdrawMin': '0.001', 'depositMin': '0.001'},
        'SOL': {'withdrawFee': '0.01', 'withdrawMin': '0.1', 'depositMin': '0.1'},
        'BNB': {'withdrawFee': '0.001', 'withdrawMin': '0.01', 'depositMin': '0.01'},
        'XRP': {'withdrawFee': '0.25', 'withdrawMin': '20', 'depositMin': '20'},
        'ADA': {'withdrawFee': '1', 'withdrawMin': '10', 'depositMin': '10'},
        'DOGE': {'withdrawFee': '5', 'withdrawMin': '50', 'depositMin': '50'},
        'AVAX': {'withdrawFee': '0.01', 'withdrawMin': '0.1', 'depositMin': '0.1'},
    }
    return fees.get(coin.upper(), {'withdrawFee': '0.001', 'withdrawMin': '0.01', 'depositMin': '0.01'})


def _demo_coin_networks(coin=None):
    """Fallback chain list when Bybit API is unavailable."""
    networks = {
        'USDT': ['TRC20', 'ERC20', 'BEP20', 'SOL'],
        'BTC': ['Bitcoin', 'Lightning'],
        'ETH': ['ERC20', 'Arbitrum', 'Optimism'],
        'SOL': ['Solana'],
        'BNB': ['BEP20', 'BEP2'],
        'XRP': ['XRP Ledger'],
        'ADA': ['Cardano'],
        'DOGE': ['Dogecoin'],
        'AVAX': ['C-Chain'],
    }

    def _chains_for(c, nets):
        meta = _demo_chain_meta(c, '')
        return [{
            'chain': n, 'chainType': n, 'confirmation': '12',
            'depositMin': meta['depositMin'], 'withdrawMin': meta['withdrawMin'],
            'withdrawFee': meta['withdrawFee'],
            'chainDeposit': '1', 'chainWithdraw': '1',
        } for n in nets]

    if coin:
        coin = coin.upper()
        chains = networks.get(coin, [coin])
        return [{'coin': coin, 'name': coin, 'chains': _chains_for(coin, chains)}]
    return [{'coin': c, 'name': c, 'chains': _chains_for(c, nets)} for c, nets in networks.items()]


def _get_demo_market_prices():
    """Static market data when Bybit API is unreachable."""
    demo = [
        ('BTCUSDT', '68200.50', '0.0125'),
        ('ETHUSDT', '3600.25', '0.0082'),
        ('SOLUSDT', '145.80', '0.0310'),
        ('BNBUSDT', '585.40', '-0.0045'),
        ('XRPUSDT', '0.52', '0.0155'),
        ('ADAUSDT', '0.45', '-0.0021'),
        ('DOGEUSDT', '0.12', '0.0420'),
        ('AVAXUSDT', '28.75', '0.0188'),
    ]
    return [{
        'symbol': sym,
        'lastPrice': price,
        'price24hPcnt': pct,
        'highPrice24h': price,
        'lowPrice24h': price,
        'volume24h': '1000000',
        'turnover24h': '1000000',
    } for sym, price, pct in demo]


def _bybit_failed(resp):
    """True when Bybit returned an error or timed out."""
    if not resp:
        return True
    code = resp.get('retCode', -1)
    if code != 0:
        return True
    return False


def _demo_deposit_address(user_id, coin, network):
    """Generate a deterministic demo wallet address for testing without Bybit API."""
    seed = f"{user_id}-{coin}-{network}"
    digest = hashlib.sha256(seed.encode()).hexdigest()
    if coin == 'BTC':
        return f"bc1q{digest[:38]}"
    if coin in ('XRP', 'ADA'):
        return digest[:34].upper()
    if coin == 'SOL':
        chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
        return ''.join(chars[int(digest[i:i+2], 16) % len(chars)] for i in range(0, 88, 2))
    return f"0x{digest[:40]}"


# ══════════════════════════════════════════════════════════════
# DEPOSIT FLOWS (Demo)
# ══════════════════════════════════════════════════════════════
@app.route('/api/deposit/crypto/init', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def init_crypto_deposit():
    """Start on-chain deposit: reserve address and create pending request."""
    data = request.get_json() or {}
    coin = data.get('coin', 'USDT').upper()
    network = data.get('network', '')
    amount = data.get('amount')
    if not network:
        return jsonify({'error': 'Network is required'}), 400

    address = None
    tag_memo = None
    from_bybit = False
    bybit = get_bybit_service(request.user_id)
    try:
        resp = bybit.get_deposit_address(coin, chain_type=network)
        if resp.get('retCode') == 0:
            chains = resp.get('result', {}).get('chains', [])
            target = next((c for c in chains if c.get('chainType') == network or c.get('chain') == network), None)
            if not target and chains:
                target = chains[0]
            if target and target.get('addressDeposit'):
                address = target.get('addressDeposit')
                tag_memo = target.get('tagDeposit')
                from_bybit = True
    except Exception:
        pass

    if not address:
        address = _demo_deposit_address(request.user_id, coin, network)

    try:
        req = CryptoDepositRequest.create(
            request.user_id, coin, network, address,
            amount=float(amount) if amount else None,
            tag_memo=tag_memo
        )
    except Exception as e:
        err = str(e).lower()
        if 'crypto_deposit_requests' in err or 'does not exist' in err:
            return jsonify({
                'error': 'Database not migrated. Run Projectdb/schema_deposit_features.sql in PostgreSQL.'
            }), 500
        return jsonify({'error': str(e)}), 500

    return jsonify({
        'request_id': req['id'],
        'reference': req['reference_number'],
        'coin': coin,
        'network': network,
        'address': address,
        'tag_memo': tag_memo,
        'demo': not from_bybit,
        'status': req['status'],
    }), 201


@app.route('/api/deposit/crypto/<int:request_id>/confirm', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def confirm_crypto_deposit(request_id):
    """Demo: user confirms they sent crypto on-chain."""
    data = request.get_json() or {}
    amount = float(data.get('amount', 0))
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    if amount > 1000000:
        return jsonify({'error': 'Demo deposit limit is 1,000,000'}), 400
    result = CryptoDepositRequest.confirm(request_id, request.user_id, amount)
    if result['success']:
        user = User.find_by_id(request.user_id)
        return jsonify({
            'message': 'Deposit confirmed and credited',
            'reference': result['reference'],
            'coin': result['coin'],
            'amount': result['amount'],
            'new_balance': user.get_balance() if user else 0,
        })
    return jsonify({'error': result['error']}), 400


@app.route('/api/deposit/fiat/init', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def init_fiat_purchase():
    """Start Buy with NGN (card) demo purchase."""
    data = request.get_json() or {}
    coin = data.get('coin', 'USDT').upper()
    fiat_currency = data.get('fiat_currency', 'NGN').upper()
    fiat_amount = float(data.get('fiat_amount', 0))
    card_number = data.get('card_number', '').replace(' ', '')

    if fiat_amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    if len(card_number) < 4:
        return jsonify({'error': 'Valid card number required'}), 400

    rates = {'USDT': {'NGN': 1620.0, 'USD': 1.0}, 'BTC': {'NGN': 110500000.0, 'USD': 68200.0},
             'ETH': {'NGN': 5830000.0, 'USD': 3600.0}}
    rate = rates.get(coin, rates['USDT']).get(fiat_currency, 1620.0)
    crypto_amount = round(fiat_amount / rate, 8) if rate else fiat_amount
    card_last_four = card_number[-4:]

    req = FiatPurchaseRequest.create(
        request.user_id, coin, fiat_currency, fiat_amount, crypto_amount, rate, card_last_four
    )
    return jsonify({
        'request_id': req['id'],
        'reference': req['reference_number'],
        'coin': coin,
        'fiat_currency': fiat_currency,
        'fiat_amount': fiat_amount,
        'crypto_amount': crypto_amount,
        'exchange_rate': rate,
        'status': req['status'],
    }), 201


@app.route('/api/deposit/fiat/<int:request_id>/complete', methods=['POST'])
@login_required
@limiter.limit("10 per hour")
def complete_fiat_purchase(request_id):
    """Demo: simulate successful card payment."""
    result = FiatPurchaseRequest.complete(request_id, request.user_id)
    if result['success']:
        user = User.find_by_id(request.user_id)
        return jsonify({
            'message': 'Payment successful — crypto credited',
            'reference': result['reference'],
            'coin': result['coin'],
            'amount': result['amount'],
            'new_balance': user.get_balance() if user else 0,
        })
    return jsonify({'error': result['error']}), 400


@app.route('/api/deposit/bybit-user/search', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def search_bybit_users():
    """Search platform users to receive crypto from."""
    query = request.args.get('q', '').strip()
    if len(query) < 2:
        return jsonify({'users': []})
    users = BybitInternalTransfer.search_users(query, request.user_id)
    formatted = []
    for u in users:
        email = u.get('email', '')
        masked = email[:3] + '***' + email[email.index('@'):] if '@' in email else '***'
        formatted.append({
            'id': u['id'],
            'username': u['username'],
            'display_name': u.get('display_name') or u['username'],
            'bybit_uid': u.get('bybit_uid'),
            'email_masked': masked,
        })
    return jsonify({'users': formatted})


@app.route('/api/deposit/bybit-user/init', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def init_bybit_user_transfer():
    """Request crypto from another user."""
    data = request.get_json() or {}
    sender_username = data.get('sender_username', '').strip()
    amount = float(data.get('amount', 0))
    coin = data.get('coin', 'USDT').upper()
    if not sender_username:
        return jsonify({'error': 'Sender username is required'}), 400
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    sender = User.find_by_username(sender_username)
    if not sender:
        return jsonify({'error': 'User not found'}), 404
    if sender.id == request.user_id:
        return jsonify({'error': 'Cannot request from yourself'}), 400
    transfer = BybitInternalTransfer.create(request.user_id, sender.id, amount, coin)
    sender_name = getattr(sender, 'display_name', None) or sender.username
    return jsonify({
        'transfer_id': transfer['id'],
        'reference': transfer['reference_number'],
        'sender_username': sender.username,
        'sender_name': sender_name,
        'amount': amount,
        'coin': coin,
        'status': transfer['status'],
    }), 201


@app.route('/api/deposit/bybit-user/<int:transfer_id>/approve', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def approve_bybit_user_transfer(transfer_id):
    """Demo: simulate sender approving and releasing funds."""
    result = BybitInternalTransfer.approve(transfer_id, request.user_id)
    if result['success']:
        user = User.find_by_id(request.user_id)
        return jsonify({
            'message': f'{result["sender_name"]} has sent your crypto',
            'reference': result['reference'],
            'sender_name': result['sender_name'],
            'amount': result['amount'],
            'coin': result['coin'],
            'new_balance': user.get_balance() if user else 0,
        })
    return jsonify({'error': result['error']}), 400


@app.route('/api/deposit/p2p/order', methods=['POST'])
@login_required
@limiter.limit("20 per hour")
def create_p2p_deposit_order():
    """Create a local P2P buy order for deposit flow."""
    data = request.get_json() or {}
    token = data.get('token', 'USDT')
    currency = data.get('currency', 'NGN')
    amount = float(data.get('amount', 0))
    price = float(data.get('price', 0))
    vendor_nickname = data.get('vendor_nickname', 'P2P Vendor')
    if amount <= 0 or price <= 0:
        return jsonify({'error': 'Amount and price must be positive'}), 400
    total_price = round(amount * price, 2)
    try:
        order = P2POrder.create_order(
            request.user_id, None, token, currency, 0, amount, price, total_price,
            counterparty_name=vendor_nickname, vendor_nickname=vendor_nickname
        )
    except Exception as e:
        err = str(e).lower()
        if 'payment_status' in err or 'does not exist' in err or 'vendor_nickname' in err:
            return jsonify({
                'error': 'Database not migrated. Run Projectdb/schema_deposit_features.sql in PostgreSQL.'
            }), 500
        return jsonify({'error': str(e)}), 500
    return jsonify({
        'order_id': order['id'],
        'reference': order.get('reference_number'),
        'token': token,
        'currency': currency,
        'amount': amount,
        'price': price,
        'total_price': total_price,
        'vendor_nickname': vendor_nickname,
        'status': order['status'],
        'payment_status': order['payment_status'],
    }), 201


@app.route('/api/deposit/p2p/order/<int:order_id>/mark-paid', methods=['POST'])
@login_required
def mark_p2p_order_paid(order_id):
    """User confirms they transferred fiat to P2P seller."""
    order = P2POrder.mark_paid(order_id, request.user_id)
    if not order:
        return jsonify({'error': 'Order not found or already paid'}), 400
    return jsonify({
        'message': 'Payment marked as transferred',
        'order_id': order['id'],
        'status': order['status'],
        'payment_status': order['payment_status'],
    })


@app.route('/api/deposit/p2p/order/<int:order_id>/release', methods=['POST'])
@login_required
def release_p2p_deposit(order_id):
    """Demo: vendor releases crypto to buyer."""
    result = P2POrder.complete_deposit(order_id, request.user_id)
    if result['success']:
        user = User.find_by_id(request.user_id)
        return jsonify({
            'message': 'Crypto released to your account',
            'reference': result['reference'],
            'amount': result['amount'],
            'coin': result['coin'],
            'new_balance': user.get_balance() if user else 0,
        })
    return jsonify({'error': result['error']}), 400


@app.route('/api/wallet/balances', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def get_wallet_balances():
    """Get cached crypto wallet balances"""
    balances = CryptoWallet.get_balances(request.user_id)
    total_usd = CryptoWallet.get_total_usd(request.user_id)
    ngn = CryptoWallet.get_fiat_balance(request.user_id, 'NGN')
    formatted = []
    for b in balances:
        formatted.append({
            'coin': b['coin'],
            'name': b.get('asset_name') or b['coin'],
            'account_type': b['account_type'],
            'wallet_label': b.get('wallet_label', 'Funding'),
            'available': float(b['available_balance']),
            'locked': float(b['locked_balance']),
            'total': float(b['total_balance']),
            'usd_value': float(b['usd_value']),
            'price_usd': float(b.get('usd_price_estimate') or 0),
            'last_synced': b['last_synced'].isoformat() if b.get('last_synced') else None,
        })
    return jsonify({
        'balances': formatted,
        'total_usd': total_usd,
        'fiat': {'NGN': ngn},
        'coin_count': len(formatted),
    })


@app.route('/api/wallet/sync', methods=['POST'])
@login_required
@limiter.limit("5 per minute")  # Limit API calls to Bybit
def sync_wallet():
    """Sync wallet from Bybit API"""
    bybit = get_bybit_service(request.user_id)
    try:
        resp = bybit.get_all_coins_balance(account_type='FUND')
        if resp.get('retCode') == 0:
            result = resp.get('result', {})
            balances = []
            for coin_data in result.get('balance', []):
                balances.append({
                    'coin': coin_data.get('coin', ''),
                    'account_type': 'FUND',
                    'available': coin_data.get('transferBalance', 0),
                    'locked': coin_data.get('locked', 0),
                    'total': coin_data.get('walletBalance', 0),
                    'usd_value': float(coin_data.get('walletBalance', 0)),
                })
            CryptoWallet.sync_balances(request.user_id, balances)
            return jsonify({'message': 'Wallet synced', 'count': len(balances)})
        return jsonify({'error': resp.get('retMsg', 'Sync failed')}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ══════════════════════════════════════════════════════════════
# DEPOSIT ADDRESSES & WITHDRAWAL
# ══════════════════════════════════════════════════════════════
@app.route('/api/wallet/deposit-address', methods=['GET'])
@login_required
def get_deposit_address():
    """Get deposit address for a coin, optionally for a specific chain/network"""
    coin = request.args.get('coin', 'USDT').upper()
    chain = request.args.get('chain') or coin
    bybit = get_bybit_service(request.user_id)
    try:
        resp = bybit.get_deposit_address(coin, chain_type=chain)
        if resp.get('retCode') == 0:
            result = resp.get('result', {})
            chains = result.get('chains', [])
            formatted_chains = []
            for c in chains:
                if c.get('addressDeposit'):
                    formatted_chains.append({
                        'chain': c.get('chain', ''),
                        'chainType': c.get('chainType', ''),
                        'addressDeposit': c.get('addressDeposit', ''),
                        'tagDeposit': c.get('tagDeposit', ''),
                        'chainDeposit': c.get('chainDeposit', ''),
                        'minAmount': c.get('chainDepositMin', '0'),
                        'confirmation': c.get('confirmation', '0'),
                    })
            if formatted_chains:
                return jsonify({
                    'coin': result.get('coin', coin),
                    'chains': formatted_chains,
                    'demo': False,
                })
    except Exception:
        pass

    # Demo fallback — works without Bybit API
    network = chain or coin
    address = _demo_deposit_address(request.user_id, coin, network)
    return jsonify({
        'coin': coin,
        'chains': [{
            'chain': network,
            'chainType': network,
            'addressDeposit': address,
            'tagDeposit': '',
            'chainDeposit': '1',
            'minAmount': _demo_chain_meta(coin, network)['depositMin'],
            'confirmation': '12',
        }],
        'demo': True,
    })


@app.route('/api/wallet/coin-info', methods=['GET'])
@login_required
def get_coin_info():
    """Get coin information including available networks"""
    coin = request.args.get('coin')
    bybit = get_bybit_service(request.user_id)
    try:
        resp = bybit.get_coin_info(coin=coin)
        if resp.get('retCode') == 0:
            rows = resp.get('result', {}).get('rows', [])
            if rows:
                result = []
                for row in rows:
                    chains = []
                    for c in row.get('chains', []):
                        chains.append({
                            'chain': c.get('chain', ''),
                            'chainType': c.get('chainType', ''),
                            'confirmation': c.get('confirmation', ''),
                            'withdrawFee': c.get('withdrawFee', '0'),
                            'depositMin': c.get('depositMin', '0'),
                            'withdrawMin': c.get('withdrawMin', '0'),
                            'chainDeposit': c.get('chainDeposit', '1'),
                            'chainWithdraw': c.get('chainWithdraw', '1'),
                        })
                    result.append({
                        'coin': row.get('coin', ''),
                        'name': row.get('name', ''),
                        'chains': chains,
                    })
                return jsonify({'coins': result})
    except Exception:
        pass
    # Bybit unavailable — return demo networks so deposit flow still works
    return jsonify({'coins': _demo_coin_networks(coin), 'demo': True})


@app.route('/api/wallet/withdraw', methods=['POST'])
@login_required
def withdraw():
    """Submit a withdrawal — uses Bybit when available, otherwise demo mode."""
    data = request.get_json()
    coin = data.get('coin', 'USDT')
    chain = data.get('chain', '')
    address = data.get('address', '').strip()
    tag = data.get('tag', '').strip()
    amount = float(data.get('amount', 0))

    if not address:
        return jsonify({'error': 'Withdrawal address is required'}), 400
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400

    user = User.find_by_id(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.get_balance(coin) < amount:
        return jsonify({'error': f'Insufficient {coin} balance'}), 400

    bybit = get_bybit_service(request.user_id)
    resp = None
    try:
        resp = bybit.create_withdrawal(coin=coin, chain=chain, address=address, tag=tag, amount=str(amount))
        if resp.get('retCode') == 0:
            withdraw_id = resp.get('result', {}).get('id', '')
            result = Transaction.create_deposit(
                request.user_id, -amount,
                description=f'Withdrawal to {address[:8]}...{address[-6:]}',
                coin=coin, tx_hash=withdraw_id
            )
            if result['success']:
                return jsonify({'message': 'Withdrawal submitted successfully', 'id': withdraw_id, 'demo': False})
            return jsonify({'error': result['error']}), 400
    except Exception:
        pass

    # Demo fallback when Bybit is unavailable
    ref = Transaction.generate_reference()
    result = Transaction.create_deposit(
        request.user_id, -amount,
        description=f'Withdrawal to {address[:8]}...{address[-6:]}',
        coin=coin, tx_hash=f'DEMO-WD-{ref}'
    )
    if result['success']:
        return jsonify({
            'message': 'Withdrawal submitted (demo mode)',
            'id': f'DEMO-WD-{ref}',
            'reference': result['reference'],
            'demo': True,
        })
    return jsonify({'error': result.get('error', 'Withdrawal failed')}), 400


# ══════════════════════════════════════════════════════════════
# TRANSFER
# ══════════════════════════════════════════════════════════════
@app.route('/api/transfer/send', methods=['POST'])
@login_required
@limiter.limit("20 per hour")  # Limit transfers to prevent abuse
def send_money():
    data = request.get_json()
    receiver_username = data.get('receiver_username', '').strip()
    amount = float(data.get('amount', 0))
    description = data.get('description', 'Crypto Transfer')
    coin = data.get('coin', 'USDT')
    if not receiver_username:
        return jsonify({'error': 'Receiver username is required'}), 400
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    receiver = User.find_by_username(receiver_username)
    if not receiver:
        return jsonify({'error': 'Receiver not found'}), 404
    if receiver.id == request.user_id:
        return jsonify({'error': 'Cannot transfer to yourself'}), 400
    result = Transaction.create_transfer(request.user_id, receiver.id, amount, description, coin)
    if result['success']:
        sender = User.find_by_id(request.user_id)
        return jsonify({
            'message': 'Transfer successful',
            'reference': result['reference'],
            'new_balance': sender.get_balance() if sender else 0
        })
    return jsonify({'error': result['error']}), 400


@app.route('/api/transfer/lookup', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def lookup_user():
    username = request.args.get('username', '').strip()
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    user = User.find_by_username(username)
    if user and user.id != request.user_id:
        return jsonify({
            'found': True,
            'username': user.username,
            'email': user.email[:3] + '***' + user.email[user.email.index('@'):]
        })
    return jsonify({'found': False})


# ══════════════════════════════════════════════════════════════
# TRANSACTIONS
# ══════════════════════════════════════════════════════════════
@app.route('/api/transactions', methods=['GET'])
@login_required
@limiter.limit("60 per minute")
def get_transactions():
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    transactions = Transaction.get_user_transactions(request.user_id, limit, offset)
    formatted = []
    for t in transactions:
        formatted.append({
            'id': t['id'],
            'amount': float(t['amount']),
            'coin': t.get('coin', 'USDT'),
            'type': t['transaction_type'],
            'description': t['description'],
            'reference': t['reference_number'],
            'status': t['status'],
            'tx_hash': t.get('tx_hash'),
            'timestamp': t['timestamp'].isoformat() if t['timestamp'] else None,
            'sender': t['sender_username'],
            'receiver': t['receiver_username'],
            'is_credit': t['receiver_id'] == request.user_id
        })
    return jsonify({'transactions': formatted})


# ══════════════════════════════════════════════════════════════
# MARKET DATA
# ══════════════════════════════════════════════════════════════
@app.route('/api/market/tickers', methods=['GET'])
@limiter.limit("60 per minute")  # Public endpoint but rate limited
def get_market_tickers():
    """Get market tickers (public endpoint)"""
    category = request.args.get('category', 'spot')
    symbol = request.args.get('symbol')
    bybit = BybitServiceFactory.get_default()
    resp = bybit.get_tickers(category=category, symbol=symbol)
    if resp.get('retCode') == 0:
        tickers = resp.get('result', {}).get('list', [])
        return jsonify({'tickers': tickers})
    return jsonify({'tickers': [], 'error': resp.get('retMsg', '')})


@app.route('/api/market/kline', methods=['GET'])
@limiter.limit("60 per minute")
def get_market_kline():
    """Get kline data (public endpoint)"""
    symbol = request.args.get('symbol', 'BTCUSDT')
    interval = request.args.get('interval', '60')
    limit = request.args.get('limit', 100)
    bybit = BybitServiceFactory.get_default()
    resp = bybit.get_kline(symbol=symbol, interval=interval, limit=limit)
    if resp.get('retCode') == 0:
        return jsonify({'kline': resp.get('result', {})})
    return jsonify({'kline': {}, 'error': resp.get('retMsg', '')})


@app.route('/api/market/search', methods=['GET'])
@limiter.limit("30 per minute")
def search_market():
    """Search for any trading pair/asset on Bybit"""
    query = request.args.get('q', '').strip().upper()
    category = request.args.get('category', 'spot')
    if not query or len(query) < 1:
        return jsonify({'results': []})
    bybit = BybitServiceFactory.get_default()
    resp = bybit.get_tickers(category=category)
    results = []
    if resp.get('retCode') == 0:
        all_tickers = resp.get('result', {}).get('list', [])
        for t in all_tickers:
            symbol = t.get('symbol', '')
            # Match query against symbol (e.g. "DOGE" matches "DOGEUSDT")
            if query in symbol:
                results.append({
                    'symbol': symbol,
                    'lastPrice': t.get('lastPrice', '0'),
                    'price24hPcnt': t.get('price24hPcnt', '0'),
                    'highPrice24h': t.get('highPrice24h', '0'),
                    'lowPrice24h': t.get('lowPrice24h', '0'),
                    'volume24h': t.get('volume24h', '0'),
                    'turnover24h': t.get('turnover24h', '0'),
                })
        # Sort: exact prefix matches first, then by volume
        results.sort(key=lambda x: (0 if x['symbol'].startswith(query) else 1, -float(x.get('turnover24h', 0))))
    return jsonify({'results': results[:50]})


@app.route('/api/market/prices', methods=['GET'])
@limiter.limit("60 per minute")
def get_market_prices():
    """Get simplified price list for popular coins"""
    symbols = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'DOGEUSDT', 'AVAXUSDT']
    prices = []
    try:
        bybit = BybitServiceFactory.get_default()
        resp = bybit.get_tickers(category='spot')
        if resp.get('retCode') == 0:
            all_tickers = resp.get('result', {}).get('list', [])
            ticker_map = {t['symbol']: t for t in all_tickers}
            for sym in symbols:
                t = ticker_map.get(sym)
                if t:
                    prices.append({
                        'symbol': t['symbol'],
                        'lastPrice': t.get('lastPrice', '0'),
                        'price24hPcnt': t.get('price24hPcnt', '0'),
                        'highPrice24h': t.get('highPrice24h', '0'),
                        'lowPrice24h': t.get('lowPrice24h', '0'),
                        'volume24h': t.get('volume24h', '0'),
                        'turnover24h': t.get('turnover24h', '0'),
                    })
    except Exception:
        pass
    if not prices:
        prices = _get_demo_market_prices()
        return jsonify({'prices': prices, 'demo': True})
    return jsonify({'prices': prices, 'demo': False})


# ══════════════════════════════════════════════════════════════
# BYBIT EARN (SAVINGS)
# ══════════════════════════════════════════════════════════════
def _get_demo_earn_products(coin=None):
    """Return demo earn products when Bybit API is unavailable"""
    demo = [
        {'productId': 'demo-usdt-flex', 'coin': 'USDT', 'productType': 'Flexible', 'estimateApy': '0.0350',
         'minPurchaseAmount': '1', 'status': 'Available'},
        {'productId': 'demo-btc-flex', 'coin': 'BTC', 'productType': 'Flexible', 'estimateApy': '0.0120',
         'minPurchaseAmount': '0.0001', 'status': 'Available'},
        {'productId': 'demo-eth-flex', 'coin': 'ETH', 'productType': 'Flexible', 'estimateApy': '0.0200',
         'minPurchaseAmount': '0.001', 'status': 'Available'},
        {'productId': 'demo-sol-flex', 'coin': 'SOL', 'productType': 'Flexible', 'estimateApy': '0.0500',
         'minPurchaseAmount': '0.1', 'status': 'Available'},
        {'productId': 'demo-usdt-fixed30', 'coin': 'USDT', 'productType': 'Fixed 30D', 'estimateApy': '0.0650',
         'minPurchaseAmount': '10', 'status': 'Available'},
        {'productId': 'demo-btc-fixed30', 'coin': 'BTC', 'productType': 'Fixed 30D', 'estimateApy': '0.0250',
         'minPurchaseAmount': '0.001', 'status': 'Available'},
    ]
    if coin:
        return [p for p in demo if p['coin'] == coin]
    return demo


@app.route('/api/earn/products', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def get_earn_products():
    """Get available Bybit Earn/Savings products"""
    coin = request.args.get('coin')
    bybit = get_bybit_service(request.user_id)
    try:
        resp = bybit.get_earn_products(coin=coin)
        if resp.get('retCode') == 0:
            products = resp.get('result', {}).get('list', [])
            if products:
                return jsonify({'products': products})
        return jsonify({'products': _get_demo_earn_products(coin), 'demo': True,
                        'message': resp.get('retMsg', 'Could not fetch from Bybit. Showing demo products.')})
    except Exception as e:
        return jsonify({'products': _get_demo_earn_products(coin), 'demo': True,
                        'message': 'API unavailable. Showing demo products.'})


@app.route('/api/earn/subscribe', methods=['POST'])
@login_required
@limiter.limit("10 per hour")  # Limit earn subscriptions
def subscribe_earn():
    """Subscribe to a Bybit Earn product — demo mode when Bybit unavailable."""
    data = request.get_json()
    product_id = data.get('product_id')
    amount = float(data.get('amount', 0))
    coin = data.get('coin', 'USDT')
    product_type = data.get('product_type', 'flexible')
    apy = float(data.get('apy', 0))

    if not product_id or amount <= 0:
        return jsonify({'error': 'Product ID and positive amount required'}), 400

    user = User.find_by_id(request.user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    if user.get_balance(coin) < amount:
        return jsonify({'error': f'Insufficient {coin} balance'}), 400

    is_demo_product = str(product_id).startswith('demo-')

    if not is_demo_product:
        bybit = get_bybit_service(request.user_id)
        try:
            resp = bybit.subscribe_earn(product_id, amount, coin)
            if resp.get('retCode') == 0:
                order_id = resp.get('result', {}).get('orderId')
                debit = CryptoWallet.debit(request.user_id, coin, amount, 'earn_lock', order_id, f'Earn subscribe {product_type}')
                if not debit['success']:
                    return jsonify({'error': debit['error']}), 400
                EarnPosition.create_position(
                    request.user_id, product_id, product_type, coin, amount, apy, order_id
                )
                return jsonify({'message': 'Subscribed successfully', 'order_id': order_id}), 201
        except Exception:
            pass

    # Demo subscription (demo products or Bybit unavailable)
    order_id = f'DEMO-{Transaction.generate_reference()}'
    debit = CryptoWallet.debit(request.user_id, coin, amount, 'earn_lock', order_id, f'Earn subscribe {product_type}')
    if not debit['success']:
        return jsonify({'error': debit['error']}), 400
    pos = EarnPosition.create_position(
        request.user_id, product_id, product_type, coin, amount, apy, order_id
    )
    return jsonify({
        'message': 'Subscribed successfully (demo mode)',
        'order_id': order_id,
        'position_id': pos['id'] if pos else None,
        'demo': True,
    }), 201


@app.route('/api/earn/positions', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def get_earn_positions():
    """Get user's Bybit Earn positions"""
    status = request.args.get('status')
    positions = EarnPosition.get_user_positions(request.user_id, status)
    formatted = []
    for p in positions:
        formatted.append({
            'id': p['id'],
            'product_id': p['product_id'],
            'product_type': p['product_type'],
            'coin': p['coin'],
            'amount': float(p['amount']),
            'apy': float(p['apy']),
            'accrued_interest': float(p['accrued_interest']),
            'status': p['status'],
            'subscribed_at': p['subscribed_at'].isoformat() if p.get('subscribed_at') else None,
            'redeemed_at': p['redeemed_at'].isoformat() if p.get('redeemed_at') else None,
        })
    return jsonify({
        'positions': formatted,
        'total_locked': EarnPosition.get_total_locked(request.user_id),
        'total_interest': EarnPosition.get_total_interest(request.user_id),
    })


@app.route('/api/earn/redeem/<int:position_id>', methods=['POST'])
@login_required
def redeem_earn(position_id):
    """Redeem from an Earn position and return funds to balance."""
    positions = EarnPosition.get_user_positions(request.user_id, 'active')
    pos = next((p for p in positions if p['id'] == position_id), None)
    if not pos:
        return jsonify({'error': 'Position not found'}), 404
    amount = float(pos['amount'])
    coin = pos['coin']
    EarnPosition.redeem_position(position_id, request.user_id)
    CryptoWallet.credit(request.user_id, coin, amount, 'earn_unlock', f'REDEEM-{position_id}', 'Earn position redeemed')
    return jsonify({'message': 'Position redeemed successfully', 'amount': amount, 'coin': coin})


@app.route('/api/earn/sync', methods=['POST'])
@login_required
def sync_earn_positions():
    """Sync earn positions from Bybit"""
    bybit = get_bybit_service(request.user_id)
    resp = bybit.get_earn_positions()
    if resp.get('retCode') == 0:
        return jsonify({'positions': resp.get('result', {})})
    return jsonify({'error': resp.get('retMsg', 'Sync failed')}), 400


# ══════════════════════════════════════════════════════════════
# P2P TRADING
# ══════════════════════════════════════════════════════════════
@app.route('/api/p2p/ads', methods=['GET'])
@login_required
@limiter.limit("30 per minute")
def get_p2p_ads():
    """Get online P2P ads — tries Bybit first, falls back to built-in vendors"""
    token = request.args.get('token', 'USDT')
    currency = request.args.get('currency', 'NGN')
    side = request.args.get('side', '0')
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))

    # Try Bybit live data first
    try:
        bybit = get_bybit_service(request.user_id)
        resp = bybit.get_p2p_online_ads(token, currency, side, page, size)
        if resp.get('retCode') == 0:
            items = resp.get('result', {}).get('items', [])
            if items:
                return jsonify({'ads': items, 'count': len(items)})
    except Exception:
        pass

    # Fallback: return built-in P2P vendor data
    ads = _get_mock_p2p_ads(token, currency, side)
    return jsonify({'ads': ads, 'count': len(ads)})


def _get_mock_p2p_ads(token, currency, side):
    """Generate realistic P2P vendor listings based on filters."""
    import random

    # Base prices per currency pair
    base_prices = {
        'USDT': {'NGN': 1620.00, 'USD': 1.00, 'EUR': 0.92, 'GBP': 0.79},
        'BTC':  {'NGN': 110_500_000, 'USD': 68200, 'EUR': 62_800, 'GBP': 53_900},
        'ETH':  {'NGN': 5_830_000, 'USD': 3600, 'EUR': 3310, 'GBP': 2840},
    }
    base = base_prices.get(token, base_prices['USDT']).get(currency, 1620.00)

    vendors = [
        {
            'nickName': 'CryptoKing_NG',
            'orderCount': 3842,
            'completionRate': '0.987',
            'payments': [{'name': 'Bank Transfer'}, {'name': 'Opay'}],
            'spread': 0.002, 'minMul': 10000, 'maxMul': 500000,
            'online': True,
        },
        {
            'nickName': 'SwiftTrader',
            'orderCount': 1205,
            'completionRate': '0.963',
            'payments': [{'name': 'Bank Transfer'}, {'name': 'Palmpay'}],
            'spread': 0.005, 'minMul': 5000, 'maxMul': 300000,
            'online': True,
        },
        {
            'nickName': 'NaijaCrypto',
            'orderCount': 6710,
            'completionRate': '0.995',
            'payments': [{'name': 'Bank Transfer'}, {'name': 'Opay'}, {'name': 'Kuda'}],
            'spread': -0.001, 'minMul': 20000, 'maxMul': 1000000,
            'online': True,
        },
        {
            'nickName': 'DiamondExchange',
            'orderCount': 892,
            'completionRate': '0.941',
            'payments': [{'name': 'Bank Transfer'}],
            'spread': 0.008, 'minMul': 50000, 'maxMul': 2000000,
            'online': True,
        },
        {
            'nickName': 'FastPay_OTC',
            'orderCount': 2150,
            'completionRate': '0.978',
            'payments': [{'name': 'Bank Transfer'}, {'name': 'Moniepoint'}],
            'spread': 0.003, 'minMul': 10000, 'maxMul': 750000,
            'online': True,
        },
        {
            'nickName': 'TrustVault_P2P',
            'orderCount': 4520,
            'completionRate': '0.992',
            'payments': [{'name': 'Bank Transfer'}, {'name': 'Opay'}, {'name': 'GTBank'}],
            'spread': 0.001, 'minMul': 15000, 'maxMul': 1500000,
            'online': True,
        },
        {
            'nickName': 'BlockMerchant',
            'orderCount': 530,
            'completionRate': '0.955',
            'payments': [{'name': 'Bank Transfer'}, {'name': 'Palmpay'}],
            'spread': 0.010, 'minMul': 5000, 'maxMul': 200000,
            'online': False,
        },
    ]

    is_buy = (side == '0')
    ads = []
    for v in vendors:
        # Sellers price slightly higher, buyers slightly lower
        spread = v['spread']
        if is_buy:
            price = round(base * (1 + spread + random.uniform(0, 0.003)), 2)
        else:
            price = round(base * (1 - spread + random.uniform(-0.003, 0)), 2)

        # Scale min/max amounts relative to currency
        scale = 1.0
        if currency == 'USD': scale = 1 / 1620
        elif currency == 'EUR': scale = 1 / 1760
        elif currency == 'GBP': scale = 1 / 2050

        min_amt = round(v['minMul'] * scale, 2)
        max_amt = round(v['maxMul'] * scale, 2)

        ads.append({
            'nickName':       v['nickName'],
            'price':          str(price),
            'currencyId':     currency,
            'tokenId':        token,
            'minAmount':      str(min_amt),
            'maxAmount':      str(max_amt),
            'orderCount':     v['orderCount'],
            'completionRate': v['completionRate'],
            'payments':       v['payments'],
            'online':         v['online'],
        })

    # Sort: buy side → cheapest first, sell side → highest first
    ads.sort(key=lambda a: float(a['price']), reverse=not is_buy)
    return ads


@app.route('/api/p2p/my-ads', methods=['GET'])
@login_required
def get_my_p2p_ads():
    """Get user's own P2P ads"""
    bybit = get_bybit_service(request.user_id)
    resp = bybit.get_p2p_ads_list()
    if resp.get('retCode') == 0:
        return jsonify({'ads': resp.get('result', {}).get('items', [])})
    return jsonify({'ads': [], 'error': resp.get('retMsg', '')})


@app.route('/api/p2p/create-ad', methods=['POST'])
@login_required
def create_p2p_ad():
    """Create a P2P ad"""
    data = request.get_json()
    bybit = get_bybit_service(request.user_id)
    resp = bybit.create_p2p_ad(
        token_id=data.get('token_id', 'USDT'),
        currency_id=data.get('currency_id', 'NGN'),
        side=data.get('side', 1),
        price=data.get('price'),
        quantity=data.get('quantity'),
        min_amount=data.get('min_amount'),
        max_amount=data.get('max_amount'),
        payment_ids=data.get('payment_ids', []),
        remark=data.get('remark', ''),
    )
    if resp.get('retCode') == 0:
        return jsonify({'message': 'Ad created successfully', 'result': resp.get('result', {})}), 201
    return jsonify({'error': resp.get('retMsg', 'Failed to create ad')}), 400


@app.route('/api/p2p/orders', methods=['GET'])
@login_required
def get_p2p_orders():
    """Get P2P orders"""
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 10))
    bybit = get_bybit_service(request.user_id)
    resp = bybit.get_p2p_orders(page=page, size=size)
    if resp.get('retCode') == 0:
        return jsonify({'orders': resp.get('result', {}).get('items', [])})
    # Fallback to local DB
    local_orders = P2POrder.get_user_orders(request.user_id)
    formatted = []
    for o in local_orders:
        formatted.append({
            'id': o['id'],
            'bybit_order_id': o.get('bybit_order_id'),
            'token_id': o['token_id'],
            'currency_id': o['currency_id'],
            'side': o['side'],
            'amount': float(o['amount']),
            'price': float(o['price']),
            'total_price': float(o['total_price']),
            'status': o['status'],
            'counterparty': o.get('counterparty_name'),
            'created_at': o['created_at'].isoformat() if o.get('created_at') else None,
        })
    return jsonify({'orders': formatted})


@app.route('/api/p2p/pending', methods=['GET'])
@login_required
def get_p2p_pending():
    """Get pending P2P orders"""
    bybit = get_bybit_service(request.user_id)
    resp = bybit.get_p2p_pending_orders()
    if resp.get('retCode') == 0:
        return jsonify({'orders': resp.get('result', {}).get('items', [])})
    return jsonify({'orders': []})


@app.route('/api/p2p/payment-methods', methods=['GET'])
@login_required
def get_p2p_payment_methods():
    """Get user's P2P payment methods"""
    bybit = get_bybit_service(request.user_id)
    resp = bybit.get_p2p_payment_methods()
    if resp.get('retCode') == 0:
        return jsonify({'methods': resp.get('result', {})})
    return jsonify({'methods': []})


# ══════════════════════════════════════════════════════════════
# API KEYS MANAGEMENT
# ══════════════════════════════════════════════════════════════
@app.route('/api/settings/api-keys', methods=['GET'])
@login_required
def get_api_keys():
    keys = BybitApiKey.get_all_keys(request.user_id)
    formatted = []
    for k in keys:
        formatted.append({
            'id': k['id'],
            'api_key': k['api_key'][:8] + '****',
            'label': k['label'],
            'permissions': k['permissions'],
            'is_testnet': k['is_testnet'],
            'is_active': k['is_active'],
            'created_at': k['created_at'].isoformat() if k.get('created_at') else None,
        })
    return jsonify({'api_keys': formatted})


@app.route('/api/settings/api-keys', methods=['POST'])
@login_required
def save_api_key():
    data = request.get_json()
    api_key = data.get('api_key', '').strip()
    api_secret = data.get('api_secret', '').strip()
    label = data.get('label', 'Default')
    is_testnet = data.get('is_testnet', True)
    if not api_key or not api_secret:
        return jsonify({'error': 'API key and secret are required'}), 400
    result = BybitApiKey.save_key(request.user_id, api_key, api_secret, label, is_testnet)
    return jsonify({'message': 'API key saved', 'id': result.get('id') if result else None})


@app.route('/api/settings/api-keys/<int:key_id>', methods=['DELETE'])
@login_required
def delete_api_key(key_id):
    BybitApiKey.delete_key(key_id, request.user_id)
    return jsonify({'message': 'API key deleted'})


# ══════════════════════════════════════════════════════════════
# WATCHLIST
# ══════════════════════════════════════════════════════════════
@app.route('/api/watchlist', methods=['GET'])
@login_required
def get_watchlist():
    symbols = Watchlist.get_all(request.user_id)
    return jsonify({'watchlist': symbols})


@app.route('/api/watchlist', methods=['POST'])
@login_required
def add_to_watchlist():
    data = request.get_json()
    symbol = data.get('symbol', '').upper().strip()
    if not symbol:
        return jsonify({'error': 'Symbol is required'}), 400
    Watchlist.add(request.user_id, symbol)
    return jsonify({'message': f'{symbol} added to watchlist'})


@app.route('/api/watchlist/<symbol>', methods=['DELETE'])
@login_required
def remove_from_watchlist(symbol):
    Watchlist.remove(request.user_id, symbol.upper())
    return jsonify({'message': f'{symbol} removed from watchlist'})


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    db_config.initialize_pool()
    app.run(host='0.0.0.0', port=5000, debug=os.getenv('FLASK_ENV') == 'development')
