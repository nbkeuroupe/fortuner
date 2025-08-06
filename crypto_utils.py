# crypto_utils.py - Production Crypto Payment Processor

from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import PrivateKey
from web3 import Web3
from web3.middleware import geth_poa_middleware
import time
from decimal import Decimal
import threading
from retrying import retry

from config import config
from logger import (
    log_crypto_payout_start, log_crypto_payout_success,
    log_crypto_payout_failure, log_system_error, log_performance_metric
)

class CryptoPaymentProcessor:
    """Production-grade cryptocurrency payment processor"""

    def __init__(self):
        self.tron_client = None
        self.eth_client = None
        self.tron_lock = threading.Lock()
        self.eth_lock = threading.Lock()
        self._initialize_clients()

        # Minimal ERC-20 ABI
        self.erc20_abi = [
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
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
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

    def _initialize_clients(self):
        """Initialize blockchain clients using mainnet configuration only"""
        try:
            # TRON client (mainnet)
            if config.TRON_PRIVATE_KEY:
                self.tron_client = Tron()
                self.tron_private_key = PrivateKey(bytes.fromhex(config.TRON_PRIVATE_KEY))

            # Ethereum client (mainnet)
            if config.ETH_PRIVATE_KEY and config.INFURA_PROJECT_ID:
                provider_url = f"https://mainnet.infura.io/v3/{config.INFURA_PROJECT_ID}"
                self.eth_client = Web3(Web3.HTTPProvider(provider_url))
                if not self.eth_client.is_connected():
                    raise Exception("Failed to connect to Ethereum mainnet.")

                self.eth_account = self.eth_client.eth.account.from_key(config.ETH_PRIVATE_KEY)

        except Exception as e:
            log_system_error(e, {"context": "crypto_client_initialization"})

    def _validate_address(self, address, network):
        """Validate cryptocurrency address format"""
        try:
            if network == "TRON":
                return address.startswith('T') and len(address) == 34
            elif network == "ETH":
                return Web3.is_address(address)
            return False
        except:
            return False

    def _convert_amount_to_token_units(self, amount, decimals=6):
        """Convert amount to token units"""
        return int(Decimal(str(amount)) * (10 ** decimals))

    def _calculate_infrastructure_fee(self, amount):
        """Calculate infrastructure service fee"""
        fee_percent = config.CONVERSION_FEE_PERCENT / 100
        infrastructure_fee = float(amount) * fee_percent
        merchant_amount = float(amount) - infrastructure_fee

        return {
            'original_amount': float(amount),
            'infrastructure_fee': round(infrastructure_fee, 6),
            'merchant_amount': round(merchant_amount, 6),
            'fee_percentage': config.CONVERSION_FEE_PERCENT
        }

    def _apply_conversion_rate(self, amount, fund_type="M0"):
        """Apply conversion rate"""
        fee_calc = self._calculate_infrastructure_fee(amount)
        merchant_amount = fee_calc['merchant_amount']

        if fund_type == "M0":
            rate = config.M0_TO_USDT_RATE
        elif fund_type == "M1":
            rate = config.M1_TO_USDT_RATE
        else:
            rate = 1.0

        usdt_amount = merchant_amount * rate

        return {
            'usdt_amount': round(usdt_amount, 6),
            'conversion_rate': rate,
            'fund_type': fund_type,
            **fee_calc
        }

    def _estimate_eth_gas(self, contract_function, from_address):
        """Estimate gas for ERC-20 transfer"""
        try:
            estimate = contract_function.estimate_gas({'from': from_address})
            return int(estimate * 1.2)
        except Exception as e:
            log_system_error(e, {"context": "eth_gas_estimation"})
            return 100000

    def _get_eth_gas_price(self):
        """Get current gas price"""
        try:
            return self.eth_client.eth.gas_price
        except Exception as e:
            log_system_error(e, {"context": "eth_gas_price"})
            return Web3.to_wei(20, 'gwei')

    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=2000)
    def _send_tron_transaction(self, to_address, amount_usdt):
        """Send TRON USDT transfer"""
        with self.tron_lock:
            try:
                token_amount = self._convert_amount_to_token_units(amount_usdt)
                contract = self.tron_client.get_contract(config.USDT_TRC20_CONTRACT)

                txn = (
                    contract.functions.transfer(to_address, token_amount)
                    .with_owner(self.tron_private_key.public_key.to_base58check_address())
                    .fee_limit(5_000_000)
                    .build()
                    .sign(self.tron_private_key)
                )
                result = txn.broadcast().wait()
                return result['txid']

            except Exception as e:
                log_system_error(e, {"context": "tron_transaction"})
                raise

    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=2000)
    def _send_eth_transaction(self, to_address, amount_usdt):
        """Send Ethereum USDT transfer"""
        with self.eth_lock:
            try:
                token_amount = self._convert_amount_to_token_units(amount_usdt)
                contract = self.eth_client.eth.contract(
                    address=Web3.to_checksum_address(config.USDT_ERC20_CONTRACT),
                    abi=self.erc20_abi
                )
                gas_limit = self._estimate_eth_gas(
                    contract.functions.transfer(to_address, token_amount),
                    self.eth_account.address
                )
                gas_price = self._get_eth_gas_price()
                nonce = self.eth_client.eth.get_transaction_count(self.eth_account.address)

                txn = contract.functions.transfer(
                    to_address, token_amount
                ).build_transaction({
                    'chainId': 1,  # Ethereum mainnet
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': nonce
                })

                signed = self.eth_account.sign_transaction(txn)
                tx_hash = self.eth_client.eth.send_raw_transaction(signed.rawTransaction)
                return tx_hash.hex()

            except Exception as e:
                log_system_error(e, {"context": "eth_transaction"})
                raise

    def process_payout(self, to_address, amount, network, token, fund_type="M0"):
        """Process payout transaction"""
        start_time = time.time()

        try:
            if not self._validate_address(to_address, network):
                raise ValueError(f"Invalid {network} address: {to_address}")

            if float(amount) <= 0:
                raise ValueError("Amount must be positive.")

            if float(amount) < config.MIN_TRANSACTION_AMOUNT:
                raise ValueError("Amount below minimum allowed.")

            if float(amount) > config.MAX_TRANSACTION_AMOUNT:
                raise ValueError("Amount exceeds maximum allowed.")

            conversion = self._apply_conversion_rate(amount, fund_type)
            usdt_amount = conversion['usdt_amount']

            log_crypto_payout_start(to_address, usdt_amount, network, token)

            if network == "TRON" and self.tron_client:
                tx_hash = self._send_tron_transaction(to_address, usdt_amount)
                log_crypto_payout_success(tx_hash, to_address, usdt_amount, network)
            elif network == "ETH" and self.eth_client:
                tx_hash = self._send_eth_transaction(to_address, usdt_amount)
                log_crypto_payout_success(tx_hash, to_address, usdt_amount, network)
            else:
                raise Exception("Unsupported network or client not initialized.")

            elapsed = int((time.time() - start_time) * 1000)
            log_performance_metric("crypto_payout_time", elapsed, "ms")

            return tx_hash

        except Exception as e:
            log_crypto_payout_failure(e, to_address, amount, network)
            return f"error: {str(e)}"


# Singleton processor
_crypto_processor = None
_processor_lock = threading.Lock()

def get_crypto_processor():
    """Get singleton crypto processor"""
    global _crypto_processor
    if _crypto_processor is None:
        with _processor_lock:
            if _crypto_processor is None:
                _crypto_processor = CryptoPaymentProcessor()
    return _crypto_processor

def process_crypto_payout(to_address, amount, network, token, fund_type="M0"):
    """Legacy function for backward compatibility"""
    return get_crypto_processor().process_payout(to_address, amount, network, token, fund_type)
