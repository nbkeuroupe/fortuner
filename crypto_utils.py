# crypto_utils.py - Production Crypto Payment Processor
from tronpy import Tron
from tronpy.providers import HTTPProvider
from web3 import Web3
from web3.middleware import geth_poa_middleware
import os
import time
import json
from decimal import Decimal, ROUND_DOWN
from datetime import datetime, timedelta
from config import config
from logger import (
    log_crypto_payout_start, log_crypto_payout_success, 
    log_crypto_payout_failure, log_system_error, log_performance_metric
)
import threading
from retrying import retry
import validators

class CryptoPaymentProcessor:
    """Production-grade cryptocurrency payment processor"""
    
    def __init__(self):
        self.tron_client = None
        self.eth_client = None
        self.tron_lock = threading.Lock()
        self.eth_lock = threading.Lock()
        self._initialize_clients()
        
        # ERC-20 USDT ABI (minimal)
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
        """Initialize blockchain clients with proper configuration"""
        try:
            # Initialize TRON client
            if config.TRON_PRIVATE_KEY:
                if config.TRON_NETWORK == 'mainnet':
                    self.tron_client = Tron()
                else:
                    # Testnet configuration
                    provider = HTTPProvider("https://api.trongrid.io")
                    self.tron_client = Tron(provider)
            
            # Initialize Ethereum client
            if config.ETH_PRIVATE_KEY and config.INFURA_PROJECT_ID:
                if config.ETH_NETWORK == 'mainnet':
                    provider_url = f"https://mainnet.infura.io/v3/{config.INFURA_PROJECT_ID}"
                else:
                    provider_url = f"https://goerli.infura.io/v3/{config.INFURA_PROJECT_ID}"
                
                self.eth_client = Web3(Web3.HTTPProvider(provider_url))
                
                # Add middleware for PoA networks if needed
                if config.ETH_NETWORK != 'mainnet':
                    self.eth_client.middleware_onion.inject(geth_poa_middleware, layer=0)
                
                # Verify connection
                if not self.eth_client.is_connected():
                    raise Exception("Failed to connect to Ethereum network")
                    
        except Exception as e:
            log_system_error(e, {"context": "crypto_client_initialization"})
    
    def _validate_address(self, address, network):
        """Validate cryptocurrency address format"""
        try:
            if network == "TRON":
                # TRON addresses start with 'T' and are 34 characters
                return address.startswith('T') and len(address) == 34
            elif network == "ETH":
                # Ethereum addresses are 42 characters starting with '0x'
                return Web3.is_address(address)
            return False
        except:
            return False
    
    def _convert_amount_to_token_units(self, amount, decimals=6):
        """Convert amount to token units (USDT has 6 decimals)"""
        decimal_amount = Decimal(str(amount))
        token_units = int(decimal_amount * (10 ** decimals))
        return token_units
    
    def _calculate_infrastructure_fee(self, amount):
        """Calculate infrastructure service fee (separate from gas fees)"""
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
        """Apply M0/M1 to USDT conversion rate (after infrastructure fee)"""
        # Calculate infrastructure fee first
        fee_calculation = self._calculate_infrastructure_fee(amount)
        merchant_amount = fee_calculation['merchant_amount']
        
        # Apply M0/M1 to USDT conversion rate
        if fund_type == "M0":
            rate = config.M0_TO_USDT_RATE
        elif fund_type == "M1":
            rate = config.M1_TO_USDT_RATE
        else:
            rate = 1.0
        
        # Convert merchant amount to USDT
        usdt_amount = merchant_amount * rate
        
        return {
            'usdt_amount': round(usdt_amount, 6),
            'conversion_rate': rate,
            'fund_type': fund_type,
            **fee_calculation
        }
    
    def _check_tron_balance(self, address):
        """Check USDT TRC-20 balance"""
        try:
            contract = self.tron_client.get_contract(config.USDT_TRC20_CONTRACT)
            balance = contract.functions.balanceOf(address)
            return balance / 1_000_000  # USDT has 6 decimals
        except Exception as e:
            log_system_error(e, {"context": "tron_balance_check", "address": address})
            return 0
    
    def _check_eth_balance(self, address):
        """Check USDT ERC-20 balance"""
        try:
            contract = self.eth_client.eth.contract(
                address=config.USDT_ERC20_CONTRACT,
                abi=self.erc20_abi
            )
            balance = contract.functions.balanceOf(address).call()
            return balance / 1_000_000  # USDT has 6 decimals
        except Exception as e:
            log_system_error(e, {"context": "eth_balance_check", "address": address})
            return 0
    
    def _estimate_eth_gas(self, contract_function, from_address):
        """Estimate gas for Ethereum transaction"""
        try:
            gas_estimate = contract_function.estimate_gas({'from': from_address})
            # Add 20% buffer
            return int(gas_estimate * 1.2)
        except Exception as e:
            log_system_error(e, {"context": "eth_gas_estimation"})
            return 100000  # Default gas limit
    
    def _get_eth_gas_price(self):
        """Get current gas price with optimization"""
        try:
            # Get current gas price
            gas_price = self.eth_client.eth.gas_price
            
            # Apply optimization (use 90% of current price for faster processing)
            optimized_price = int(gas_price * 0.9)
            
            # Ensure minimum gas price
            min_gas_price = Web3.to_wei(1, 'gwei')
            return max(optimized_price, min_gas_price)
            
        except Exception as e:
            log_system_error(e, {"context": "eth_gas_price"})
            return Web3.to_wei(20, 'gwei')  # Default 20 gwei
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=2000)
    def _send_tron_transaction(self, to_address, amount_usdt):
        """Send TRON TRC-20 USDT transaction with retry logic"""
        with self.tron_lock:
            try:
                # Convert amount to token units
                token_amount = self._convert_amount_to_token_units(amount_usdt, 6)
                
                # Build transaction
                contract = self.tron_client.get_contract(config.USDT_TRC20_CONTRACT)
                txn = (
                    contract.functions.transfer(to_address, token_amount)
                    .with_owner(self.tron_client.generate_address(config.TRON_PRIVATE_KEY)['base58check_address'])
                    .fee_limit(50_000_000)  # 50 TRX fee limit
                    .build()
                    .sign(config.TRON_PRIVATE_KEY)
                )
                
                # Broadcast transaction
                result = txn.broadcast()
                
                if result.get('result'):
                    return result['txid']
                else:
                    raise Exception(f"Transaction failed: {result}")
                    
            except Exception as e:
                log_system_error(e, {"context": "tron_transaction", "address": to_address})
                raise
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=2000)
    def _send_eth_transaction(self, to_address, amount_usdt):
        """Send Ethereum ERC-20 USDT transaction with retry logic"""
        with self.eth_lock:
            try:
                # Get account from private key
                account = self.eth_client.eth.account.from_key(config.ETH_PRIVATE_KEY)
                from_address = account.address
                
                # Convert amount to token units
                token_amount = self._convert_amount_to_token_units(amount_usdt, 6)
                
                # Create contract instance
                contract = self.eth_client.eth.contract(
                    address=config.USDT_ERC20_CONTRACT,
                    abi=self.erc20_abi
                )
                
                # Estimate gas
                gas_limit = self._estimate_eth_gas(
                    contract.functions.transfer(to_address, token_amount),
                    from_address
                )
                
                # Get current gas price
                gas_price = self._get_eth_gas_price()
                
                # Get nonce
                nonce = self.eth_client.eth.get_transaction_count(from_address)
                
                # Build transaction
                transaction = contract.functions.transfer(
                    to_address, token_amount
                ).build_transaction({
                    'chainId': 1 if config.ETH_NETWORK == 'mainnet' else 5,  # Goerli testnet
                    'gas': gas_limit,
                    'gasPrice': gas_price,
                    'nonce': nonce
                })
                
                # Sign transaction
                signed_txn = self.eth_client.eth.account.sign_transaction(
                    transaction, config.ETH_PRIVATE_KEY
                )
                
                # Send transaction
                tx_hash = self.eth_client.eth.send_raw_transaction(signed_txn.rawTransaction)
                
                return tx_hash.hex()
                
            except Exception as e:
                log_system_error(e, {"context": "eth_transaction", "address": to_address})
                raise
    
    def _wait_for_confirmation(self, tx_hash, network, timeout=300):
        """Wait for transaction confirmation"""
        start_time = time.time()
        
        try:
            if network == "TRON":
                while time.time() - start_time < timeout:
                    try:
                        tx_info = self.tron_client.get_transaction(tx_hash)
                        if tx_info and tx_info.get('ret', [{}])[0].get('contractRet') == 'SUCCESS':
                            return True
                    except:
                        pass
                    time.sleep(5)
                    
            elif network == "ETH":
                while time.time() - start_time < timeout:
                    try:
                        receipt = self.eth_client.eth.get_transaction_receipt(tx_hash)
                        if receipt and receipt['status'] == 1:
                            return True
                    except:
                        pass
                    time.sleep(10)
            
            return False
            
        except Exception as e:
            log_system_error(e, {"context": "transaction_confirmation", "tx_hash": tx_hash})
            return False
    
    def process_payout(self, to_address, amount, network, token, fund_type="M0"):
        """Process cryptocurrency payout with full production features"""
        start_time = time.time()
        
        try:
            # Validate inputs
            if not self._validate_address(to_address, network):
                raise ValueError(f"Invalid {network} address: {to_address}")
            
            if float(amount) <= 0:
                raise ValueError(f"Invalid amount: {amount}")
            
            if float(amount) < config.MIN_TRANSACTION_AMOUNT:
                raise ValueError(f"Amount below minimum: {config.MIN_TRANSACTION_AMOUNT}")
            
            if float(amount) > config.MAX_TRANSACTION_AMOUNT:
                raise ValueError(f"Amount exceeds maximum: {config.MAX_TRANSACTION_AMOUNT}")
            
            # Apply conversion rate and calculate fees
            conversion_result = self._apply_conversion_rate(amount, fund_type)
            usdt_amount = conversion_result['usdt_amount']
            
            # Log payout start with fee details
            log_crypto_payout_start(to_address, usdt_amount, network, token)
            
            # Process based on network
            if network == "TRON" and self.tron_client:
                tx_hash = self._send_tron_transaction(to_address, converted_amount)
                
                # Wait for confirmation (optional, for critical transactions)
                # confirmed = self._wait_for_confirmation(tx_hash, "TRON")
                
                log_crypto_payout_success(tx_hash, to_address, converted_amount, network)
                
            elif network == "ETH" and self.eth_client:
                tx_hash = self._send_eth_transaction(to_address, converted_amount)
                
                # Wait for confirmation (optional)
                # confirmed = self._wait_for_confirmation(tx_hash, "ETH")
                
                log_crypto_payout_success(tx_hash, to_address, converted_amount, network)
                
            else:
                raise Exception(f"Unsupported network or client not initialized: {network}")
            
            # Log performance metric
            processing_time = int((time.time() - start_time) * 1000)
            log_performance_metric("crypto_payout_time", processing_time, "ms")
            
            return tx_hash
            
        except Exception as e:
            log_crypto_payout_failure(e, to_address, amount, network)
            return f"error: {str(e)}"

# Global processor instance
_crypto_processor = None
_processor_lock = threading.Lock()

def get_crypto_processor():
    """Get singleton crypto processor instance"""
    global _crypto_processor
    if _crypto_processor is None:
        with _processor_lock:
            if _crypto_processor is None:
                _crypto_processor = CryptoPaymentProcessor()
    return _crypto_processor

# Legacy compatibility function
def process_crypto_payout(to_address, amount, network, token, fund_type="M0"):
    """Legacy function for backward compatibility"""
    processor = get_crypto_processor()
    return processor.process_payout(to_address, amount, network, token, fund_type)
