"""
Bybit V5 API Service for CryptoVault
Handles all communication with Bybit exchange APIs:
  - Earn (Savings) products
  - P2P trading
  - Market data
  - Wallet/Asset balances

Reference: https://bybit-exchange.github.io/docs/v5/intro
"""

import hashlib
import hmac
import json
import time
import requests
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

BYBIT_MAINNET_URL = "https://api.bybit.com"
BYBIT_TESTNET_URL = "https://api-testnet.bybit.com"


class BybitService:
    """Bybit V5 API wrapper"""

    def __init__(self, api_key=None, api_secret=None, testnet=True):
        self.api_key = api_key or os.getenv('BYBIT_API_KEY', '')
        self.api_secret = api_secret or os.getenv('BYBIT_API_SECRET', '')
        self.testnet = testnet if testnet is not None else os.getenv('BYBIT_TESTNET', 'true').lower() == 'true'
        self.base_url = BYBIT_TESTNET_URL if self.testnet else BYBIT_MAINNET_URL
        self.recv_window = 5000
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    # ─── Signature ────────────────────────────────────────────────
    def _generate_signature(self, timestamp, payload_str):
        """Generate HMAC SHA256 signature for Bybit V5 API"""
        sign_string = f"{timestamp}{self.api_key}{self.recv_window}{payload_str}"
        return hmac.new(
            self.api_secret.encode('utf-8'),
            sign_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    def _get_headers(self, timestamp, signature):
        return {
            'X-BAPI-API-KEY': self.api_key,
            'X-BAPI-SIGN': signature,
            'X-BAPI-SIGN-TYPE': '2',
            'X-BAPI-TIMESTAMP': str(timestamp),
            'X-BAPI-RECV-WINDOW': str(self.recv_window),
            'Content-Type': 'application/json',
        }

    # ─── Core request methods ─────────────────────────────────────
    def _signed_get(self, endpoint, params=None):
        """Signed GET request"""
        params = params or {}
        timestamp = int(time.time() * 1000)
        query_string = '&'.join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
        signature = self._generate_signature(timestamp, query_string)
        headers = self._get_headers(timestamp, signature)

        url = f"{self.base_url}{endpoint}"
        if query_string:
            url += f"?{query_string}"

        try:
            resp = self.session.get(url, headers=headers, timeout=4)
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            logger.error(f"Bybit GET error: {e}")
            return {'retCode': -1, 'retMsg': str(e), 'result': {}}

    def _signed_post(self, endpoint, data=None):
        """Signed POST request"""
        data = data or {}
        timestamp = int(time.time() * 1000)
        payload_str = json.dumps(data)
        signature = self._generate_signature(timestamp, payload_str)
        headers = self._get_headers(timestamp, signature)

        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.post(url, headers=headers, data=payload_str, timeout=4)
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            logger.error(f"Bybit POST error: {e}")
            return {'retCode': -1, 'retMsg': str(e), 'result': {}}

    def _public_get(self, endpoint, params=None):
        """Unsigned public GET request"""
        params = params or {}
        url = f"{self.base_url}{endpoint}"
        query_string = '&'.join(f"{k}={v}" for k, v in sorted(params.items()) if v is not None)
        if query_string:
            url += f"?{query_string}"

        try:
            resp = self.session.get(url, timeout=4)
            return self._handle_response(resp)
        except requests.exceptions.RequestException as e:
            logger.error(f"Bybit public GET error: {e}")
            return {'retCode': -1, 'retMsg': str(e), 'result': {}}

    def _handle_response(self, resp):
        """Parse and validate response"""
        try:
            data = resp.json()
        except Exception:
            return {'retCode': -1, 'retMsg': 'Invalid JSON response', 'result': {}}

        ret_code = data.get('retCode', data.get('ret_code', -1))
        if ret_code != 0:
            logger.warning(f"Bybit API error: {data.get('retMsg', data.get('ret_msg', 'Unknown'))}")
        return data

    # ─── Market Data (Public) ─────────────────────────────────────
    def get_tickers(self, category='spot', symbol=None):
        """Get market tickers"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        return self._public_get('/v5/market/tickers', params)

    def get_kline(self, symbol, interval='60', category='spot', limit=100):
        """Get kline/candlestick data"""
        return self._public_get('/v5/market/kline', {
            'category': category,
            'symbol': symbol,
            'interval': interval,
            'limit': limit,
        })

    def get_orderbook(self, symbol, category='spot', limit=25):
        """Get order book"""
        return self._public_get('/v5/market/orderbook', {
            'category': category,
            'symbol': symbol,
            'limit': limit,
        })

    def get_server_time(self):
        """Get Bybit server time"""
        return self._public_get('/v5/market/time')

    def get_instruments_info(self, category='spot', symbol=None):
        """Get instrument info"""
        params = {'category': category}
        if symbol:
            params['symbol'] = symbol
        return self._public_get('/v5/market/instruments-info', params)

    # ─── Wallet / Asset ───────────────────────────────────────────
    def get_wallet_balance(self, account_type='UNIFIED', coin=None):
        """Get wallet balance for all coins or specific coin"""
        params = {'accountType': account_type}
        if coin:
            params['coin'] = coin
        return self._signed_get('/v5/account/wallet-balance', params)

    def get_all_coins_balance(self, account_type='FUND', coin=None):
        """Get all coins balance (funding account)"""
        params = {'accountType': account_type}
        if coin:
            params['coin'] = coin
        return self._signed_get('/v5/asset/transfer/query-account-coins-balance', params)

    def get_deposit_address(self, coin, chain_type=None):
        """Get deposit address for a coin"""
        params = {'coin': coin}
        if chain_type:
            params['chainType'] = chain_type
        return self._signed_get('/v5/asset/deposit/query-address', params)

    def get_coin_info(self, coin=None):
        """Get coin information (networks, fees, etc.)"""
        params = {}
        if coin:
            params['coin'] = coin
        return self._signed_get('/v5/asset/coin/query-info', params)

    def create_internal_transfer(self, coin, amount, from_account, to_account, transfer_id=None):
        """Transfer between account types"""
        import uuid
        return self._signed_post('/v5/asset/transfer/inter-transfer', {
            'transferId': transfer_id or str(uuid.uuid4()),
            'coin': coin,
            'amount': str(amount),
            'fromAccountType': from_account,
            'toAccountType': to_account,
        })

    def create_withdrawal(self, coin, chain, address, amount, tag=None, force_chain=None):
        """Submit a withdrawal request"""
        import uuid
        data = {
            'coin': coin,
            'chain': chain,
            'address': address,
            'amount': str(amount),
            'timestamp': int(time.time() * 1000),
            'forceChain': 0 if force_chain is None else force_chain,
            'accountType': 'FUND',
        }
        if tag:
            data['tag'] = tag
        return self._signed_post('/v5/asset/withdraw/create', data)

    # ─── Earn / Savings ───────────────────────────────────────────
    def get_earn_products(self, coin=None, product_type=None):
        """
        Get available Bybit Earn/Savings products
        Endpoint: /v5/earn/product
        """
        params = {}
        if coin:
            params['coin'] = coin
        if product_type:
            params['productType'] = product_type
        return self._signed_get('/v5/earn/product', params)

    def subscribe_earn(self, product_id, amount, coin, serial_no=None):
        """
        Subscribe to a Bybit Earn product (place earn order)
        Endpoint: /v5/earn/place-order
        """
        import uuid
        data = {
            'productId': product_id,
            'amount': str(amount),
            'coin': coin,
        }
        if serial_no:
            data['serialNo'] = serial_no
        else:
            data['serialNo'] = str(uuid.uuid4())
        return self._signed_post('/v5/earn/place-order', data)

    def redeem_earn(self, product_id, amount, coin, serial_no=None):
        """
        Redeem from a Bybit Earn product
        Endpoint: /v5/earn/place-order (with redeem action)
        """
        import uuid
        data = {
            'productId': product_id,
            'amount': str(amount),
            'coin': coin,
            'serialNo': serial_no or str(uuid.uuid4()),
        }
        return self._signed_post('/v5/earn/place-order', data)

    def get_earn_positions(self, coin=None, product_type=None):
        """
        Get current earn/savings positions
        Endpoint: /v5/earn/position
        """
        params = {}
        if coin:
            params['coin'] = coin
        if product_type:
            params['productType'] = product_type
        return self._signed_get('/v5/earn/position', params)

    def get_earn_orders(self, coin=None, order_id=None):
        """
        Get earn order history
        Endpoint: /v5/earn/order
        """
        params = {}
        if coin:
            params['coin'] = coin
        if order_id:
            params['orderId'] = order_id
        return self._signed_get('/v5/earn/order', params)

    def get_yield_history(self, coin=None, product_type=None):
        """
        Get yield/interest history
        Endpoint: /v5/earn/yield
        """
        params = {}
        if coin:
            params['coin'] = coin
        if product_type:
            params['productType'] = product_type
        return self._signed_get('/v5/earn/yield', params)

    # ─── P2P Trading ──────────────────────────────────────────────
    def get_p2p_online_ads(self, token_id='USDT', currency_id='NGN', side='0', page=1, size=20):
        """
        Get public P2P advertisements
        side: 0=buy, 1=sell
        Try signed request first, fall back to public POST if API key is invalid.
        """
        payload = {
            'tokenId': token_id,
            'currencyId': currency_id,
            'side': str(side),
            'page': str(page),
            'size': str(size),
        }
        # Try signed request first
        resp = self._signed_post('/v5/p2p/item/online', payload)
        if resp.get('retCode') == 0:
            return resp
        # If API key error, try as public POST (no auth headers)
        ret_msg = (resp.get('retMsg') or '').lower()
        if 'api key' in ret_msg or 'invalid' in ret_msg or 'auth' in ret_msg:
            logger.info("Signed P2P request failed, trying public endpoint...")
            try:
                url = f"{self.base_url}/v5/p2p/item/online"
                r = self.session.post(url, json=payload, timeout=10)
                public_resp = self._handle_response(r)
                if public_resp.get('retCode') == 0:
                    return public_resp
            except Exception as e:
                logger.warning(f"Public P2P fallback also failed: {e}")
        return resp

    def get_p2p_ads_list(self, **kwargs):
        """Get user's own P2P ads"""
        return self._signed_post('/v5/p2p/item/personal/list', kwargs)

    def create_p2p_ad(self, token_id, currency_id, side, price, quantity,
                      min_amount, max_amount, payment_ids, remark='', **kwargs):
        """Create a new P2P advertisement"""
        data = {
            'tokenId': token_id,
            'currencyId': currency_id,
            'side': str(side),
            'priceType': str(kwargs.get('price_type', 0)),
            'price': str(price),
            'quantity': str(quantity),
            'minAmount': str(min_amount),
            'maxAmount': str(max_amount),
            'paymentIds': payment_ids,
            'remark': remark,
            'paymentPeriod': str(kwargs.get('payment_period', 15)),
            'itemType': kwargs.get('item_type', 'ORIGIN'),
            'tradingPreferenceSet': kwargs.get('trading_preferences', {
                'hasUnPostAd': 0, 'isKyc': 1, 'isEmail': 0,
                'isMobile': 0, 'hasRegisterTime': 0,
                'registerTimeThreshold': 0,
                'orderFinishNumberDay30': 0, 'completeRateDay30': '',
                'nationalLimit': '', 'hasOrderFinishNumberDay30': 0,
                'hasCompleteRateDay30': 0, 'hasNationalLimit': 0
            }),
        }
        return self._signed_post('/v5/p2p/item/create', data)

    def remove_p2p_ad(self, item_id):
        """Remove a P2P ad"""
        return self._signed_post('/v5/p2p/item/cancel', {'itemId': str(item_id)})

    def get_p2p_orders(self, page=1, size=10, **kwargs):
        """Get all P2P orders"""
        data = {'page': str(page), 'size': str(size)}
        data.update({k: str(v) for k, v in kwargs.items()})
        return self._signed_post('/v5/p2p/order/simplifyList', data)

    def get_p2p_pending_orders(self, page=1, size=10):
        """Get pending P2P orders"""
        return self._signed_post('/v5/p2p/order/pending/simplifyList', {
            'page': str(page), 'size': str(size)
        })

    def get_p2p_order_details(self, order_id):
        """Get P2P order details"""
        return self._signed_post('/v5/p2p/order/info', {'orderId': str(order_id)})

    def mark_p2p_paid(self, order_id, payment_type, payment_id):
        """Mark P2P order as paid"""
        return self._signed_post('/v5/p2p/order/pay', {
            'orderId': str(order_id),
            'paymentType': str(payment_type),
            'paymentId': str(payment_id),
        })

    def release_p2p_assets(self, order_id):
        """Release assets for completed P2P order"""
        return self._signed_post('/v5/p2p/order/finish', {'orderId': str(order_id)})

    def get_p2p_account_info(self):
        """Get P2P account information"""
        return self._signed_post('/v5/p2p/user/personal/info', {})

    def get_p2p_payment_methods(self):
        """Get user's P2P payment methods"""
        return self._signed_post('/v5/p2p/user/payment/list', {})

    def get_p2p_chat_messages(self, order_id, size=50, start_message_id=0):
        """Get chat messages for a P2P order"""
        return self._signed_post('/v5/p2p/order/message/listpage', {
            'orderId': str(order_id),
            'size': str(size),
            'startMessageId': str(start_message_id),
        })

    def send_p2p_chat_message(self, order_id, message, content_type='str', msg_uuid=None):
        """Send a chat message in P2P order"""
        import uuid
        return self._signed_post('/v5/p2p/order/message/send', {
            'orderId': str(order_id),
            'message': message,
            'contentType': content_type,
            'msgUuid': msg_uuid or uuid.uuid4().hex,
        })


class BybitServiceFactory:
    """Factory to create BybitService instances per user"""

    _default_instance = None

    @classmethod
    def get_default(cls):
        """Get default instance using env vars"""
        if cls._default_instance is None:
            cls._default_instance = BybitService()
        return cls._default_instance

    @classmethod
    def get_for_user(cls, api_key, api_secret, testnet=True):
        """Get instance for specific user API keys"""
        return BybitService(api_key=api_key, api_secret=api_secret, testnet=testnet)
