# crypto_utils.py

import os
import json
import random
import threading
from web3 import Web3
from tronpy import Tron
from tronpy.keys import PrivateKey

# Load wallets.json once
with open("wallets.json") as f:
    WALLETS_CONFIG = json.load(f)

# Lock for thread-safe rotation
_wallet_lock = threading.Lock()
_wallet_indexes = {}

def rotate_wallet(network, token_type):
    """
    Rotate wallets for round-robin payouts.
    """
    key = f"{network.lower()}_{token_type.lower()}"
    wallets = WALLETS_CONFIG.get(key)

    if not wallets or not isinstance(wallets, list) or not wallets:
        raise Exception(f"Payout failed: No wallets configured for {network.upper()} - {token_type.upper()}")

    with _wallet_lock:
        index = _wallet_indexes.get(key, 0)
        wallet = wallets[index % len(wallets)]
        _wallet_indexes[key] = index + 1

    # If you store sensitive private keys in environment vars:
    if wallet.get("private_key_env"):
        env_var = wallet["private_key_env"]
        wallet["private_key"] = os.environ.get(env_var)
        if not wallet["private_key"]:
            raise Exception(f"Missing environment variable: {env_var}")

    return wallet

def send_erc20_token(to_address, amount, private_key, contract_address):
    """
    Send ERC20 token (e.g., USDT) on Ethereum.
    """
    eth_node = os.environ.get("ETH_NODE_URL")
    if not eth_node:
        raise Exception("ETH_NODE_URL not set")
    web3 = Web3(Web3.HTTPProvider(eth_node))

    account = web3.eth.account.privateKeyToAccount(private_key)
    nonce = web3.eth.get_transaction_count(account.address)

    contract = web3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=_ERC20_ABI())
    decimals = contract.functions.decimals().call()
    amount_in_wei = int(amount * (10 ** decimals))

    txn = contract.functions.transfer(
        Web3.to_checksum_address(to_address),
        amount_in_wei
    ).build_transaction({
        'chainId': web3.eth.chain_id,
        'gas': 100000,
        'gasPrice': web3.eth.gas_price,
        'nonce': nonce
    })

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=private_key)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return web3.to_hex(tx_hash)

def send_trc20_token(to_address, amount, private_key, contract_address):
    """
    Send TRC20 token (e.g., USDT) on Tron.
    """
    tron = Tron()
    pk = PrivateKey(bytes.fromhex(private_key))
    from_addr = pk.public_key.to_base58check_address()

    contract = tron.get_contract(contract_address)
    decimals = contract.functions.decimals()
    amount_in_sun = int(amount * (10 ** decimals))

    txn = (
        contract.functions.transfer(to_address, amount_in_sun)
        .with_owner(from_addr)
        .fee_limit(5_000_000)
        .build()
        .sign(pk)
        .broadcast()
    )

    result = txn.wait()
    return result["id"]

def process_crypto_payout(to_address, amount, network, token_type):
    """
    Main payout function with rotation.
    """
    try:
        wallet = rotate_wallet(network, token_type)
        private_key = wallet.get("private_key")
        contract_address = wallet.get("contract_address")

        if not private_key:
            raise Exception("Wallet missing private key")
        if not contract_address:
            raise Exception("Wallet missing contract address")

        if network.lower() == "ethereum" and token_type.lower() == "usdt":
            tx_hash = send_erc20_token(to_address, amount, private_key, contract_address)
        elif network.lower() == "tron" and token_type.lower() == "usdt":
            tx_hash = send_trc20_token(to_address, amount, private_key, contract_address)
        else:
            raise Exception(f"Unsupported payout type: {network.upper()} - {token_type.upper()}")

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
