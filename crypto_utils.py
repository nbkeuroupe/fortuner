import json
import os
import threading
from tronpy import Tron
from tronpy.keys import PrivateKey
from tronpy import TronError
from web3 import Web3, exceptions
from web3.middleware import geth_poa_middleware # For POA networks if needed

# --- Configuration Constants ---
# It is recommended to use environment variables for sensitive data.
# e.g., os.environ.get('TRON_USDT_CONTRACT_ADDRESS')
TRON_USDT_CONTRACT_ADDRESS = 'TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf'
ETHEREUM_USDT_CONTRACT_ADDRESS = '0xdAC17F958D2ee523a2206206994597C13D831ec7'

# A minimal ERC20 ABI with transfer and decimals.
ERC20_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "_to", "type": "address"},
            {"name": "_value", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "type": "function"
    }
]

# --- Wallet and Client Setup ---
# Load wallets configuration
wallets_file = os.path.join(os.path.dirname(__file__), 'wallets.json')
WALLETS = {}
if os.path.exists(wallets_file):
    try:
        with open(wallets_file, 'r') as f:
            WALLETS = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        print(f"[ERROR] Failed to load wallets.json: {e}")
        WALLETS = {}

# Rotation tracker (in-memory, needs to be thread-safe)
rotation_counters = {}
rotation_lock = threading.Lock()

# TRON client
tron_client = Tron()

# Ethereum client
# IMPORTANT: Replace YOUR_INFURA_PROJECT_ID with your actual key.
# This is a critical step for the code to function correctly.
eth_web3 = Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/6aaea4c2d2be42bf89c660d07863fea5"))


# --- Helper Functions ---
def get_next_wallet(network, token):
    """
    Thread-safe round-robin wallet selector.
    """
    with rotation_lock:
        try:
            wallets = WALLETS[network][token]
            key = f"{network}_{token}"
            if key not in rotation_counters:
                rotation_counters[key] = 0
            wallet = wallets[rotation_counters[key] % len(wallets)]
            rotation_counters[key] += 1
            return wallet
        except KeyError:
            return None


def send_tron_usdt_payout(to_address, amount):
    """
    Send TRC20 USDT.
    """
    wallet = get_next_wallet("TRON", "USDT")
    if wallet is None:
        return {"success": False, "error": "No TRON USDT wallets configured."}

    # The original error occurred here. The `bytes.fromhex()` function
    # will fail if `wallet["private_key"]` contains any non-hexadecimal characters.
    try:
        priv_key = PrivateKey(bytes.fromhex(wallet["private_key"]))
    except ValueError as e:
        return {"success": False, "error": f"Payout failed: Invalid TRON private key: {e}"}

    try:
        contract = tron_client.get_contract(TRON_USDT_CONTRACT_ADDRESS)
        # TronPy expects values in the smallest unit (6 decimals for USDT)
        value = int(amount * 1_000_000)
        
        # Build the transaction
        txn = (
            contract.functions.transfer(to_address, value)
            .with_owner(wallet["address"])
            .build()
        )
        
        # Sign and broadcast the transaction
        signed_txn = txn.sign(priv_key)
        result = signed_txn.broadcast().wait()
        
        if result and result.get("receipt", {}).get("result") == "SUCCESS":
            return {"success": True, "txid": signed_txn.txid}
        else:
            return {"success": False, "error": f"Transaction failed on-chain: {result}"}
    except TronError as e:
        return {"success": False, "error": f"TRON network error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected TRON payout error: {e}"}


def send_erc20_usdt_payout(to_address, amount):
    """
    Send ERC20 USDT.
    """
    wallet = get_next_wallet("ETHEREUM", "USDT")
    if wallet is None:
        return {"success": False, "error": "No Ethereum USDT wallets configured."}

    try:
        # Check if connected to Ethereum network
        if not eth_web3.is_connected():
            return {"success": False, "error": "Not connected to Ethereum node."}
        
        contract = eth_web3.eth.contract(
            address=Web3.to_checksum_address(ETHEREUM_USDT_CONTRACT_ADDRESS),
            abi=ERC20_ABI
        )

        nonce = eth_web3.eth.get_transaction_count(wallet["address"])
        
        # Get current gas price to avoid using a fixed value
        gas_price = eth_web3.eth.gas_price
        
        # Build transaction
        txn = contract.functions.transfer(
            Web3.to_checksum_address(to_address),
            int(amount * 10**6)  # USDT has 6 decimals
        ).build_transaction({
            "chainId": 1,
            "gas": 100000, # This can be estimated more accurately
            "gasPrice": gas_price,
            "nonce": nonce
        })

        signed_txn = eth_web3.eth.account.sign_transaction(txn, private_key=wallet["private_key"])
        tx_hash = eth_web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        
        return {"success": True, "txid": tx_hash.hex()}

    except exceptions.InvalidAddress as e:
        return {"success": False, "error": f"Ethereum payout error: Invalid wallet or destination address: {e}"}
    except exceptions.TimeExhausted as e:
        return {"success": False, "error": f"Ethereum network timeout error: {e}"}
    except Exception as e:
        return {"success": False, "error": f"Unexpected Ethereum payout error: {e}"}


def process_crypto_payout(network, token, to_address, amount):
    """
    Unified payout dispatcher
    """
    if network == "TRON" and token == "USDT":
        return send_tron_usdt_payout(to_address, amount)
    elif network == "ETH" and token == "USDT":
        return send_erc20_usdt_payout(to_address, amount)
    else:
        return {
            "success": False,
            "error": f"Payout failed: Unsupported network/token combination: {network} - {token}"
        }


# --- Class-based Processor (Example) ---
class CryptoPaymentProcessor:
    def process_payout(self, network, token, to_address, amount):
        return process_crypto_payout(network, token, to_address, amount)

# Singleton instance
_crypto_processor = None
_processor_lock = threading.Lock()

def get_crypto_processor():
    global _crypto_processor
    with _processor_lock:
        if _crypto_processor is None:
            _crypto_processor = CryptoPaymentProcessor()
    return _crypto_processor
