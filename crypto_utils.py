import json
import os
from tronpy import Tron
from tronpy.keys import PrivateKey
from web3 import Web3
import threading

# Load wallets configuration
wallets_file = os.path.join(os.path.dirname(__file__), 'wallets.json')
if os.path.exists(wallets_file):
    with open(wallets_file, 'r') as f:
        WALLETS = json.load(f)
else:
    WALLETS = {}

# Rotation tracker (in-memory)
rotation_counters = {}

# TRON client
tron_client = Tron()

# Ethereum client
eth_web3 = Web3(Web3.HTTPProvider("https://mainnet.infura.io/v3/YOUR_INFURA_PROJECT_ID"))  # replace with your endpoint


def get_next_wallet(network, token):
    """
    Round-robin wallet selector
    """
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
    Send TRC20 USDT
    """
    wallet = get_next_wallet("TRON", "USDT")
    if wallet is None:
        return {"success": False, "error": "No TRON USDT wallets configured."}

    try:
        contract = tron_client.get_contract('TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf')  # USDT contract on TRON
        priv_key = PrivateKey(bytes.fromhex(wallet["private_key"]))
        txn = (
            contract.functions.transfer(to_address, int(amount * 1_000_000))
            .with_owner(wallet["address"])
            .build()
            .sign(priv_key)
            .broadcast()
        )
        result = txn.wait()
        if result["receipt"]["result"]:
            return {"success": True, "txid": txn.txid}
        else:
            return {"success": False, "error": "Transaction failed on-chain."}
    except Exception as e:
        return {"success": False, "error": f"TRON payout error: {str(e)}"}


def send_erc20_usdt_payout(to_address, amount):
    """
    Send ERC20 USDT
    """
    wallet = get_next_wallet("ETHEREUM", "USDT")
    if wallet is None:
        return {"success": False, "error": "No Ethereum USDT wallets configured."}

    try:
        contract = eth_web3.eth.contract(
            address=Web3.to_checksum_address("0xdAC17F958D2ee523a2206206994597C13D831ec7"),  # USDT ERC20 contract
            abi=[
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
        )

        nonce = eth_web3.eth.get_transaction_count(wallet["address"])
        txn = contract.functions.transfer(
            Web3.to_checksum_address(to_address),
            int(amount * 1_000_000)
        ).build_transaction({
            "chainId": 1,
            "gas": 100000,
            "gasPrice": eth_web3.to_wei("20", "gwei"),
            "nonce": nonce
        })

        signed_txn = eth_web3.eth.account.sign_transaction(txn, private_key=wallet["private_key"])
        tx_hash = eth_web3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return {"success": True, "txid": tx_hash.hex()}

    except Exception as e:
        return {"success": False, "error": f"Ethereum payout error: {str(e)}"}


def process_crypto_payout(network, token, to_address, amount):
    """
    Unified payout dispatcher
    """
    try:
        if network == "TRON" and token == "USDT":
            result = send_tron_usdt_payout(to_address, amount)
        elif network == "ETH" and token == "USDT":
            result = send_erc20_usdt_payout(to_address, amount)
        else:
            return {
                "success": False,
                "error": f"Payout failed: Unsupported network/token combination: {network} - {token}"
            }

        # The send_* functions should return a dict like {"success": True, "tx_hash": "..."}
        return result

    except Exception as e:
        log_crypto_payout_failure(e, to_address, amount, network)
        return {
            "success": False,
            "error": str(e)
        }

def log_crypto_payout_failure(exception, to_address, amount, network):
    """
    Log payout failures.
    """
    print(f"[ERROR] Crypto payout failed: {str(exception)} | Address: {to_address} | Amount: {amount} | Network: {network}")

def _ERC20_ABI():
    """
    Returns a minimal ERC20 ABI with transfer and decimals.
    """
    return [
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

# Optionally a class-based processor
class CryptoPaymentProcessor:
    def process_payout(self, to_address, amount, network, token_type, fund_type="M0"):
        return process_crypto_payout(to_address, amount, network, token_type)

# Singleton instance
_crypto_processor = None
_processor_lock = threading.Lock()

def get_crypto_processor():
    global _crypto_processor
    with _processor_lock:
        if _crypto_processor is None:
            _crypto_processor = CryptoPaymentProcessor()
    return _crypto_processor
