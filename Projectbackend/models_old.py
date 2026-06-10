"""
User model and authentication utilities for CryptoVault
"""
import bcrypt
import jwt
import secrets
from datetime import datetime, timedelta
import os
from config import execute_query, execute_transaction


class User:
    """User model class"""
    
    # Interest rates for savings plans
    INTEREST_RATES = {
        'money_lock': 27.0,    # 27% APR
        'flexi_save': 20.0,    # 20% APR
        'flexi_target': 23.0   # 23% APR
    }
    
    def __init__(self, user_data=None):
        if user_data:
            self.id = user_data.get('id')
            self.username = user_data.get('username')
            self.email = user_data.get('email')
            self.password_hash = user_data.get('password_hash')
            self.account_balance = float(user_data.get('account_balance', 0))
            self.created_at = user_data.get('created_at')
            self.is_active = user_data.get('is_active', True)
    
    @staticmethod
    def hash_password(password):
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password, password_hash):
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    
    @staticmethod
    def create_user(username, email, password):
        """Create a new user"""
        password_hash = User.hash_password(password)
        # Use parameter style compatible with both MySQL (%s) and psycopg2
        if os.getenv('DB_ENGINE', '').lower().startswith('post'):
            query = """INSERT INTO users (username, email, password_hash, account_balance)
                       VALUES (%s, %s, %s, %s) RETURNING id"""
            try:
                result = execute_query(query, (username, email, password_hash, 0.00), fetch_one=True, commit=True)
                user_id = result['id'] if result and 'id' in result else None
                return {'success': True, 'user_id': user_id}
            except Exception as e:
                if 'duplicate key value violates unique constraint' in str(e).lower():
                    if 'username' in str(e).lower():
                        return {'success': False, 'error': 'Username already exists'}
                    elif 'email' in str(e).lower():
                        return {'success': False, 'error': 'Email already registered'}
                return {'success': False, 'error': str(e)}
        else:
            query = """
            INSERT INTO users (username, email, password_hash, account_balance)
            VALUES (%s, %s, %s, %s)
            """
            try:
                user_id = execute_query(query, (username, email, password_hash, 0.00), commit=True)
                return {'success': True, 'user_id': user_id}
            except Exception as e:
                if 'Duplicate entry' in str(e):
                    if 'username' in str(e):
                        return {'success': False, 'error': 'Username already exists'}
                    elif 'email' in str(e):
                        return {'success': False, 'error': 'Email already registered'}
                return {'success': False, 'error': str(e)}

    @staticmethod
    def find_by_username(username):
        """Find a user by username"""
        query = "SELECT * FROM users WHERE username = %s AND is_active = TRUE"
        result = execute_query(query, (username,), fetch_one=True)
        return User(result) if result else None
    
    @staticmethod
    def find_by_email(email):
        """Find a user by email"""
        query = "SELECT * FROM users WHERE email = %s AND is_active = TRUE"
        result = execute_query(query, (email,), fetch_one=True)
        return User(result) if result else None
    
    @staticmethod
    def find_by_id(user_id):
        """Find a user by ID"""
        query = "SELECT * FROM users WHERE id = %s AND is_active = TRUE"
        result = execute_query(query, (user_id,), fetch_one=True)
        return User(result) if result else None
    
    @staticmethod
    def authenticate(username_or_email, password):
        """Authenticate a user"""
        # Try username first, then email
        user = User.find_by_username(username_or_email)
        if not user:
            user = User.find_by_email(username_or_email)
        
        if user and User.verify_password(password, user.password_hash):
            return user
        return None
    
    @staticmethod
    def generate_token(user_id):
        """Generate JWT token for user"""
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
        """Verify JWT token"""
        secret_key = os.getenv('JWT_SECRET_KEY', 'default-secret-key')
        try:
            payload = jwt.decode(token, secret_key, algorithms=['HS256'])
            return payload['user_id']
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    @staticmethod
    def create_session(user_id, ip_address=None, user_agent=None):
        """Create a user session"""
        session_token = secrets.token_urlsafe(32)
        lifetime_hours = int(os.getenv('SESSION_LIFETIME_HOURS', 24))
        expires_at = datetime.now() + timedelta(hours=lifetime_hours)
        
        query = """
            INSERT INTO user_sessions (user_id, session_token, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s)
        """
        execute_query(query, (user_id, session_token, expires_at, ip_address, user_agent), commit=True)
        return session_token
    
    @staticmethod
    def validate_session(session_token):
        """Validate a session token"""
        query = """
            SELECT user_id FROM user_sessions 
            WHERE session_token = %s AND expires_at > NOW() AND is_valid = TRUE
        """
        result = execute_query(query, (session_token,), fetch_one=True)
        return result['user_id'] if result else None
    
    @staticmethod
    def invalidate_session(session_token):
        """Invalidate a session"""
        query = "UPDATE user_sessions SET is_valid = FALSE WHERE session_token = %s"
        execute_query(query, (session_token,), commit=True)
    
    def get_balance(self):
        """Get current account balance"""
        query = "SELECT account_balance FROM users WHERE id = %s"
        result = execute_query(query, (self.id,), fetch_one=True)
        return float(result['account_balance']) if result else 0.0
    
    def update_balance(self, amount, operation='add'):
        """Update user balance"""
        if operation == 'add':
            query = "UPDATE users SET account_balance = account_balance + %s WHERE id = %s"
        else:
            query = "UPDATE users SET account_balance = account_balance - %s WHERE id = %s"
        execute_query(query, (amount, self.id), commit=True)
    
    def get_locked_funds(self):
        """Get total locked funds in savings plans"""
        query = """
            SELECT COALESCE(SUM(locked_amount), 0) as total_locked 
            FROM savings_plans 
            WHERE user_id = %s AND status = 'active'
        """
        result = execute_query(query, (self.id,), fetch_one=True)
        return float(result['total_locked']) if result else 0.0
    
    def to_dict(self):
        """Convert user to dictionary (without sensitive data)"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'account_balance': self.account_balance,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Transaction:
    """Transaction model class"""
    
    @staticmethod
    def generate_reference():
        """Generate unique transaction reference"""
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        random_part = secrets.token_hex(4).upper()
        return f"TXN{timestamp}{random_part}"
    
    @staticmethod
    def create_transfer(sender_id, receiver_id, amount, description=None):
        """Create a money transfer between users"""
        # Get sender's current balance
        sender = User.find_by_id(sender_id)
        if not sender:
            return {'success': False, 'error': 'Sender not found'}
        
        if sender.get_balance() < amount:
            return {'success': False, 'error': 'Insufficient balance'}
        
        # Get receiver
        receiver = User.find_by_id(receiver_id)
        if not receiver:
            return {'success': False, 'error': 'Receiver not found'}
        
        reference = Transaction.generate_reference()
        
        # Execute transfer in transaction
        queries = [
            ("UPDATE users SET account_balance = account_balance - %s WHERE id = %s", (amount, sender_id)),
            ("UPDATE users SET account_balance = account_balance + %s WHERE id = %s", (amount, receiver_id)),
            ("""INSERT INTO transactions (sender_id, receiver_id, amount, transaction_type, description, reference_number)
                VALUES (%s, %s, %s, 'transfer', %s, %s)""", 
             (sender_id, receiver_id, amount, description or 'Money Transfer', reference))
        ]
        
        try:
            execute_transaction(queries)
            return {'success': True, 'reference': reference, 'message': 'Transfer successful'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def create_deposit(user_id, amount, description=None):
        """Create a deposit transaction"""
        reference = Transaction.generate_reference()
        
        queries = [
            ("UPDATE users SET account_balance = account_balance + %s WHERE id = %s", (amount, user_id)),
            ("""INSERT INTO transactions (receiver_id, amount, transaction_type, description, reference_number)
                VALUES (%s, %s, 'deposit', %s, %s)""", 
             (user_id, amount, description or 'Account Deposit', reference))
        ]
        
        try:
            execute_transaction(queries)
            return {'success': True, 'reference': reference}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_user_transactions(user_id, limit=50, offset=0):
        """Get transaction history for a user"""
        query = """
            SELECT t.*, 
                   s.username as sender_username, 
                   r.username as receiver_username
            FROM transactions t
            LEFT JOIN users s ON t.sender_id = s.id
            LEFT JOIN users r ON t.receiver_id = r.id
            WHERE t.sender_id = %s OR t.receiver_id = %s
            ORDER BY t.timestamp DESC
            LIMIT %s OFFSET %s
        """
        return execute_query(query, (user_id, user_id, limit, offset), fetch_all=True) or []


class SavingsPlan:
    """Savings plan model class"""
    
    PLAN_TYPES = {
        'money_lock': {'rate': 27.0, 'min_days': 30, 'name': 'Money Lock'},
        'flexi_save': {'rate': 20.0, 'min_days': 7, 'name': 'Flexi Save'},
        'flexi_target': {'rate': 23.0, 'min_days': 14, 'name': 'Flexi Target'}
    }
    
    @staticmethod
    def calculate_interest(principal, rate, days):
        """Calculate interest based on principal, rate, and duration"""
        # Simple interest calculation: I = P * R * T / 365
        annual_rate = rate / 100
        interest = principal * annual_rate * (days / 365)
        return round(interest, 2)
    
    @staticmethod
    def create_plan(user_id, plan_type, amount, duration_days, target_amount=None):
        """Create a new savings plan"""
        if plan_type not in SavingsPlan.PLAN_TYPES:
            return {'success': False, 'error': 'Invalid plan type'}
        
        plan_info = SavingsPlan.PLAN_TYPES[plan_type]
        
        if duration_days < plan_info['min_days']:
            return {'success': False, 'error': f"Minimum duration for {plan_info['name']} is {plan_info['min_days']} days"}
        
        # Check user balance
        user = User.find_by_id(user_id)
        if not user or user.get_balance() < amount:
            return {'success': False, 'error': 'Insufficient balance'}
        
        maturity_date = datetime.now() + timedelta(days=duration_days)
        expected_interest = SavingsPlan.calculate_interest(amount, plan_info['rate'], duration_days)
        
        queries = [
            ("UPDATE users SET account_balance = account_balance - %s WHERE id = %s", (amount, user_id)),
            ("""INSERT INTO savings_plans 
                (user_id, plan_type, locked_amount, interest_rate, maturity_date, expected_interest, target_amount)
                VALUES (%s, %s, %s, %s, %s, %s, %s)""",
             (user_id, plan_type, amount, plan_info['rate'], maturity_date, expected_interest, target_amount))
        ]
        
        try:
            execute_transaction(queries)
            return {
                'success': True, 
                'message': f'{plan_info["name"]} plan created successfully',
                'expected_interest': expected_interest,
                'maturity_date': maturity_date.isoformat()
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_user_plans(user_id, status=None):
        """Get savings plans for a user"""
        if status:
            query = """
                SELECT * FROM savings_plans 
                WHERE user_id = %s AND status = %s
                ORDER BY created_at DESC
            """
            return execute_query(query, (user_id, status), fetch_all=True) or []
        else:
            query = """
                SELECT * FROM savings_plans 
                WHERE user_id = %s
                ORDER BY created_at DESC
            """
            return execute_query(query, (user_id,), fetch_all=True) or []
    
    @staticmethod
    def withdraw_plan(plan_id, user_id):
        """Withdraw from a savings plan"""
        query = "SELECT * FROM savings_plans WHERE id = %s AND user_id = %s AND status = 'active'"
        plan = execute_query(query, (plan_id, user_id), fetch_one=True)
        
        if not plan:
            return {'success': False, 'error': 'Plan not found or already withdrawn'}
        
        # Calculate actual interest (prorated if early withdrawal)
        lock_date = plan['lock_date']
        days_held = (datetime.now() - lock_date).days
        maturity_days = (plan['maturity_date'] - lock_date).days
        
        # Penalty for early withdrawal: 50% interest reduction
        if datetime.now() < plan['maturity_date']:
            actual_interest = SavingsPlan.calculate_interest(
                float(plan['locked_amount']), 
                float(plan['interest_rate']), 
                days_held
            ) * 0.5  # 50% penalty
            status = 'withdrawn'
        else:
            actual_interest = float(plan['expected_interest'])
            status = 'matured'
        
        total_return = float(plan['locked_amount']) + actual_interest
        reference = Transaction.generate_reference()
        
        queries = [
            ("UPDATE users SET account_balance = account_balance + %s WHERE id = %s", (total_return, user_id)),
            ("""UPDATE savings_plans SET status = %s, actual_interest_paid = %s WHERE id = %s""",
             (status, actual_interest, plan_id)),
            ("""INSERT INTO transactions (receiver_id, amount, transaction_type, description, reference_number)
                VALUES (%s, %s, 'interest', %s, %s)""",
             (user_id, actual_interest, f'Interest from {plan["plan_type"]} plan', reference))
        ]
        
        try:
            execute_transaction(queries)
            return {
                'success': True,
                'principal': float(plan['locked_amount']),
                'interest_earned': actual_interest,
                'total_returned': total_return,
                'status': status
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}


class TaxCalculator:
    """Tax calculation utilities"""
    
    # Nigerian tax brackets (simplified for educational purposes)
    TAX_BRACKETS = [
        (300000, 0.07),      # First 300,000 at 7%
        (300000, 0.11),      # Next 300,000 at 11%
        (500000, 0.15),      # Next 500,000 at 15%
        (500000, 0.19),      # Next 500,000 at 19%
        (1600000, 0.21),     # Next 1,600,000 at 21%
        (float('inf'), 0.24) # Above 3,200,000 at 24%
    ]
    
    @staticmethod
    def calculate_tax(income):
        """Calculate estimated tax based on income"""
        tax = 0
        remaining_income = income
        
        for bracket_amount, rate in TaxCalculator.TAX_BRACKETS:
            if remaining_income <= 0:
                break
            taxable_in_bracket = min(remaining_income, bracket_amount)
            tax += taxable_in_bracket * rate
            remaining_income -= bracket_amount
        
        return round(tax, 2)
    
    @staticmethod
    def suggest_lock_amount(income, current_savings=0):
        """Suggest optimal lock-in amount for tax efficiency"""
        estimated_tax = TaxCalculator.calculate_tax(income)
        
        # Suggest locking enough to cover tax with interest earnings
        # Using Money Lock (27% APR) as reference for best returns
        suggested_lock = estimated_tax / 1.27  # Amount that would earn enough interest to cover tax
        
        # Also suggest setting aside at least 20% of income
        alternative_suggestion = income * 0.20
        
        return {
            'estimated_tax': estimated_tax,
            'suggested_lock_for_tax': round(suggested_lock, 2),
            'suggested_savings_20_percent': round(alternative_suggestion, 2),
            'current_savings': current_savings,
            'deficit': max(0, round(suggested_lock - current_savings, 2))
        }
    
    @staticmethod
    def create_tax_record(user_id, income, estimated_tax, suggested_amount):
        """Create a tax record for the user"""
        tax_year = datetime.now().year
        
        query = """
            INSERT INTO tax_records (user_id, estimated_tax, income_amount, suggested_lock_amount, tax_year)
            VALUES (%s, %s, %s, %s, %s)
        """
        try:
            execute_query(query, (user_id, estimated_tax, income, suggested_amount, tax_year), commit=True)
            return {'success': True}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    @staticmethod
    def get_tax_history(user_id):
        """Get tax calculation history for a user"""
        query = """
            SELECT * FROM tax_records 
            WHERE user_id = %s 
            ORDER BY calculation_date DESC
            LIMIT 10
        """
        return execute_query(query, (user_id,), fetch_all=True) or []
