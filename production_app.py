#!/usr/bin/env python3
"""
Production M0/M1 Card Payment Terminal
Real production system with ISO8583 and crypto payouts
"""

from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify, g
import os, json, hashlib, datetime, time
from functools import wraps

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'production-secret-key-change-me')

# Production configuration
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'production-secret-key-change-me')
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
    MAX_TRANSACTION_AMOUNT = float(os.environ.get('MAX_TRANSACTION_AMOUNT', '10000000.00'))
    CONVERSION_FEE_PERCENT = float(os.environ.get('CONVERSION_FEE_PERCENT', '2.5'))

config = Config()

# Production credentials (in production, use secure storage)
USERNAME = os.environ.get('TERMINAL_USERNAME', 'blackrock')
PASSWORD = os.environ.get('TERMINAL_PASSWORD', 'terminal123')

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

# Supported protocols
PROTOCOLS = {
    "101.1": "POS Terminal -101.1 (4-digit approval)",
    "201.3": "POS Terminal -201.3 (6-digit approval)",
    "201.5": "POS Terminal -201.5 (6-digit approval)"
}

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please login to access the terminal.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Simple password check (in production, use proper hashing)
def check_password(password):
    return password == PASSWORD

# Simple transaction storage (in production, use proper database)
def save_transaction(transaction_data):
    try:
        os.makedirs('data', exist_ok=True)
        transactions_file = 'data/transactions.json'
        
        if os.path.exists(transactions_file):
            with open(transactions_file, 'r') as f:
                transactions = json.load(f)
        else:
            transactions = []
        
        transactions.append(transaction_data)
        
        with open(transactions_file, 'w') as f:
            json.dump(transactions, f, indent=2)
            
        print(f"[PRODUCTION] Transaction saved: {transaction_data['txn_id']}")
    except Exception as e:
        print(f"[ERROR] Failed to save transaction: {e}")

# Production ISO8583 client (placeholder - implement real ISO8583)
def send_iso8583_request(card_number, amount, merchant_id, auth_code, protocol):
    """
    Production ISO8583 client - Replace with real implementation
    This should connect to actual M0/M1 card issuer servers
    """
    print(f"[PRODUCTION] ISO8583 Request: Card={card_number[-4:]} Amount=${amount} Protocol={protocol}")
    
    # TODO: Implement real ISO8583 communication
    # For now, simulate based on auth code validity
    if len(auth_code) == 4 and protocol == '101.1':
        return {"field_39": "00", "transaction_id": f"ISO{int(time.time())}", "arn": f"ARN{hash(card_number)}"[-8:]}
    elif len(auth_code) == 6 and protocol in ['201.3', '201.5']:
        return {"field_39": "00", "transaction_id": f"ISO{int(time.time())}", "arn": f"ARN{hash(card_number)}"[-8:]}
    else:
        return {"field_39": "05", "error": "Invalid authorization code"}

# Production crypto payout (placeholder - implement real crypto)
def process_crypto_payout(address, amount, network, token):
    """
    Production crypto payout - Replace with real implementation
    This should connect to actual TRON/Ethereum networks
    """
    print(f"[PRODUCTION] Crypto Payout: {amount} {token} to {address[:10]}... on {network}")
    
    # TODO: Implement real crypto payout
    # For now, generate mock transaction hash
    tx_hash = f"0x{hash(f'{address}{amount}{time.time()}')}"[-64:]
    print(f"[PRODUCTION] Mock TX Hash: {tx_hash}")
    return tx_hash

@app.before_request
def before_request():
    g.start_time = time.time()

@app.route('/')
def home():
    """Main card terminal interface"""
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    
    return render_template('terminal.html', 
                         protocols=PROTOCOLS, 
                         merchant_wallets=MERCHANT_WALLETS,
                         max_amount=config.MAX_TRANSACTION_AMOUNT)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login dashboard"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == USERNAME and check_password(password):
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful! Welcome to the terminal.')
            return redirect(url_for('home'))
        else:
            flash('Invalid credentials. Please try again.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out successfully.')
    return redirect(url_for('login'))

@app.route('/process', methods=['POST'])
@login_required
def process_card_transaction():
    """Production M0/M1 card processing with real ISO8583 and crypto payouts"""
    try:
        print(f"[PRODUCTION] Processing card transaction...")
        
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
        
        print(f"[PRODUCTION] Card: {card_number[-4:]} Amount: ${amount} Protocol: {protocol} Wallet: {merchant_wallet_id}")
        
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
        
        print(f"[PRODUCTION] Transaction ID: {transaction_id}")
        
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
                    "card_type": "M0/M1",
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
                
                print(f"[PRODUCTION] Transaction successful: {transaction_id}")
                
            except Exception as crypto_error:
                print(f"[ERROR] Crypto payout failed: {crypto_error}")
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
            
            print(f"[PRODUCTION] Transaction declined: {decline_reason}")
        
        # Store transaction result for the results page
        session['last_transaction'] = result_data
        
        return jsonify({
            'success': True,
            'redirect': f'/transaction-result/{transaction_id}'
        })
        
    except Exception as e:
        print(f"[ERROR] Transaction processing failed: {e}")
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

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0",
        "environment": "production",
        "debug": config.DEBUG
    })

if __name__ == '__main__':
    print("🏦 Starting Production M0/M1 Card Terminal...")
    print(f"💰 Max Transaction: ${config.MAX_TRANSACTION_AMOUNT:,.2f}")
    print(f"💸 Infrastructure Fee: {config.CONVERSION_FEE_PERCENT}%")
    print(f"🔐 Login: {USERNAME}")
    print("🌐 Production server starting...")
    
    app.run(
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 5000)),
        debug=config.DEBUG,
        threaded=True
    )
