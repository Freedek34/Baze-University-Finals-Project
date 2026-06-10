"""
CryptoVault - Flask Backend Application (Legacy)
Third-party crypto banking app powered by Bybit

Date: February 2026
"""

from flask import Flask, request, jsonify, session
from flask_cors import CORS
from functools import wraps
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import models
from models import User, Transaction, SavingsPlan, TaxCalculator
from config import db_config

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Configure CORS - allow all origins for development
# Use token-based authentication instead of relying on cookies/credentials
CORS(app, 
     supports_credentials=False,
     origins="*",
     allow_headers=["Content-Type", "Authorization", "X-Session-Token"],
     methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
     max_age=3600,
     expose_headers=["Content-Type", "X-Session-Token"])

# Session configuration
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)


# =====================
# Authentication Decorator
# =====================
def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for JWT token in header
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            user_id = User.verify_token(token)
            if user_id:
                request.user_id = user_id
                return f(*args, **kwargs)
        
        # Check for session token
        session_token = request.headers.get('X-Session-Token') or session.get('session_token')
        if session_token:
            user_id = User.validate_session(session_token)
            if user_id:
                request.user_id = user_id
                return f(*args, **kwargs)
        
        return jsonify({'error': 'Authentication required'}), 401
    return decorated_function


# =====================
# Error Handlers
# =====================
@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Resource not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# =====================
# Health Check
# =====================
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'service': 'CryptoVault API'
    })


# =====================
# Authentication Endpoints
# =====================
@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    username = data.get('username', '').strip()
    email = data.get('email', '').strip().lower()
    password = data.get('password', '')
    
    # Validation
    if not username or len(username) < 3:
        return jsonify({'error': 'Username must be at least 3 characters'}), 400
    if not email or '@' not in email:
        return jsonify({'error': 'Valid email is required'}), 400
    if not password or len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Create user
    result = User.create_user(username, email, password)
    
    if result['success']:
        return jsonify({
            'message': 'Registration successful',
            'user_id': result['user_id']
        }), 201
    else:
        return jsonify({'error': result['error']}), 400


@app.route('/api/auth/login', methods=['POST', 'OPTIONS'])
def login():
    """Login user"""
    if request.method == 'OPTIONS':
        return '', 200
    
    data = request.get_json()
    
    print(f"[DEBUG] Raw request data: {data}")
    print(f"[DEBUG] Content-Type: {request.content_type}")
    
    if not data:
        print(f"[DEBUG] No data provided in request")
        return jsonify({'error': 'No data provided'}), 400
    
    username_or_email = data.get('username', '').strip()
    password = data.get('password', '')
    
    print(f"[DEBUG] Extracted username: '{username_or_email}'")
    print(f"[DEBUG] Extracted password length: {len(password)}")
    
    if not username_or_email or not password:
        print(f"[DEBUG] Missing username or password")
        return jsonify({'error': 'Username/email and password are required'}), 400
    
    print(f"[DEBUG] Login attempt for: {username_or_email}")
    
    # Authenticate user
    user = User.authenticate(username_or_email, password)
    
    print(f"[DEBUG] Authentication result: {user is not None}")
    if not user:
        print(f"[DEBUG] User not found or password incorrect for: {username_or_email}")
    
    if user:
        # Generate tokens
        jwt_token = User.generate_token(user.id)
        session_token = User.create_session(
            user.id, 
            request.remote_addr, 
            request.user_agent.string
        )
        
        # Set session
        session['session_token'] = session_token
        session['user_id'] = user.id
        session.permanent = True
        
        return jsonify({
            'message': 'Login successful',
            'token': jwt_token,
            'session_token': session_token,
            'user': user.to_dict()
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401


@app.route('/api/auth/logout', methods=['POST'])
@login_required
def logout():
    """Logout user"""
    session_token = request.headers.get('X-Session-Token') or session.get('session_token')
    if session_token:
        User.invalidate_session(session_token)
    
    session.clear()
    return jsonify({'message': 'Logged out successfully'})


@app.route('/api/auth/me', methods=['GET'])
@login_required
def get_current_user():
    """Get current authenticated user"""
    user = User.find_by_id(request.user_id)
    if user:
        locked_funds = user.get_locked_funds()
        return jsonify({
            'user': user.to_dict(),
            'locked_funds': locked_funds,
            'available_balance': user.account_balance - locked_funds
        })
    return jsonify({'error': 'User not found'}), 404


# =====================
# Account Endpoints
# =====================
@app.route('/api/account/balance', methods=['GET'])
@login_required
def get_balance():
    """Get account balance"""
    user = User.find_by_id(request.user_id)
    if user:
        locked_funds = user.get_locked_funds()
        return jsonify({
            'account_balance': user.account_balance,
            'locked_funds': locked_funds,
            'available_balance': user.account_balance
        })
    return jsonify({'error': 'User not found'}), 404


@app.route('/api/account/deposit', methods=['POST'])
@login_required
def deposit():
    """Deposit money (for demo purposes)"""
    data = request.get_json()
    amount = float(data.get('amount', 0))
    
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    if amount > 1000000:  # Demo limit
        return jsonify({'error': 'Demo deposit limit is 1,000,000'}), 400
    
    result = Transaction.create_deposit(request.user_id, amount)
    
    if result['success']:
        user = User.find_by_id(request.user_id)
        return jsonify({
            'message': 'Deposit successful',
            'reference': result['reference'],
            'new_balance': user.get_balance() if user else 0
        })
    return jsonify({'error': result['error']}), 400


# =====================
# Transfer Endpoints
# =====================
@app.route('/api/transfer/send', methods=['POST'])
@login_required
def send_money():
    """Send money to another user"""
    data = request.get_json()
    
    receiver_username = data.get('receiver_username', '').strip()
    amount = float(data.get('amount', 0))
    description = data.get('description', 'Money Transfer')
    
    if not receiver_username:
        return jsonify({'error': 'Receiver username is required'}), 400
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    # Find receiver
    receiver = User.find_by_username(receiver_username)
    if not receiver:
        return jsonify({'error': 'Receiver not found'}), 404
    
    if receiver.id == request.user_id:
        return jsonify({'error': 'Cannot transfer to yourself'}), 400
    
    # Process transfer
    result = Transaction.create_transfer(
        request.user_id, 
        receiver.id, 
        amount, 
        description
    )
    
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
def lookup_user():
    """Lookup user by username for transfer"""
    username = request.args.get('username', '').strip()
    
    if not username:
        return jsonify({'error': 'Username is required'}), 400
    
    user = User.find_by_username(username)
    if user and user.id != request.user_id:
        return jsonify({
            'found': True,
            'username': user.username,
            'email': user.email[:3] + '***' + user.email[user.email.index('@'):]  # Mask email
        })
    return jsonify({'found': False})


# =====================
# Transaction History
# =====================
@app.route('/api/transactions', methods=['GET'])
@login_required
def get_transactions():
    """Get transaction history"""
    limit = min(int(request.args.get('limit', 50)), 100)
    offset = int(request.args.get('offset', 0))
    
    transactions = Transaction.get_user_transactions(request.user_id, limit, offset)
    
    # Format transactions for response
    formatted_transactions = []
    for t in transactions:
        formatted_transactions.append({
            'id': t['id'],
            'amount': float(t['amount']),
            'type': t['transaction_type'],
            'description': t['description'],
            'reference': t['reference_number'],
            'status': t['status'],
            'timestamp': t['timestamp'].isoformat() if t['timestamp'] else None,
            'sender': t['sender_username'],
            'receiver': t['receiver_username'],
            'is_credit': t['receiver_id'] == request.user_id
        })
    
    return jsonify({'transactions': formatted_transactions})


# =====================
# Savings Plan Endpoints
# =====================
@app.route('/api/savings/plans', methods=['GET'])
@login_required
def get_savings_plans():
    """Get user's savings plans"""
    status = request.args.get('status')
    plans = SavingsPlan.get_user_plans(request.user_id, status)
    
    formatted_plans = []
    for p in plans:
        formatted_plans.append({
            'id': p['id'],
            'plan_type': p['plan_type'],
            'plan_name': SavingsPlan.PLAN_TYPES.get(p['plan_type'], {}).get('name', p['plan_type']),
            'locked_amount': float(p['locked_amount']),
            'interest_rate': float(p['interest_rate']),
            'expected_interest': float(p['expected_interest']),
            'actual_interest_paid': float(p['actual_interest_paid'] or 0),
            'lock_date': p['lock_date'].isoformat() if p['lock_date'] else None,
            'maturity_date': p['maturity_date'].isoformat() if p['maturity_date'] else None,
            'status': p['status'],
            'target_amount': float(p['target_amount']) if p['target_amount'] else None
        })
    
    return jsonify({'plans': formatted_plans})


@app.route('/api/savings/create', methods=['POST'])
@login_required
def create_savings_plan():
    """Create a new savings plan"""
    data = request.get_json()
    
    plan_type = data.get('plan_type')
    amount = float(data.get('amount', 0))
    duration_days = int(data.get('duration_days', 30))
    target_amount = data.get('target_amount')
    
    if plan_type not in SavingsPlan.PLAN_TYPES:
        return jsonify({'error': 'Invalid plan type. Choose from: money_lock, flexi_save, flexi_target'}), 400
    if amount <= 0:
        return jsonify({'error': 'Amount must be positive'}), 400
    
    result = SavingsPlan.create_plan(
        request.user_id, 
        plan_type, 
        amount, 
        duration_days,
        float(target_amount) if target_amount else None
    )
    
    if result['success']:
        return jsonify(result), 201
    return jsonify({'error': result['error']}), 400


@app.route('/api/savings/withdraw/<int:plan_id>', methods=['POST'])
@login_required
def withdraw_savings(plan_id):
    """Withdraw from a savings plan"""
    result = SavingsPlan.withdraw_plan(plan_id, request.user_id)
    
    if result['success']:
        return jsonify(result)
    return jsonify({'error': result['error']}), 400


@app.route('/api/savings/calculate', methods=['POST'])
@login_required
def calculate_savings_interest():
    """Calculate potential interest for a savings plan"""
    data = request.get_json()
    
    plan_type = data.get('plan_type')
    amount = float(data.get('amount', 0))
    duration_days = int(data.get('duration_days', 30))
    
    if plan_type not in SavingsPlan.PLAN_TYPES:
        return jsonify({'error': 'Invalid plan type'}), 400
    
    plan_info = SavingsPlan.PLAN_TYPES[plan_type]
    interest = SavingsPlan.calculate_interest(amount, plan_info['rate'], duration_days)
    
    return jsonify({
        'plan_type': plan_type,
        'plan_name': plan_info['name'],
        'principal': amount,
        'interest_rate': plan_info['rate'],
        'duration_days': duration_days,
        'expected_interest': interest,
        'total_return': amount + interest,
        'effective_daily_rate': round(plan_info['rate'] / 365, 4)
    })


# =====================
# Tax Calculator Endpoints
# =====================
@app.route('/api/tax/calculate', methods=['POST'])
@login_required
def calculate_tax():
    """Calculate estimated tax"""
    data = request.get_json()
    
    income = float(data.get('income', 0))
    
    if income < 0:
        return jsonify({'error': 'Income cannot be negative'}), 400
    
    user = User.find_by_id(request.user_id)
    current_savings = user.get_locked_funds() if user else 0
    
    result = TaxCalculator.suggest_lock_amount(income, current_savings)
    
    # Calculate potential interest from savings plans
    potential_interest = {
        'money_lock': SavingsPlan.calculate_interest(result['suggested_lock_for_tax'], 27, 365),
        'flexi_save': SavingsPlan.calculate_interest(result['suggested_lock_for_tax'], 20, 365),
        'flexi_target': SavingsPlan.calculate_interest(result['suggested_lock_for_tax'], 23, 365)
    }
    
    return jsonify({
        'income': income,
        'estimated_tax': result['estimated_tax'],
        'effective_tax_rate': round((result['estimated_tax'] / income * 100) if income > 0 else 0, 2),
        'suggested_lock_for_tax': result['suggested_lock_for_tax'],
        'suggested_savings_20_percent': result['suggested_savings_20_percent'],
        'current_locked_savings': current_savings,
        'savings_deficit': result['deficit'],
        'potential_interest_earnings': potential_interest
    })


@app.route('/api/tax/save-record', methods=['POST'])
@login_required
def save_tax_record():
    """Save tax calculation record"""
    data = request.get_json()
    
    income = float(data.get('income', 0))
    estimated_tax = float(data.get('estimated_tax', 0))
    suggested_amount = float(data.get('suggested_amount', 0))
    
    result = TaxCalculator.create_tax_record(
        request.user_id, 
        income, 
        estimated_tax, 
        suggested_amount
    )
    
    if result['success']:
        return jsonify({'message': 'Tax record saved successfully'})
    return jsonify({'error': result['error']}), 400


@app.route('/api/tax/history', methods=['GET'])
@login_required
def get_tax_history():
    """Get tax calculation history"""
    history = TaxCalculator.get_tax_history(request.user_id)
    
    formatted_history = []
    for h in history:
        formatted_history.append({
            'id': h['id'],
            'estimated_tax': float(h['estimated_tax']),
            'income_amount': float(h['income_amount']),
            'suggested_lock_amount': float(h['suggested_lock_amount']),
            'tax_year': h['tax_year'],
            'calculation_date': h['calculation_date'].isoformat() if h['calculation_date'] else None
        })
    
    return jsonify({'history': formatted_history})


# =====================
# Plan Information
# =====================
@app.route('/api/info/plans', methods=['GET'])
def get_plan_info():
    """Get information about available savings plans"""
    plans = []
    for plan_type, info in SavingsPlan.PLAN_TYPES.items():
        plans.append({
            'type': plan_type,
            'name': info['name'],
            'interest_rate': info['rate'],
            'min_duration_days': info['min_days'],
            'description': get_plan_description(plan_type)
        })
    
    return jsonify({'plans': plans})


def get_plan_description(plan_type):
    """Get description for plan type"""
    descriptions = {
        'money_lock': 'Lock your money for a fixed period and earn 27% APR. Best for long-term savings with no early withdrawal needed.',
        'flexi_save': 'Flexible savings with 20% APR. Minimum 7-day lock period. Good for short-term goals.',
        'flexi_target': 'Set a savings target and earn 23% APR. Minimum 14-day lock period. Ideal for goal-based savings.'
    }
    return descriptions.get(plan_type, '')


# =====================
# Main Entry Point
# =====================
if __name__ == '__main__':
    # Initialize database connection pool
    db_config.initialize_pool()
    
    # Run the application
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=os.getenv('FLASK_ENV') == 'development'
    )
