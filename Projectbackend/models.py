"""
CryptoVault - Data Models
User management, crypto wallets, Bybit Earn positions, P2P orders
"""
import bcrypt
import jwt
import secrets
from datetime import datetime, timedelta
import os
from config import execute_query, execute_transaction


class User:
    """User model class"""

    def __init__(self, user_data=None):
        if user_data:
            self.id = user_data.get('id')
            self.username = user_data.get('username')
            self.email = user_data.get('email')
            self.password_hash = user_data.get('password_hash')
            self.account_balance = float(user_data.get('account_balance', 0))
            self.preferred_currency = user_data.get('preferred_currency', 'USDT')
            self.created_at = user_data.get('created_at')
            self.is_active = user_data.get('is_active', True)

    @staticmethod
    def hash_password(password):
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

    @staticmethod
    def verify_password(password, password_hash):
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def create_user(username, email, password):
        password_hash = User.hash_password(password)
        query = """INSERT INTO users (username, email, password_hash, account_balance)
                   VALUES (%s, %s, %s, %s) RETURNING id"""
        try:
            result = execute_query(query, (username, email, password_hash, 0.00), fetch_one=True, commit=True)
            user_id = result['id'] if result and 'id' in result else None
            if user_id:
                CryptoWallet.initialize_user_wallets(user_id)
            return {'success': True, 'user_id': user_id}
        except Exception as e:
            err = str(e).lower()
            if 'duplicate key' in err or 'unique' in err:
                if 'username' in err:
                    return {'success': False, 'error': 'Username already exists'}
                elif 'email' in err:
                    return {'success': False, 'error': 'Email already registered'}
            return {'success': False, 'error': str(e)}

    @staticmethod
    def find_by_username(username):
        query = "SELECT * FROM users WHERE username = %s AND is_active = TRUE"
        result = execute_query(query, (username,), fetch_one=True)
        return User(result) if result else None

    @staticmethod
    def find_by_email(email):
        query = "SELECT * FROM users WHERE email = %s AND is_active = TRUE"
        result = execute_query(query, (email,), fetch_one=True)
        return User(result) if result else None

    @staticmethod
    def find_by_id(user_id):
        query = "SELECT * FROM users WHERE id = %s AND is_active = TRUE"
        result = execute_query(query, (user_id,), fetch_one=True)
        return User(result) if result else None

    @staticmethod
    def authenticate(username_or_email, password):
        # Normalize inputs: username/email already trimmed by the caller,
        # ensure password accidental whitespace is ignored to avoid
        # confusion from copy/paste including leading/trailing spaces.
        if isinstance(password, str):
            password = password.strip()
        user = User.find_by_username(username_or_email)
        if not user:
            user = User.find_by_email(username_or_email)
        if user and User.verify_password(password, user.password_hash):
            return user
        return None

    @staticmethod
    def generate_token(user_id):
        secret_key = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
        expires = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES', 3600))
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(seconds=expires),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, secret_key, algorithm='HS256')

    @staticmethod
    def verify_token(token):
        secret_key = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
        try:
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return payload['user_id']
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None

    @staticmethod
    def create_session(user_id, ip_address=None, user_agent=None):
        session_token = secrets.token_urlsafe(32)
        lifetime_hours = int(os.getenv('SESSION_LIFETIME_HOURS', 24))
        expires_at = datetime.now() + timedelta(hours=lifetime_hours)
        query = """INSERT INTO user_sessions (user_id, session_token, expires_at, ip_address, user_agent)
                   VALUES (%s, %s, %s, %s, %s)"""
        execute_query(query, (user_id, session_token, expires_at, ip_address, user_agent), commit=True)
        return session_token

    @staticmethod
    def validate_session(session_token):
        query = """SELECT user_id FROM user_sessions
                   WHERE session_token = %s AND expires_at > NOW() AND is_valid = TRUE"""
        result = execute_query(query, (session_token,), fetch_one=True)
        return result['user_id'] if result else None

    @staticmethod
    def invalidate_session(session_token):
        query = "UPDATE user_sessions SET is_valid = FALSE WHERE session_token = %s"
        execute_query(query, (session_token,), commit=True)

    def get_balance(self, coin=None):
        if coin:
            return CryptoWallet.get_coin_balance(self.id, coin)
        return CryptoWallet.get_total_usd(self.id)

    def update_balance(self, amount, operation='add'):
        if operation == 'add':
            query = "UPDATE users SET account_balance = account_balance + %s WHERE id = %s"
        else:
            query = "UPDATE users SET account_balance = account_balance - %s WHERE id = %s"
        execute_query(query, (amount, self.id), commit=True)

    def get_locked_funds(self):
        query = """SELECT COALESCE(SUM(amount), 0) as total_locked
                   FROM earn_positions WHERE user_id = %s AND status = 'active'"""
        result = execute_query(query, (self.id,), fetch_one=True)
        return float(result['total_locked']) if result else 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'account_balance': self.account_balance,
            'preferred_currency': self.preferred_currency,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class BybitApiKey:
    """Manage user Bybit API keys"""

    @staticmethod
    def save_key(user_id, api_key, api_secret_encrypted, label='Default', is_testnet=True, permissions='read'):
        query = """INSERT INTO bybit_api_keys (user_id, api_key, api_secret_encrypted, label, is_testnet, permissions)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON CONFLICT (user_id, label) DO UPDATE
                   SET api_key = EXCLUDED.api_key,
                       api_secret_encrypted = EXCLUDED.api_secret_encrypted,
                       is_testnet = EXCLUDED.is_testnet,
                       permissions = EXCLUDED.permissions,
                       updated_at = now()
                   RETURNING id"""
        result = execute_query(query, (user_id, api_key, api_secret_encrypted, label, is_testnet, permissions),
                               fetch_one=True, commit=True)
        return result

    @staticmethod
    def get_active_key(user_id):
        query = """SELECT * FROM bybit_api_keys
                   WHERE user_id = %s AND is_active = TRUE
                   ORDER BY created_at DESC LIMIT 1"""
        return execute_query(query, (user_id,), fetch_one=True)

    @staticmethod
    def get_all_keys(user_id):
        query = """SELECT id, api_key, label, permissions, is_testnet, is_active, created_at
                   FROM bybit_api_keys WHERE user_id = %s ORDER BY created_at DESC"""
        return execute_query(query, (user_id,), fetch_all=True) or []

    @staticmethod
    def delete_key(key_id, user_id):
        query = "DELETE FROM bybit_api_keys WHERE id = %s AND user_id = %s"
        execute_query(query, (key_id, user_id), commit=True)


class CryptoWallet:
    """Per-coin wallet balances (source of truth for holdings)"""

    ACCOUNT_TYPE = 'FUND'
    SUPPORTED_COINS = ['USDT', 'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'ADA', 'DOGE', 'AVAX', 'USDC']

    @staticmethod
    def _usd_price(coin):
        row = execute_query(
            "SELECT usd_price_estimate FROM supported_assets WHERE coin = %s",
            (coin.upper(),), fetch_one=True
        )
        if row:
            return float(row['usd_price_estimate'])
        defaults = {'USDT': 1.0, 'USDC': 1.0, 'BTC': 68200.0, 'ETH': 3600.0, 'SOL': 145.0,
                    'BNB': 585.0, 'XRP': 0.52, 'ADA': 0.45, 'DOGE': 0.12, 'AVAX': 28.75}
        return defaults.get(coin.upper(), 1.0)

    @staticmethod
    def ensure_wallet(user_id, coin, account_type=None):
        coin = coin.upper()
        acct = account_type or CryptoWallet.ACCOUNT_TYPE
        query = """INSERT INTO crypto_wallets (user_id, coin, account_type, wallet_label, available_balance, locked_balance, total_balance, usd_value)
                   VALUES (%s, %s, %s, 'Funding', 0, 0, 0, 0)
                   ON CONFLICT (user_id, coin, account_type) DO NOTHING"""
        execute_query(query, (user_id, coin, acct), commit=True)

    @staticmethod
    def initialize_user_wallets(user_id):
        for coin in CryptoWallet.SUPPORTED_COINS:
            CryptoWallet.ensure_wallet(user_id, coin)

    @staticmethod
    def get_coin_balance(user_id, coin, account_type=None):
        coin = coin.upper()
        acct = account_type or CryptoWallet.ACCOUNT_TYPE
        CryptoWallet.ensure_wallet(user_id, coin, acct)
        query = """SELECT available_balance, locked_balance, total_balance, usd_value
                   FROM crypto_wallets WHERE user_id = %s AND coin = %s AND account_type = %s"""
        row = execute_query(query, (user_id, coin, acct), fetch_one=True)
        if not row:
            return 0.0
        return float(row['available_balance'])

    @staticmethod
    def _sync_user_total_usd(user_id):
        total = CryptoWallet.get_total_usd(user_id)
        execute_query(
            "UPDATE users SET account_balance = %s, updated_at = now() WHERE id = %s",
            (total, user_id), commit=True
        )
        return total

    @staticmethod
    def _write_ledger(user_id, coin, amount, balance_after, entry_type, reference=None, description=None, related_user_id=None):
        try:
            execute_query(
                """INSERT INTO wallet_ledger (user_id, coin, amount, balance_after, entry_type, reference_number, description, related_user_id)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (user_id, coin.upper(), amount, balance_after, entry_type, reference, description, related_user_id),
                commit=True
            )
        except Exception:
            pass  # ledger optional if schema not migrated yet

    @staticmethod
    def credit(user_id, coin, amount, entry_type='deposit', reference=None, description=None, related_user_id=None):
        coin = coin.upper()
        amount = float(amount)
        if amount <= 0:
            return {'success': False, 'error': 'Amount must be positive'}
        CryptoWallet.ensure_wallet(user_id, coin)
        price = CryptoWallet._usd_price(coin)
        usd_delta = amount * price
        query = """UPDATE crypto_wallets SET
                   available_balance = available_balance + %s,
                   total_balance = total_balance + %s,
                   usd_value = usd_value + %s,
                   updated_at = now()
                   WHERE user_id = %s AND coin = %s AND account_type = %s
                   RETURNING available_balance"""
        row = execute_query(query, (amount, amount, usd_delta, user_id, coin, CryptoWallet.ACCOUNT_TYPE),
                            fetch_one=True, commit=True)
        balance_after = float(row['available_balance']) if row else amount
        CryptoWallet._write_ledger(user_id, coin, amount, balance_after, entry_type, reference, description, related_user_id)
        CryptoWallet._sync_user_total_usd(user_id)
        return {'success': True, 'balance': balance_after}

    @staticmethod
    def debit(user_id, coin, amount, entry_type='withdraw', reference=None, description=None, related_user_id=None):
        coin = coin.upper()
        amount = float(amount)
        if amount <= 0:
            return {'success': False, 'error': 'Amount must be positive'}
        available = CryptoWallet.get_coin_balance(user_id, coin)
        if available < amount:
            return {'success': False, 'error': f'Insufficient {coin} balance'}
        price = CryptoWallet._usd_price(coin)
        usd_delta = amount * price
        query = """UPDATE crypto_wallets SET
                   available_balance = available_balance - %s,
                   total_balance = total_balance - %s,
                   usd_value = GREATEST(usd_value - %s, 0),
                   updated_at = now()
                   WHERE user_id = %s AND coin = %s AND account_type = %s AND available_balance >= %s
                   RETURNING available_balance"""
        row = execute_query(query, (amount, amount, usd_delta, user_id, coin, CryptoWallet.ACCOUNT_TYPE, amount),
                            fetch_one=True, commit=True)
        if not row:
            return {'success': False, 'error': f'Insufficient {coin} balance'}
        balance_after = float(row['available_balance'])
        CryptoWallet._write_ledger(user_id, coin, -amount, balance_after, entry_type, reference, description, related_user_id)
        CryptoWallet._sync_user_total_usd(user_id)
        return {'success': True, 'balance': balance_after}

    @staticmethod
    def sync_balances(user_id, balances):
        for bal in balances:
            query = """INSERT INTO crypto_wallets (user_id, coin, account_type, available_balance, locked_balance, total_balance, usd_value, last_synced)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                       ON CONFLICT (user_id, coin, account_type) DO UPDATE
                       SET available_balance = EXCLUDED.available_balance,
                           locked_balance = EXCLUDED.locked_balance,
                           total_balance = EXCLUDED.total_balance,
                           usd_value = EXCLUDED.usd_value,
                           last_synced = NOW()"""
            execute_query(query, (
                user_id, bal.get('coin', 'UNKNOWN'), bal.get('account_type', 'UNIFIED'),
                float(bal.get('available', 0)), float(bal.get('locked', 0)),
                float(bal.get('total', 0)), float(bal.get('usd_value', 0)),
            ), commit=True)

    @staticmethod
    def get_balances(user_id, include_zero=False):
        if include_zero:
            query = """SELECT cw.*, sa.name AS asset_name, sa.usd_price_estimate
                       FROM crypto_wallets cw
                       LEFT JOIN supported_assets sa ON sa.coin = cw.coin
                       WHERE cw.user_id = %s AND cw.is_active = TRUE
                       ORDER BY cw.usd_value DESC, cw.coin"""
        else:
            query = """SELECT cw.*, sa.name AS asset_name, sa.usd_price_estimate
                       FROM crypto_wallets cw
                       LEFT JOIN supported_assets sa ON sa.coin = cw.coin
                       WHERE cw.user_id = %s AND cw.total_balance > 0 AND cw.is_active = TRUE
                       ORDER BY cw.usd_value DESC"""
        return execute_query(query, (user_id,), fetch_all=True) or []

    @staticmethod
    def get_fiat_balance(user_id, currency='NGN'):
        try:
            row = execute_query(
                "SELECT available_balance FROM fiat_wallets WHERE user_id = %s AND currency_id = %s",
                (user_id, currency.upper()), fetch_one=True
            )
            return float(row['available_balance']) if row else 0.0
        except Exception:
            return 0.0

    @staticmethod
    def get_total_usd(user_id):
        query = """SELECT COALESCE(SUM(total_balance * COALESCE(sa.usd_price_estimate, 1)), 0) as total
                   FROM crypto_wallets cw
                   LEFT JOIN supported_assets sa ON sa.coin = cw.coin
                   WHERE cw.user_id = %s AND cw.is_active = TRUE"""
        result = execute_query(query, (user_id,), fetch_one=True)
        return float(result['total']) if result else 0.0


class EarnPosition:
    """Bybit Earn/Savings position tracking"""

    @staticmethod
    def create_position(user_id, product_id, product_type, coin, amount, apy, bybit_order_id=None):
        query = """INSERT INTO earn_positions (user_id, bybit_order_id, product_id, product_type, coin, amount, apy)
                   VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING id"""
        result = execute_query(query, (user_id, bybit_order_id, product_id, product_type, coin, amount, apy),
                               fetch_one=True, commit=True)
        return result

    @staticmethod
    def get_user_positions(user_id, status=None):
        if status:
            query = """SELECT * FROM earn_positions WHERE user_id = %s AND status = %s ORDER BY created_at DESC"""
            return execute_query(query, (user_id, status), fetch_all=True) or []
        query = """SELECT * FROM earn_positions WHERE user_id = %s ORDER BY created_at DESC"""
        return execute_query(query, (user_id,), fetch_all=True) or []

    @staticmethod
    def update_position(position_id, user_id, **kwargs):
        sets = []
        params = []
        for k, v in kwargs.items():
            sets.append(f"{k} = %s")
            params.append(v)
        sets.append("updated_at = NOW()")
        params.extend([position_id, user_id])
        query = f"UPDATE earn_positions SET {', '.join(sets)} WHERE id = %s AND user_id = %s"
        execute_query(query, tuple(params), commit=True)

    @staticmethod
    def redeem_position(position_id, user_id):
        query = """UPDATE earn_positions SET status = 'redeemed', redeemed_at = NOW(), updated_at = NOW()
                   WHERE id = %s AND user_id = %s AND status = 'active'"""
        execute_query(query, (position_id, user_id), commit=True)

    @staticmethod
    def get_total_locked(user_id):
        query = """SELECT COALESCE(SUM(amount), 0) as total FROM earn_positions
                   WHERE user_id = %s AND status = 'active'"""
        result = execute_query(query, (user_id,), fetch_one=True)
        return float(result['total']) if result else 0.0

    @staticmethod
    def get_total_interest(user_id):
        query = """SELECT COALESCE(SUM(accrued_interest), 0) as total FROM earn_positions WHERE user_id = %s"""
        result = execute_query(query, (user_id,), fetch_one=True)
        return float(result['total']) if result else 0.0


class P2POrder:
    """P2P order tracking"""

    @staticmethod
    def create_order(user_id, bybit_order_id, token_id, currency_id, side, amount, price, total_price,
                     counterparty_name=None, ad_id=None, vendor_nickname=None):
        reference = Transaction.generate_reference()
        query = """INSERT INTO p2p_orders (user_id, bybit_order_id, ad_id, token_id, currency_id, side,
                   amount, price, total_price, counterparty_name, vendor_nickname, reference_number, status, payment_status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'pending', 'unpaid') RETURNING *"""
        return execute_query(query, (user_id, bybit_order_id, ad_id, token_id, currency_id, side,
                                     amount, price, total_price, counterparty_name, vendor_nickname, reference),
                             fetch_one=True, commit=True)

    @staticmethod
    def get_user_orders(user_id, limit=20, offset=0):
        query = """SELECT * FROM p2p_orders WHERE user_id = %s ORDER BY created_at DESC LIMIT %s OFFSET %s"""
        return execute_query(query, (user_id, limit, offset), fetch_all=True) or []

    @staticmethod
    def find_by_id(order_id, user_id):
        query = "SELECT * FROM p2p_orders WHERE id = %s AND user_id = %s"
        return execute_query(query, (order_id, user_id), fetch_one=True)

    @staticmethod
    def update_status(order_id, user_id, status):
        query = "UPDATE p2p_orders SET status = %s, updated_at = NOW() WHERE id = %s AND user_id = %s"
        execute_query(query, (status, order_id, user_id), commit=True)

    @staticmethod
    def mark_paid(order_id, user_id):
        query = """UPDATE p2p_orders SET payment_status = 'paid', status = 'awaiting_release', updated_at = NOW()
                   WHERE id = %s AND user_id = %s AND payment_status = 'unpaid' RETURNING *"""
        return execute_query(query, (order_id, user_id), fetch_one=True, commit=True)

    @staticmethod
    def complete_deposit(order_id, user_id):
        order = P2POrder.find_by_id(order_id, user_id)
        if not order:
            return {'success': False, 'error': 'Order not found'}
        if order['status'] == 'completed':
            return {'success': False, 'error': 'Order already completed'}
        if order['payment_status'] != 'paid':
            return {'success': False, 'error': 'Mark payment as transferred first'}
        amount = float(order['amount'])
        coin = order['token_id']
        vendor = order.get('vendor_nickname') or order.get('counterparty_name') or 'P2P Vendor'
        desc = f'P2P purchase from {vendor}'
        queries = [
            ("UPDATE p2p_orders SET status = 'completed', updated_at = NOW() WHERE id = %s", (order_id,)),
        ]
        try:
            execute_transaction(queries)
            result = Transaction.create_deposit(
                user_id, amount, description=desc, coin=coin,
                tx_hash=f"P2P-{order.get('reference_number', order_id)}"
            )
            if result['success']:
                return {'success': True, 'reference': result['reference'], 'amount': amount, 'coin': coin}
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}


class Transaction:
    """Transaction model class"""

    @staticmethod
    def generate_reference():
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(4).upper()
        return f"TXN{timestamp}{random_part}"

    @staticmethod
    def create_transfer(sender_id, receiver_id, amount, description=None, coin='USDT'):
        sender = User.find_by_id(sender_id)
        if not sender:
            return {'success': False, 'error': 'Sender not found'}
        coin = coin.upper()
        amount = float(amount)
        if sender.get_balance(coin) < amount:
            return {'success': False, 'error': f'Insufficient {coin} balance'}
        receiver = User.find_by_id(receiver_id)
        if not receiver:
            return {'success': False, 'error': 'Receiver not found'}
        reference = Transaction.generate_reference()
        debit = CryptoWallet.debit(sender_id, coin, amount, 'transfer_out', reference,
                                   description or 'Crypto Transfer', receiver_id)
        if not debit['success']:
            return debit
        CryptoWallet.credit(receiver_id, coin, amount, 'transfer_in', reference,
                            description or 'Crypto Transfer', sender_id)
        execute_query(
            """INSERT INTO transactions (sender_id, receiver_id, amount, transaction_type, description, reference_number, coin)
               VALUES (%s, %s, %s, 'transfer', %s, %s, %s)""",
            (sender_id, receiver_id, amount, description or 'Crypto Transfer', reference, coin),
            commit=True
        )
        return {'success': True, 'reference': reference}

    @staticmethod
    def create_deposit(user_id, amount, description=None, coin='USDT', tx_hash=None):
        coin = coin.upper()
        amount = float(amount)
        reference = Transaction.generate_reference()
        if amount >= 0:
            credit = CryptoWallet.credit(user_id, coin, amount, 'deposit', reference, description or 'Deposit')
            if not credit['success']:
                return credit
            tx_type = 'deposit'
            tx_amount = amount
        else:
            debit = CryptoWallet.debit(user_id, coin, abs(amount), 'withdraw', reference, description or 'Withdrawal')
            if not debit['success']:
                return debit
            tx_type = 'withdraw'
            tx_amount = amount
        execute_query(
            """INSERT INTO transactions (receiver_id, amount, transaction_type, description, reference_number, coin, tx_hash)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, tx_amount, tx_type, description or 'Deposit', reference, coin, tx_hash),
            commit=True
        )
        return {'success': True, 'reference': reference}

    @staticmethod
    def get_user_transactions(user_id, limit=50, offset=0):
        query = """
            SELECT t.*, s.username as sender_username, r.username as receiver_username
            FROM transactions t
            LEFT JOIN users s ON t.sender_id = s.id
            LEFT JOIN users r ON t.receiver_id = r.id
            WHERE t.sender_id = %s OR t.receiver_id = %s
            ORDER BY t.timestamp DESC LIMIT %s OFFSET %s
        """
        return execute_query(query, (user_id, user_id, limit, offset), fetch_all=True) or []


class CryptoDepositRequest:
    """On-chain crypto deposit flow tracking"""

    @staticmethod
    def create(user_id, coin, network, deposit_address, amount=None, tag_memo=None):
        reference = Transaction.generate_reference()
        query = """INSERT INTO crypto_deposit_requests
                   (user_id, coin, network, amount, deposit_address, tag_memo, reference_number, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'awaiting_transfer') RETURNING *"""
        return execute_query(query, (user_id, coin, network, amount, deposit_address, tag_memo, reference),
                             fetch_one=True, commit=True)

    @staticmethod
    def find_by_id(request_id, user_id):
        query = """SELECT * FROM crypto_deposit_requests WHERE id = %s AND user_id = %s"""
        return execute_query(query, (request_id, user_id), fetch_one=True)

    @staticmethod
    def confirm(request_id, user_id, amount):
        req = CryptoDepositRequest.find_by_id(request_id, user_id)
        if not req:
            return {'success': False, 'error': 'Deposit request not found'}
        if req['status'] == 'completed':
            return {'success': False, 'error': 'Deposit already completed'}
        coin = req['coin']
        network = req['network']
        desc = f'Crypto deposit ({coin} via {network})'
        queries = [
            ("UPDATE crypto_deposit_requests SET status = 'completed', amount = %s, completed_at = NOW(), updated_at = NOW() WHERE id = %s",
             (amount, request_id)),
        ]
        try:
            execute_transaction(queries)
            result = Transaction.create_deposit(
                user_id, amount,
                description=desc, coin=coin,
                tx_hash=f"DEMO-{req['reference_number']}"
            )
            if result['success']:
                return {'success': True, 'reference': result['reference'], 'coin': coin, 'amount': amount}
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}


class FiatPurchaseRequest:
    """Buy crypto with fiat (NGN card demo)"""

    @staticmethod
    def create(user_id, coin, fiat_currency, fiat_amount, crypto_amount, exchange_rate, card_last_four):
        reference = Transaction.generate_reference()
        query = """INSERT INTO fiat_purchase_requests
                   (user_id, coin, fiat_currency, fiat_amount, crypto_amount, exchange_rate, card_last_four, reference_number, status)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'processing') RETURNING *"""
        return execute_query(query, (user_id, coin, fiat_currency, fiat_amount, crypto_amount,
                                     exchange_rate, card_last_four, reference),
                             fetch_one=True, commit=True)

    @staticmethod
    def find_by_id(request_id, user_id):
        query = """SELECT * FROM fiat_purchase_requests WHERE id = %s AND user_id = %s"""
        return execute_query(query, (request_id, user_id), fetch_one=True)

    @staticmethod
    def complete(request_id, user_id):
        req = FiatPurchaseRequest.find_by_id(request_id, user_id)
        if not req:
            return {'success': False, 'error': 'Purchase not found'}
        if req['status'] == 'completed':
            return {'success': False, 'error': 'Purchase already completed'}
        amount = float(req['crypto_amount'])
        coin = req['coin']
        desc = f'Card purchase ({req["fiat_currency"]} {float(req["fiat_amount"]):.2f})'
        queries = [
            ("UPDATE fiat_purchase_requests SET status = 'completed', completed_at = NOW(), updated_at = NOW() WHERE id = %s",
             (request_id,)),
        ]
        try:
            execute_transaction(queries)
            result = Transaction.create_deposit(user_id, amount, description=desc, coin=coin,
                                                tx_hash=f"CARD-{req['reference_number']}")
            if result['success']:
                return {'success': True, 'reference': result['reference'], 'coin': coin, 'amount': amount}
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}


class BybitInternalTransfer:
    """Receive crypto from another platform user"""

    @staticmethod
    def search_users(query, exclude_user_id, limit=10):
        q = f"%{query.strip()}%"
        sql = """SELECT id, username, email, bybit_uid, display_name
                 FROM users
                 WHERE is_active = TRUE AND id != %s
                 AND (username ILIKE %s OR display_name ILIKE %s OR bybit_uid ILIKE %s OR email ILIKE %s)
                 ORDER BY username LIMIT %s"""
        return execute_query(sql, (exclude_user_id, q, q, q, q, limit), fetch_all=True) or []

    @staticmethod
    def create(receiver_id, sender_id, amount, coin='USDT'):
        reference = Transaction.generate_reference()
        query = """INSERT INTO bybit_internal_transfers
                   (receiver_id, sender_id, amount, coin, reference_number, status)
                   VALUES (%s, %s, %s, %s, %s, 'pending') RETURNING *"""
        return execute_query(query, (receiver_id, sender_id, amount, coin, reference),
                             fetch_one=True, commit=True)

    @staticmethod
    def find_by_id(transfer_id, receiver_id):
        query = """SELECT t.*, s.username as sender_username, s.display_name as sender_display_name
                   FROM bybit_internal_transfers t
                   JOIN users s ON t.sender_id = s.id
                   WHERE t.id = %s AND t.receiver_id = %s"""
        return execute_query(query, (transfer_id, receiver_id), fetch_one=True)

    @staticmethod
    def approve(transfer_id, receiver_id):
        transfer = BybitInternalTransfer.find_by_id(transfer_id, receiver_id)
        if not transfer:
            return {'success': False, 'error': 'Transfer request not found'}
        if transfer['status'] == 'completed':
            return {'success': False, 'error': 'Transfer already completed'}
        amount = float(transfer['amount'])
        coin = transfer['coin']
        sender_name = transfer.get('sender_display_name') or transfer.get('sender_username', 'User')
        desc = f'Received from {sender_name}'
        queries = [
            ("UPDATE bybit_internal_transfers SET status = 'completed', completed_at = NOW(), updated_at = NOW() WHERE id = %s",
             (transfer_id,)),
        ]
        try:
            execute_transaction(queries)
            result = Transaction.create_deposit(
                receiver_id, amount, description=desc, coin=coin,
                tx_hash=f"INT-{transfer['reference_number']}"
            )
            if result['success']:
                return {
                    'success': True, 'reference': result['reference'],
                    'sender_name': sender_name, 'amount': amount, 'coin': coin
                }
            return result
        except Exception as e:
            return {'success': False, 'error': str(e)}


class Watchlist:
    """User watchlist management"""

    @staticmethod
    def add(user_id, symbol):
        query = """INSERT INTO watchlist (user_id, symbol) VALUES (%s, %s) ON CONFLICT DO NOTHING"""
        execute_query(query, (user_id, symbol), commit=True)

    @staticmethod
    def remove(user_id, symbol):
        query = "DELETE FROM watchlist WHERE user_id = %s AND symbol = %s"
        execute_query(query, (user_id, symbol), commit=True)

    @staticmethod
    def get_all(user_id):
        query = "SELECT symbol FROM watchlist WHERE user_id = %s ORDER BY added_at DESC"
        results = execute_query(query, (user_id,), fetch_all=True) or []
        return [r['symbol'] for r in results]
