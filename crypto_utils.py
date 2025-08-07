import json
import os
import threading
from decimal import Decimal
from web3 import Web3
from tronpy import Tron
from tronpy.keys import PrivateKey
from dotenv import load_dotenv

load_dotenv()

# Load wallets
with open("wallets.json") as f:
    WALLETS = json.load(f)

# Ethereum mainnet setup
INFURA_URL = os.getenv("INFURA_MAINNET_URL")  # e.g., https://mainnet.infura.io/v3/YOUR_PROJECT_ID
w3 = Web3(Web3.HTTPProvider(INFURA_URL))

# TRON client setup
tron = Tron()

# ERC20 Token ABI (simplified)
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    }
]

def send_erc20_token(to_address, amount, private_key, contract_address):
    try:
        account = w3.eth.account.from_key(private_key)
        contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=ERC20_ABI)
        decimals = contract.functions.decimals().call()
        token_amount = int(Decimal(amount) * (10 ** decimals))

        nonce = w3.eth.get_transaction_count(account.address)
        txn = contract.functions.transfer(
            Web3.to_checksum_address(to_address),
            token_amount
        ).build_transaction({
            'chainId': 1,  # Ethereum Mainnet
            'gas': 100000,
            'gasPrice': w3.eth.gas_price,
            'nonce': nonce,
        })

        signed_txn = w3.eth.account.sign_transaction(txn, private_key=private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return tx_hash.hex()

    except Exception as e:
        raise Exception(f"ERC20 Transfer Error: {str(e)}")

def send_trc20_token(to_address, amount, private_key_hex, contract_address):
    try:
        priv_key = PrivateKey(bytes.fromhex(private_key_hex))
        contract = tron.get_contract(contract_address)
        decimals = contract.functions.decimals()
        token_amount = int(Decimal(amount) * (10 ** decimals))

        txn = (
            contract.functions.transfer(to_address, token_amount)
            .with_owner(priv_key.public_key.to_base58check_address())
            .fee_limit(1_000_000)
            .build()
            .sign(priv_key)
        )
        result = txn.broadcast().wait()
        return result["id"]

    except Exception as e:
        raise Exception(f"TRC20 Transfer Error: {str(e)}")

def rotate_wallet(network, token_type):
    rotation_pool = WALLETS.get(network, {}).get(token_type, [])
    if not rotation_pool:
        raise Exception(f"No wallets configured for {network} - {token_type}")
    
    current = rotation_pool.pop(0)
    rotation_pool.append(current)
    WALLETS[network][token_type] = rotation_pool
    
    with open("wallets.json", "w") as f:
        json.dump(WALLETS, f, indent=2)
    
    return current

def log_crypto_payout_failure(error, to_address, amount, network):
    # Placeholder: Replace with logging or database recording as needed
    print(f"[ERROR] Payout failed: {error} | To: {to_address} | Amt: {amount} | Network: {network}")

def process_crypto_payout(to_address, amount, network, token_type):
    try:
        wallet = rotate_wallet(network, token_type)
        private_key = wallet["private_key"]
        contract_address = wallet["contract_address"]

        if network == "ethereum" and token_type == "usdt":
            tx_hash = send_erc20_token(to_address, amount, private_key, contract_address)
        elif network == "tron" and token_type == "usdt":
            tx_hash = send_trc20_token(to_address, amount, private_key, contract_address)
        else:
            raise Exception(f"Unsupported payout type: {network} - {token_type}")

        return {
            "success": True,
            "tx_hash": tx_hash
        }

    except Exception as e:
        log_crypto_payout_failure(e, to_address, amount, network)
        return {
            "success": False,
            "error": str(e)
        }

# Optional Singleton Processor
class CryptoPaymentProcessor:
    def process_payout(self, to_address, amount, network, token_type, fund_type="M0"):
        return process_crypto_payout(to_address, amount, network, token_type)

_crypto_processor = None
_processor_lock = threading.Lock()

def get_crypto_processor():
    global _crypto_processor
    if _crypto_processor is None:
        with _processor_lock:
            if _crypto_processor is None:
                _crypto_processor = CryptoPaymentProcessor()
    return _crypto_processor
