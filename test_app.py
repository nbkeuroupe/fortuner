# test_app.py - Minimal version for local testing
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import os
import json
from functools import wraps
from crypto_testnet import CryptoTestnetPayout

app = Flask(__name__)
app.secret_key = 'test-secret-key'

# Login credentials (for testing)
USERNAME = "blackrock"
PASSWORD = "terminal123"

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please login to access the terminal.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Test configuration
MAX_TRANSACTION_AMOUNT = 10000000.00
CONVERSION_FEE_PERCENT = 2.5

# Embedded merchant wallets (in production, these would be in secure config)
MERCHANT_WALLETS = {
    'trc20': {
        'address': 'TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE',
        'network': 'TRON',
        'label': 'TRON (TRC-20) - Lower fees'
    },
    'erc20': {
        'address': '0x742d35Cc6634C0532925a3b8D0C9f2b8b8b8b8b8',
        'network': 'ETHEREUM',
        'label': 'Ethereum (ERC-20) - Higher fees'
    }
}

# Mock data for testing
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

WALLET_LABELS = {
    "usdt_trc20": "USDT TRC-20 (TRON Network)",
    "usdt_erc20": "USDT ERC-20 (Ethereum Network)"
}

WALLETS = {
    "usdt_trc20": {
        "address": "TTest123...",
        "network": "TRON",
        "token": "USDT"
    },
    "usdt_erc20": {
        "address": "0xTest123...",
        "network": "ETH", 
        "token": "USDT"
    }
}

@app.route('/')
def home():
    """Redirect to login or terminal"""
    if 'logged_in' in session:
        return redirect(url_for('terminal'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login dashboard"""
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if username == USERNAME and password == PASSWORD:
            session['logged_in'] = True
            session['username'] = username
            flash('Login successful! Welcome to the terminal.')
            return redirect(url_for('terminal'))
        else:
            flash('Invalid credentials. Please try again.')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Logout and clear session"""
    session.clear()
    flash('You have been logged out successfully.')
    return redirect(url_for('login'))

@app.route('/terminal')
@login_required
def terminal():
    """Main card terminal interface"""
    return render_template('terminal.html', 
                         protocols=PROTOCOLS, 
                         wallets=WALLETS, 
                         wallet_labels=WALLET_LABELS,
                         max_amount=MAX_TRANSACTION_AMOUNT)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "version": "1.0.0-test",
        "max_amount": MAX_TRANSACTION_AMOUNT,
        "fee_percent": CONVERSION_FEE_PERCENT
    })

@app.route('/process', methods=['POST'])
@login_required
def process_card_transaction():
    """Mock card processing for testing"""
    try:
        print(f"[DEBUG] Form data received: {dict(request.form)}")
        # Get form data
        card_number = request.form.get('card_number', '').replace(' ', '')
        expiry_date = request.form.get('expiry_date', '')
        cvv = request.form.get('cvv', '')
        amount = float(request.form.get('amount', 0))
        currency = request.form.get('currency', 'USD')
        protocol = request.form.get('protocol', '101.1')
        auth_code = request.form.get('auth_code', '')
        merchant_wallet_id = request.form.get('merchant_wallet', '')
        
        # Get merchant wallet details
        if merchant_wallet_id not in MERCHANT_WALLETS:
            return jsonify({'success': False, 'error': 'Invalid merchant wallet selected'})
        
        wallet_info = MERCHANT_WALLETS[merchant_wallet_id]
        payout_address = wallet_info['address']
        network = wallet_info['network']
        
        # Basic validation
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
        
        if amount <= 0 or amount > MAX_TRANSACTION_AMOUNT:
            return jsonify({'success': False, 'error': f'Amount must be between $0.01 and ${MAX_TRANSACTION_AMOUNT:,.2f}'})
        
        # Calculate fees (mock)
        infrastructure_fee = amount * (CONVERSION_FEE_PERCENT / 100)
        merchant_amount = amount - infrastructure_fee
        
        # Generate transaction ID
        import time
        transaction_id = f'TXN{int(time.time())}{hash(card_number)}'[-8:]
        
        # Real testnet crypto payout processing
        print(f"🧪 Processing testnet transaction: {transaction_id}")
        
        # Initialize testnet payout
        crypto_payout = CryptoTestnetPayout()
        
        # Mock ISO8583 approval (75% success rate)
        import random
        iso_approved = random.choice([True, True, True, False])
        
        if iso_approved:
            # Process real testnet crypto payout
            payout_result = crypto_payout.process_testnet_payout(
                network=network,
                to_address=payout_address,
                amount_usdt=merchant_amount
            )
            
            if payout_result['success']:
                # Successful testnet transaction
                result_data = {
                    'status': 'success',
                    'transaction_id': transaction_id,
                    'card_last4': card_number[-4:],
                    'amount': amount,
                    'currency': currency,
                    'protocol': protocol,
                    'auth_code': auth_code,
                    'infrastructure_fee': infrastructure_fee,
                    'net_amount': merchant_amount,
                    'network': payout_result['network'],
                    'payout_address': payout_address,
                    'crypto_hash': payout_result['tx_hash'],
                    'explorer_url': payout_result.get('explorer_url', ''),
                    'testnet': True,
                    'mock': payout_result.get('mock', False),
                    'processing_time': f'{random.randint(2, 8)} seconds',
                    'timestamp': time.time()
                }
                print(f"✅ Testnet payout successful: {payout_result['tx_hash']}")
            else:
                # Crypto payout failed
                result_data = {
                    'status': 'failed',
                    'transaction_id': transaction_id,
                    'card_last4': card_number[-4:],
                    'amount': amount,
                    'currency': currency,
                    'protocol': protocol,
                    'auth_code': auth_code,
                    'infrastructure_fee': infrastructure_fee,
                    'net_amount': merchant_amount,
                    'error_message': f"Card approved but crypto payout failed: {payout_result.get('error', 'Unknown error')}",
                    'processing_time': f'{random.randint(1, 3)} seconds',
                    'timestamp': time.time()
                }
                print(f"❌ Testnet payout failed: {payout_result.get('error')}")
        else:
            # Mock failed transaction
            result_data = {
                'status': 'failed',
                'transaction_id': transaction_id,
                'card_last4': card_number[-4:],
                'amount': amount,
                'currency': currency,
                'protocol': protocol,
                'auth_code': auth_code,
                'infrastructure_fee': infrastructure_fee,
                'net_amount': merchant_amount,
                'error_message': random.choice([
                    'Insufficient funds on M0/M1 card',
                    'Invalid authorization code from issuer',
                    'Card expired or blocked',
                    'ISO8583 communication timeout'
                ]),
                'processing_time': f'{random.randint(1, 3)} seconds',
                'timestamp': time.time()
            }
        
        # Store transaction result for the results page
        session['last_transaction'] = result_data
        
        response_data = {
            'success': True,
            'redirect': f'/transaction-result/{transaction_id}'
        }
        print(f"[DEBUG] Sending response: {response_data}")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({"status": "error", "error": str(e)})

@app.route('/transaction-result/<transaction_id>')
@login_required
def transaction_result(transaction_id):
    """Transaction result page"""
    result_data = session.get('last_transaction')
    if result_data and result_data['transaction_id'] == transaction_id:
        return render_template('transaction_result.html', result_data=result_data)
    else:
        flash('Invalid transaction ID or result not found.')
        return redirect(url_for('terminal'))

if __name__ == '__main__':
    print("🧪 Starting Card Terminal Test Server...")
    print(f"💰 Max Transaction: ${MAX_TRANSACTION_AMOUNT:,.2f}")
    print(f"💸 Infrastructure Fee: {CONVERSION_FEE_PERCENT}%")
    print("🌐 Open: http://localhost:5000")
    
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=True
    )
