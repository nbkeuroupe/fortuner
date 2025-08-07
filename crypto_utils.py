import os
import json
import threading
import time
from tronpy import Tron
from tronpy.keys import PrivateKey
from web3 import Web3, exceptions
from web3.middleware import geth_poa_middleware # For POA networks if needed

# --- Configuration Constants ---
# These are the contract addresses for USDT on TRON (TRC20) and Ethereum (ERC20).
TRON_USDT_CONTRACT_ADDRESS = 'TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf'
ETHEREUM_USDT_CONTRACT_ADDRESS = '0xdAC17F958D2ee523a2206206994597C13D831ec7'

# A minimal ERC20 ABI with transfer and decimals for interacting with the contract.
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

# The TRC20 ABI is no longer required as tronpy fetches it automatically.


# --- Wallet and Client Setup ---
# This dictionary is populated from environment variables, which is a
# best practice for security and deployment.
WALLETS = {
    "TRON": {
        "USDT": [
            {
                "address": os.environ.get("TRON_MERCHANT_WALLET"),
                "private_key": os.environ.get("TRON_PRIVATE_KEY")
            }
        ]
    },
    "ETHEREUM": {
        "USDT": [
            {
                "address": os.environ.get("ETH_MERCHANT_WALLET"),
                "private_key": os.environ.get("ETH_PRIVATE_KEY")
            }
        ]
    }
}

rotation_counters = {}
rotation_lock = threading.Lock()

# TRON client
tron_client = Tron()

# Ethereum client - reads the INFURA_PROJECT_ID from environment variables
infura_project_id = os.environ.get("INFURA_PROJECT_ID")
if not infura_project_id:
    # Raise an error if a critical environment variable is missing.
    raise ValueError("INFURA_PROJECT_ID not found in environment variables.")

eth_web3 = Web3(Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{infura_project_id}"))

# --- Helper Functions ---
def get_next_wallet(network, token):
    """
    Thread-safe round-robin wallet selector.
    """
    with rotation_lock:
        try:
            wallets = WALLETS[network][token]
            # Ensure the wallet data from env vars is not None
            if not wallets[0]["address"] or not wallets[0]["private_key"]:
                return None
            
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
    Send TRC20 USDT with exponential backoff for rate-limiting.
    """
    wallet = get_next_wallet("TRON", "USDT")
    if wallet is None:
        return {"success": False, "error": "No TRON USDT wallets configured. Check environment variables."}

    try:
        priv_key = PrivateKey(bytes.fromhex(wallet["private_key"]))
    except ValueError as e:
        return {"success": False, "error": f"Payout failed: Invalid TRON private key: {e}"}

    retries = 3
    delay = 1 # initial delay in seconds
    for attempt in range(retries):
        try:
            # Check for network connection before attempting a transaction
            if not tron_client.is_connected():
                raise ConnectionError("Not connected to TRON network.")

            # The tronpy library handles fetching the ABI automatically
            contract = tron_client.get_contract(TRON_USDT_CONTRACT_ADDRESS)
            value = int(amount * 1_000_000)
            
            txn = (
                contract.functions.transfer(to_address, value)
                .with_owner(wallet["address"])
                .build()
            )
            
            signed_txn = txn.sign(priv_key)
            result = signed_txn.broadcast().wait()
            
            if result and result.get("receipt", {}).get("result") == "SUCCESS":
                return {"success": True, "txid": signed_txn.txid}
            else:
                return {"success": False, "error": f"Transaction failed on-chain: {result}"}
        except ConnectionError as e:
            # Retry on connection errors
            if attempt < retries - 1:
                print(f"TRON connection error. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2
            else:
                return {"success": False, "error": f"TRON payout error: {e}"}
        except Exception as e:
            # Check for rate-limiting error
            if "Too Many Requests" in str(e) and attempt < retries - 1:
                print(f"Rate limit hit. Retrying in {delay} seconds...")
                time.sleep(delay)
                delay *= 2  # Exponentially increase the delay
            else:
                return {"success": False, "error": f"TRON payout error: {e}"}
    
    return {"success": False, "error": "Maximum retries exceeded due to rate-limiting or connection issues."}


def send_erc20_usdt_payout(to_address, amount):
    """
    Send ERC20 USDT.
    """
    wallet = get_next_wallet("ETHEREUM", "USDT")
    if wallet is None:
        return {"success": False, "error": "No Ethereum USDT wallets configured. Check environment variables."}

    try:
        if not eth_web3.is_connected():
            return {"success": False, "error": "Not connected to Ethereum node."}
        
        contract = eth_web3.eth.contract(
            address=Web3.to_checksum_address(ETHEREUM_USDT_CONTRACT_ADDRESS),
            abi=ERC20_ABI
        )

        nonce = eth_web3.eth.get_transaction_count(wallet["address"])
        gas_price = eth_web3.eth.gas_price
        
        txn = contract.functions.transfer(
            Web3.to_checksum_address(to_address),
            int(amount * 10**6)
        ).build_transaction({
            "chainId": 1,
            "gas": 100000,
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

class CryptoPaymentProcessor:
    def process_payout(self, network, token, to_address, amount):
        return process_crypto_payout(network, token, to_address, amount)

_crypto_processor = None
_processor_lock = threading.Lock()

def get_crypto_processor():
    global _crypto_processor
    with _processor_lock:
        if _crypto_processor is None:
            _crypto_processor = CryptoPaymentProcessor()
    return _crypto_processor
