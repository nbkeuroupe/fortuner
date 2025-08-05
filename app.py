# app.py - Production Card Payment Terminal
from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS
import os, json, hashlib, datetime, time
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import validators
from decimal import Decimal

# Import our modules
from utils import check_password, set_password, login_required, send_otp, verify_otp, save_transaction, load_transactions
from iso_client import send_iso8583_request
from crypto_utils import process_crypto_payout
try:
    from config import config, USERNAME, PASSWORD_FILE, WALLETS_FILE
except ImportError:
    # Fallback for local testing
    class Config:
        SECRET_KEY = 'dev-secret-key'
        DEBUG = True
        MAX_TRANSACTION_AMOUNT = 10000000.00
        CONVERSION_FEE_PERCENT = 2.5
        RATE_LIMIT_PER_MINUTE = 60
        RATE_LIMIT_PER_HOUR = 1000
    
    config = Config()
    USERNAME = "blackrock"
    PASSWORD_FILE = "data/passwords.json"
    WALLETS_FILE = "data/wallets.json"
from logger import (
    log_transaction_start, log_security_event, log_system_error, 
    log_performance_metric, payment_logger
)

# Initialize Flask app with production settings
app = Flask(__name__)
app.config.from_object(config)

# Enable CORS for mobile compatibility
CORS(app, origins=["*"], supports_credentials=True)

# Initialize rate limiter
limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=[f"{config.RATE_LIMIT_PER_MINUTE} per minute", f"{config.RATE_LIMIT_PER_HOUR} per hour"]
)

# Production middleware and security
@app.before_request
def before_request():
    """Pre-request processing"""
    g.start_time = time.time()
    g.request_id = hashlib.md5(f"{time.time()}{request.remote_addr}".encode()).hexdigest()[:8]
    
    # Security headers
    if request.endpoint and request.endpoint.startswith('static'):
        return
    
    # Log security events for suspicious activity
    if request.method == 'POST' and request.endpoint == 'login':
        if session.get('failed_attempts', 0) >= config.MAX_LOGIN_ATTEMPTS:
            log_security_event(
                'login_lockout', 
                request.form.get('username', 'unknown'),
                request.remote_addr
            )
            flash(f"Account locked. Try again in {config.LOCKOUT_DURATION} seconds.")
            return redirect(url_for('login'))

@app.after_request
def after_request(response):
    """Post-request processing"""
    # Add security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    
    # Log performance metrics
    if hasattr(g, 'start_time'):
        duration = int((time.time() - g.start_time) * 1000)
        log_performance_metric(f"request_{request.endpoint or 'unknown'}", duration, "ms")
    
    return response

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('error.html', error_code=404, error_message="Page not found"), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    log_system_error(error, {"context": "flask_500_error", "request_id": getattr(g, 'request_id', 'unknown')})
    return render_template('error.html', error_code=500, error_message="Internal server error"), 500

@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit errors"""
    log_security_event('rate_limit_exceeded', 'anonymous', request.remote_addr)
    return jsonify({"error": "Rate limit exceeded", "retry_after": str(e.retry_after)}), 429

# Production merchant wallets (secure configuration)
MERCHANT_WALLETS = {
    'trc20': {
        'address': os.environ.get('TRON_MERCHANT_WALLET', 'TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE'),
        'network': 'TRON',
        'label': 'TRON (TRC-20) - Lower fees ⚡',
        'token': 'USDT'
    },
    'erc20': {
        'address': os.environ.get('ETH_MERCHANT_WALLET', '0x742d35Cc6634C0532925a3b8D0C9f2b8b8b8b8b8'),
        'network': 'ETHEREUM', 
        'label': 'Ethereum (ERC-20) - Higher fees 💰',
        'token': 'USDT'
    }
}

# Legacy wallet loading for backward compatibility
try:
    with open(WALLETS_FILE) as f:
        WALLETS = json.load(f)
except FileNotFoundError:
    WALLETS = MERCHANT_WALLETS
    # Create default wallets file
    os.makedirs(os.path.dirname(WALLETS_FILE), exist_ok=True)
    with open(WALLETS_FILE, 'w') as f:
        json.dump(WALLETS, f, indent=2)

# Supported Protocols
PROTOCOLS = {
    "POS Terminal -101.1 (4-digit approval)": 4,
    "POS Terminal -101.4 (6-digit approval)": 6,
    "POS Terminal -101.6 (Pre-authorization)": 6,
    "POS Terminal -101.7 (4-digit approval)": 4,
    "POS Terminal -101.8 (PIN-LESS transaction)": 4,
    "POS Terminal -201.1 (6-digit approval)": 6,
    "POS Terminal -201.3 (6-digit approval)": 6,
    "POS Terminal -201.5 (6-digit approval)": 6
}

# Label mapping for wallet dropdown
WALLET_LABELS = {
    "usdt_trc20": "USDT TRC-20 (TRON Network)",
    "usdt_erc20": "USDT ERC-20 (Ethereum Network)"
}

@app.route('/')
def home():
    """Main card terminal interface"""
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    return render_template('terminal.html', 
                         protocols=PROTOCOLS, 
                         merchant_wallets=MERCHANT_WALLETS,
                         max_amount=config.MAX_TRANSACTION_AMOUNT)

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    try:
        # Basic health checks
        status = {
            "status": "healthy",
            "timestamp": datetime.datetime.now().isoformat(),
            "version": "1.0.0",
            "services": {
                "flask": "running",
                "crypto_processor": "initialized" if config.TRON_PRIVATE_KEY else "not_configured",
                "wallets": "loaded" if WALLETS else "empty"
            }
        }
        return jsonify(status), 200
    except Exception as e:
        log_system_error(e, {"context": "health_check"})
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/api/v1/settlement', methods=['POST'])
@limiter.limit("100 per minute")
def settlement_webhook():
    """Webhook endpoint for card terminal settlement notifications"""
    try:
        # This endpoint receives settlement confirmations from your card terminals
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Invalid JSON payload"}), 400
        
        # Extract settlement data
        transaction_id = data.get('transaction_id')
        card_number = data.get('card_number')
        amount = data.get('amount')
        merchant_id = data.get('merchant_id')
        wallet_address = data.get('wallet_address')
        network = data.get('network', 'TRON')
        fund_type = data.get('fund_type', 'M0')
        
        # Validate required fields
        if not all([transaction_id, card_number, amount, merchant_id, wallet_address]):
            return jsonify({"error": "Missing required fields"}), 400
        
        # Log settlement start
        log_transaction_start(card_number, amount, merchant_id, "API_SETTLEMENT")
        
        # Process crypto payout immediately
        tx_hash = process_crypto_payout(
            wallet_address, 
            float(amount), 
            network, 
            "USDT",
            fund_type
        )
        
        # Save transaction record
        transaction_data = {
            "txn_id": transaction_id,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "pan": card_number[-4:],
            "amount": amount,
            "merchant_id": merchant_id,
            "wallet": wallet_address,
            "network": network,
            "fund_type": fund_type,
            "payout_tx_hash": tx_hash,
            "status": "completed" if not tx_hash.startswith("error") else "failed"
        }
        
        save_transaction(transaction_data)
        
        # Return response to card terminal
        response = {
            "status": "success" if not tx_hash.startswith("error") else "failed",
            "transaction_id": transaction_id,
            "payout_tx_hash": tx_hash,
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        return jsonify(response), 200
        
    except Exception as e:
        log_system_error(e, {"context": "settlement_webhook"})
        return jsonify({"error": "Internal server error"}), 500

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form.get('username')
        passwd = request.form.get('password')
        if user == USERNAME and check_password(passwd):
            session['logged_in'] = True
            session['username'] = user
            flash('Login successful! Welcome to the terminal.')
            return redirect(url_for('home'))
        flash("Invalid credentials.")
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        user = request.form.get('username')
        if user == USERNAME:
            send_otp(user)
            session['otp_sent'] = True
            return redirect(url_for('reset_password'))
        flash("Username not found.")
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if 'otp_sent' not in session:
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        otp = request.form.get('otp')
        new_pass = request.form.get('new_password')
        if verify_otp(USERNAME, otp):
            set_password(new_pass)
            flash("Password reset successfully. Please login.")
            return redirect(url_for('login'))
        else:
            flash("Invalid OTP.")
    return render_template('reset_password.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/process', methods=['POST'])
@limiter.limit("30 per minute")
@login_required
def process_card_transaction():
    """Production M0/M1 card processing with real ISO8583 and crypto payouts"""
    try:
        # Log transaction start
        log_transaction_start(getattr(g, 'request_id', 'unknown'))
        
        # Get form data
        card_number = request.form.get('card_number', '').replace(' ', '')
        expiry_date = request.form.get('expiry_date', '')
        cvv = request.form.get('cvv', '')
        amount = float(request.form.get('amount', 0))
        currency = request.form.get('currency', 'USD')
        protocol = request.form.get('protocol', '101.1')
        merchant_id = request.form.get('merchant_id', '')
        auth_code = request.form.get('auth_code', '')
        merchant_wallet_id = request.form.get('merchant_wallet', '')
        
        # Validate merchant wallet
        if merchant_wallet_id not in MERCHANT_WALLETS:
            return jsonify({'success': False, 'error': 'Invalid merchant wallet selected'})
        
        wallet_info = MERCHANT_WALLETS[merchant_wallet_id]
        payout_address = wallet_info['address']
        network = wallet_info['network']
        
        # Validate input data
        if not card_number or len(card_number) < 13:
            return jsonify({'success': False, 'error': 'Invalid card number'})
        
        if not expiry_date or len(expiry_date) != 5:
            return jsonify({'success': False, 'error': 'Invalid expiry date (MM/YY format required)'})
        
        if not cvv or len(cvv) < 3:
            return jsonify({'success': False, 'error': 'Invalid CVV/CVC'})
        
        # Authorization code validation based on protocol
        if protocol == '101.1' and (not auth_code or len(auth_code) != 4):
            return jsonify({'success': False, 'error': 'Protocol 101.1 requires 4-digit authorization code'})
        elif protocol == '201.3' and (not auth_code or len(auth_code) != 6):
            return jsonify({'success': False, 'error': 'Protocol 201.3 requires 6-digit authorization code'})
        elif not auth_code or len(auth_code) < 4:
            return jsonify({'success': False, 'error': 'Authorization code required (4 or 6 digits)'})
        
        if amount <= 0 or amount > config.MAX_TRANSACTION_AMOUNT:
            return jsonify({'success': False, 'error': f'Amount must be between $0.01 and ${config.MAX_TRANSACTION_AMOUNT:,.2f}'})
        
        # Calculate fees
        infrastructure_fee = amount * (config.CONVERSION_FEE_PERCENT / 100)
        net_amount = amount - infrastructure_fee
        
        # Generate transaction ID
        transaction_id = f'TXN{int(time.time())}{hash(card_number)}'[-8:]
        
        # Process ISO8583 request
        iso_response = send_iso8583_request(card_number, amount, merchant_id, auth_code, protocol)
        
        if iso_response and iso_response.get("field_39") == "00":
            # ISO8583 approved - process crypto payout
            try:
                tx_hash = process_crypto_payout(
                    payout_address, net_amount, network, wallet_info['token']
                )
                
                # Success - create transaction data
                result_data = {
                    'status': 'success',
                    'transaction_id': transaction_id,
                    'card_last4': card_number[-4:],
                    'amount': amount,
                    'currency': currency,
                    'protocol': protocol,
                    'auth_code': auth_code,
                    'infrastructure_fee': infrastructure_fee,
                    'net_amount': net_amount,
                    'network': network,
                    'payout_address': payout_address,
                    'crypto_hash': tx_hash,
                    'processing_time': f'{int((time.time() - g.start_time) * 1000)}ms',
                    'timestamp': time.time(),
                    'iso_response': iso_response
                }
                
                # Save transaction
                save_transaction({
                    "txn_id": transaction_id,
                    "arn": iso_response.get("arn"),
                    "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "card_type": iso_response.get("card_type", "M0/M1"),
                    "pan": card_number[-4:],
                    "amount": amount,
                    "currency": currency,
                    "payout": wallet_info['label'],
                    "wallet": payout_address,
                    "auth_code": auth_code,
                    "protocol": protocol,
                    "field39": iso_response.get("field_39"),
                    "payout_tx_hash": tx_hash,
                    "infrastructure_fee": infrastructure_fee,
                    "net_amount": net_amount
                })
                
            except Exception as crypto_error:
                log_system_error(crypto_error, {"context": "crypto_payout", "transaction_id": transaction_id})
                result_data = {
                    'status': 'failed',
                    'transaction_id': transaction_id,
                    'card_last4': card_number[-4:],
                    'amount': amount,
                    'currency': currency,
                    'protocol': protocol,
                    'auth_code': auth_code,
                    'infrastructure_fee': infrastructure_fee,
                    'net_amount': net_amount,
                    'error_message': 'Card approved but crypto payout failed. Contact support.',
                    'processing_time': f'{int((time.time() - g.start_time) * 1000)}ms',
                    'timestamp': time.time()
                }
        else:
            # ISO8583 declined
            decline_reason = iso_response.get('field_39', 'Unknown') if iso_response else 'Communication error'
            result_data = {
                'status': 'failed',
                'transaction_id': transaction_id,
                'card_last4': card_number[-4:],
                'amount': amount,
                'currency': currency,
                'protocol': protocol,
                'auth_code': auth_code,
                'infrastructure_fee': infrastructure_fee,
                'net_amount': net_amount,
                'error_message': f'Card declined: {decline_reason}',
                'processing_time': f'{int((time.time() - g.start_time) * 1000)}ms',
                'timestamp': time.time()
            }
        
        # Store transaction result for the results page
        session['last_transaction'] = result_data
        
        return jsonify({
            'success': True,
            'redirect': f'/transaction-result/{transaction_id}'
        })
        
    except Exception as e:
        log_system_error(e, {"context": "card_processing", "request_id": getattr(g, 'request_id', 'unknown')})
        return jsonify({'success': False, 'error': 'System error. Please try again.'})

@app.route('/transaction-result/<transaction_id>')
@login_required
def transaction_result(transaction_id):
    """Transaction result page"""
    result_data = session.get('last_transaction')
    if result_data and result_data['transaction_id'] == transaction_id:
        return render_template('transaction_result.html', result_data=result_data)
    else:
        flash('Invalid transaction ID or result not found.')
        return redirect(url_for('home'))

@app.route('/history')
@login_required
def history():
    transactions = load_transactions()
    return render_template('history.html', transactions=transactions)

# Production startup and cleanup
@app.before_first_request
def initialize_app():
    """Initialize application on first request"""
    try:
        # Create necessary directories
        os.makedirs('data', exist_ok=True)
        os.makedirs('logs', exist_ok=True)
        
        # Initialize crypto processor
        from crypto_utils import get_crypto_processor
        crypto_processor = get_crypto_processor()
        
        # Log startup
        payment_logger.logger.info(
            "card_terminal_startup",
            version="1.0.0",
            environment=config.FLASK_ENV,
            crypto_networks=["TRON", "ETH"],
            supported_protocols=list(PROTOCOLS.keys())
        )
        
    except Exception as e:
        log_system_error(e, {"context": "app_initialization"})

@app.teardown_appcontext
def cleanup_request(error):
    """Cleanup after each request"""
    if error:
        log_system_error(error, {"context": "request_teardown"})

if __name__ == '__main__':
    # Development server (production uses gunicorn)
    app.run(
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 10000)),
        debug=config.DEBUG,
        threaded=True
    )
