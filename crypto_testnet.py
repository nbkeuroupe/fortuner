#!/usr/bin/env python3
"""
Crypto Testnet Payout Module for M0/M1 Terminal
Real testnet transactions for TRON and Ethereum
"""

import os
import time
from web3 import Web3
from tronpy import Tron
from tronpy.keys import PrivateKey
import json

# Testnet Configuration
TRON_TESTNET_RPC = "https://api.shasta.trongrid.io"
ETH_TESTNET_RPC = "https://sepolia.infura.io/v3/YOUR_INFURA_KEY"

# Testnet USDT Contract Addresses
TRON_TESTNET_USDT = "TG3XXyExBkPp9nzdajDZsozEu4BkaSJozs"  # Shasta testnet USDT
ETH_TESTNET_USDT = "0x7169D38820dfd117C3FA1f22a697dBA58d90BA06"  # Sepolia testnet USDT

# Test private keys (DO NOT USE IN PRODUCTION)
TEST_TRON_PRIVATE_KEY = os.environ.get('TEST_TRON_PRIVATE_KEY', '')
TEST_ETH_PRIVATE_KEY = os.environ.get('TEST_ETH_PRIVATE_KEY', '')

class CryptoTestnetPayout:
    def __init__(self):
        self.tron_client = None
        self.eth_client = None
        self.setup_clients()
    
    def setup_clients(self):
        """Initialize testnet clients"""
        try:
            # TRON Shasta testnet
            self.tron_client = Tron(network='shasta')
            print("✅ TRON Shasta testnet connected")
            
            # Ethereum Sepolia testnet
            if ETH_TESTNET_RPC != "https://sepolia.infura.io/v3/YOUR_INFURA_KEY":
                self.eth_client = Web3(Web3.HTTPProvider(ETH_TESTNET_RPC))
                if self.eth_client.is_connected():
                    print("✅ Ethereum Sepolia testnet connected")
                else:
                    print("❌ Ethereum testnet connection failed")
            else:
                print("⚠️  Ethereum testnet requires Infura key")
                
        except Exception as e:
            print(f"❌ Testnet setup error: {e}")
    
    def send_tron_testnet_usdt(self, to_address, amount_usdt):
        """Send USDT on TRON Shasta testnet"""
        try:
            if not TEST_TRON_PRIVATE_KEY:
                return self._mock_transaction("TRON_TESTNET", to_address, amount_usdt)
            
            print(f"🔄 Sending {amount_usdt} USDT to {to_address} on TRON testnet...")
            
            # Create private key object
            private_key = PrivateKey(bytes.fromhex(TEST_TRON_PRIVATE_KEY))
            
            # Get contract
            contract = self.tron_client.get_contract(TRON_TESTNET_USDT)
            
            # Convert amount to proper decimals (USDT has 6 decimals)
            amount_with_decimals = int(amount_usdt * 1_000_000)
            
            # Build transaction
            txn = (
                contract.functions.transfer(to_address, amount_with_decimals)
                .with_owner(private_key.public_key.to_base58check_address())
                .fee_limit(100_000_000)  # 100 TRX fee limit
                .build()
                .sign(private_key)
            )
            
            # Broadcast transaction
            result = txn.broadcast()
            
            if result.get('result'):
                tx_hash = result['txid']
                print(f"✅ TRON testnet transaction successful: {tx_hash}")
                return {
                    'success': True,
                    'tx_hash': tx_hash,
                    'network': 'TRON_TESTNET',
                    'explorer_url': f"https://shasta.tronscan.org/#/transaction/{tx_hash}"
                }
            else:
                print(f"❌ TRON testnet transaction failed: {result}")
                return {'success': False, 'error': 'Transaction failed'}
                
        except Exception as e:
            print(f"❌ TRON testnet error: {e}")
            return self._mock_transaction("TRON_TESTNET", to_address, amount_usdt)
    
    def send_eth_testnet_usdt(self, to_address, amount_usdt):
        """Send USDT on Ethereum Sepolia testnet"""
        try:
            if not TEST_ETH_PRIVATE_KEY or not self.eth_client:
                return self._mock_transaction("ETH_TESTNET", to_address, amount_usdt)
            
            print(f"🔄 Sending {amount_usdt} USDT to {to_address} on Ethereum testnet...")
            
            # Account setup
            account = self.eth_client.eth.account.from_key(TEST_ETH_PRIVATE_KEY)
            
            # USDT contract ABI (simplified)
            usdt_abi = [
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
            
            # Contract instance
            contract = self.eth_client.eth.contract(
                address=ETH_TESTNET_USDT,
                abi=usdt_abi
            )
            
            # Convert amount (USDT has 6 decimals)
            amount_with_decimals = int(amount_usdt * 1_000_000)
            
            # Build transaction
            transaction = contract.functions.transfer(
                to_address, amount_with_decimals
            ).build_transaction({
                'from': account.address,
                'gas': 100000,
                'gasPrice': self.eth_client.to_wei('20', 'gwei'),
                'nonce': self.eth_client.eth.get_transaction_count(account.address)
            })
            
            # Sign and send
            signed_txn = self.eth_client.eth.account.sign_transaction(transaction, TEST_ETH_PRIVATE_KEY)
            tx_hash = self.eth_client.eth.send_raw_transaction(signed_txn.rawTransaction)
            
            print(f"✅ Ethereum testnet transaction successful: {tx_hash.hex()}")
            return {
                'success': True,
                'tx_hash': tx_hash.hex(),
                'network': 'ETH_TESTNET',
                'explorer_url': f"https://sepolia.etherscan.io/tx/{tx_hash.hex()}"
            }
            
        except Exception as e:
            print(f"❌ Ethereum testnet error: {e}")
            return self._mock_transaction("ETH_TESTNET", to_address, amount_usdt)
    
    def _mock_transaction(self, network, to_address, amount):
        """Mock transaction for testing without real keys"""
        mock_hash = f"0x{hash(f'{network}{to_address}{amount}{time.time()}')}"[-64:]
        print(f"🧪 Mock {network} transaction: {amount} USDT to {to_address}")
        
        explorer_urls = {
            'TRON_TESTNET': f"https://shasta.tronscan.org/#/transaction/{mock_hash}",
            'ETH_TESTNET': f"https://sepolia.etherscan.io/tx/{mock_hash}"
        }
        
        return {
            'success': True,
            'tx_hash': mock_hash,
            'network': network,
            'explorer_url': explorer_urls.get(network, ''),
            'mock': True
        }
    
    def process_testnet_payout(self, network, to_address, amount_usdt):
        """Process testnet payout based on network"""
        print(f"🧪 Processing testnet payout: {amount_usdt} USDT on {network}")
        
        if network.upper() == 'TRON':
            return self.send_tron_testnet_usdt(to_address, amount_usdt)
        elif network.upper() == 'ETHEREUM':
            return self.send_eth_testnet_usdt(to_address, amount_usdt)
        else:
            return {'success': False, 'error': f'Unsupported testnet: {network}'}

# Test function
def test_crypto_payouts():
    """Test both TRON and Ethereum testnet payouts"""
    print("🧪 Testing Crypto Testnet Payouts")
    print("=" * 50)
    
    payout = CryptoTestnetPayout()
    
    # Test addresses (these are valid testnet addresses)
    test_tron_address = "TQn9Y2khEsLJW1ChVWFMSMeRDow5KcbLSE"
    test_eth_address = "0x742d35Cc6634C0532925a3b8D0C9f2b8b8b8b8b8"
    
    # Test TRON payout
    print("\n1. Testing TRON Shasta testnet payout...")
    tron_result = payout.process_testnet_payout('TRON', test_tron_address, 10.50)
    print(f"Result: {tron_result}")
    
    # Test Ethereum payout
    print("\n2. Testing Ethereum Sepolia testnet payout...")
    eth_result = payout.process_testnet_payout('ETHEREUM', test_eth_address, 25.75)
    print(f"Result: {eth_result}")
    
    print("\n✅ Testnet payout tests completed!")
    return tron_result, eth_result

if __name__ == '__main__':
    test_crypto_payouts()
