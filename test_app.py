from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
from functools import wraps
import os, time, random
from dotenv import load_dotenv
from crypto_utils import process_crypto_payout

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "production-secret")

USERNAME = os.getenv("APP_USERNAME", "blackrock")
PASSWORD = os.getenv("APP_PASSWORD", "terminal123")
USE_MAINNET = os.getenv("USE_MAINNET", "true").lower() == "true"

MAX_TRANSACTION_AMOUNT = 10000000.00
CONVERSION_FEE_PERCENT = 2.5

MERCHANT_WALLETS = {
    'trc20': {
        'address': os.getenv('TRC20_MAINNET_WALLET', ''),
        'network': 'TRON',
        'token': 'USDT',
        'label': 'TRON (TRC-20)'
    },
    'erc20': {
        'address': os.getenv('ERC20_MAINNET_WALLET', ''),
        'network': 'ETH',
        'token': 'USDT',
        'label': 'Ethereum (ERC-20)'
    }
}

PROTOCOLS = {
    "POS Terminal -101.1 (4-digit approval)": 4,
    "POS Terminal -201.3 (6-digit approval)": 6,
}

WALLET_LABELS = {
    "usdt_trc20": "USDT TRC-20 (TRON)",
    "usdt_erc20": "USDT ERC-20 (Ethereum)"
}

WALLETS = {
    "usdt_trc20": {
        "address": os.getenv("TRC20_MAINNET_WALLET", ""),
        "network": "TRON",
        "token": "USDT"
    },
    "usdt_erc20": {
        "address": os.getenv("ERC20_MAINNET_WALLET", ""),
        "network": "ETH",
        "token": "USDT"
    }
}

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            flash('Please login first.')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return redirect(url_for('terminal') if 'logged_in' in session else url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == USERNAME and request.form.get('password') == PASSWORD:
            session['logged_in'] = True
            session['username'] = USERNAME
            flash('Logged in.')
            return redirect(url_for('terminal'))
        flash('Invalid credentials.')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.')
    return redirect(url_for('login'))

@app.route('/terminal')
@login_required
def terminal():
    return render_template('terminal.html', 
                           protocols=PROTOCOLS, 
                           wallets=WALLETS, 
                           wallet_labels=WALLET_LABELS,
                           max_amount=MAX_TRANSACTION_AMOUNT)

@app.route('/process', methods=['POST'])
@login_required
def process_card_transaction():
    try:
        data = request.form
        amount = float(data.get('amount', 0))
        card_number = data.get('card_number', '').replace(' ', '')
        expiry_date = data.get('expiry_date', '')
        cvv = data.get('cvv', '')
        currency = data.get('currency', 'USD')
        auth_code = data.get('auth_code', '')
        protocol = data.get('protocol', '')
        merchant_wallet_id = data.get('merchant_wallet', '')

        if merchant_wallet_id not in MERCHANT_WALLETS:
            return jsonify({'success': False, 'error': 'Invalid merchant wallet'})

        if not card_number or len(card_number) < 13:
            return jsonify({'success': False, 'error': 'Invalid card number'})
        if not expiry_date or len(expiry_date) != 5:
            return jsonify({'success': False, 'error': 'Invalid expiry date'})
        if not cvv or len(cvv) < 3:
            return jsonify({'success': False, 'error': 'Invalid CVV'})
        if protocol == '101.1' and len(auth_code) != 4:
            return jsonify({'success': False, 'error': 'Protocol 101.1 requires 4-digit code'})
        if protocol == '201.3' and len(auth_code) != 6:
            return jsonify({'success': False, 'error': 'Protocol 201.3 requires 6-digit code'})
        if amount <= 0 or amount > MAX_TRANSACTION_AMOUNT:
            return jsonify({'success': False, 'error': f'Amount must be between $0.01 and ${MAX_TRANSACTION_AMOUNT:,.2f}'})

        transaction_id = f'TXN{int(time.time())}{abs(hash(card_number))}'[-8:]
        infrastructure_fee = amount * (CONVERSION_FEE_PERCENT / 100)
        merchant_amount = round(amount - infrastructure_fee, 2)

        wallet = MERCHANT_WALLETS[merchant_wallet_id]

        result = process_crypto_payout(
            network=wallet['network'],
            token=wallet['token'],
            to_address=wallet['address'],
            amount=merchant_amount
        )

        if not result['success']:
            return jsonify({'success': False, 'error': f"Payout failed: {result.get('error', 'Unknown')}"})

        session['last_transaction'] = {
            'status': 'success',
            'transaction_id': transaction_id,
            'card_last4': card_number[-4:],
            'amount': amount,
            'currency': currency,
            'protocol': protocol,
            'auth_code': auth_code,
            'infrastructure_fee': infrastructure_fee,
            'net_amount': merchant_amount,
            'network': wallet['network'],
            'payout_address': wallet['address'],
            'crypto_hash': result['tx_hash'],
            'explorer_url': result.get('explorer_url'),
            'testnet': not USE_MAINNET,
            'processing_time': f'{random.randint(2, 8)} seconds',
            'timestamp': time.time()
        }

        return jsonify({'success': True, 'redirect': url_for('transaction_result', transaction_id=transaction_id)})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/transaction-result/<transaction_id>')
@login_required
def transaction_result(transaction_id):
    result_data = session.get('last_transaction')
    if result_data and result_data['transaction_id'] == transaction_id:
        return render_template('transaction_result.html', result_data=result_data)
    flash("Transaction not found.")
    return redirect(url_for('terminal'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
