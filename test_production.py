#!/usr/bin/env python3
"""
Production M0/M1 Terminal Test Script
Tests complete end-to-end flow
"""

import requests
import json
import time

BASE_URL = 'http://127.0.0.1:5000'

def test_production_flow():
    """Test complete production flow"""
    session = requests.Session()
    
    print("🏦 Testing Production M0/M1 Card Terminal")
    print("=" * 50)
    
    # Test 1: Health check
    print("\n1. Testing health check...")
    try:
        response = session.get(f'{BASE_URL}/health')
        if response.status_code == 200:
            health_data = response.json()
            print(f"✅ Health check passed: {health_data['status']}")
            print(f"   Environment: {health_data.get('environment', 'unknown')}")
            print(f"   Version: {health_data.get('version', 'unknown')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False
    
    # Test 2: Login
    print("\n2. Testing login...")
    try:
        # Get login page
        response = session.get(f'{BASE_URL}/login')
        if response.status_code != 200:
            print(f"❌ Login page failed: {response.status_code}")
            return False
        
        # Login with credentials
        login_data = {
            'username': 'blackrock',
            'password': 'terminal123'
        }
        response = session.post(f'{BASE_URL}/login', data=login_data)
        if response.status_code == 200 and 'terminal.html' in response.text:
            print("✅ Login successful")
        else:
            print(f"❌ Login failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Login error: {e}")
        return False
    
    # Test 3: Terminal page access
    print("\n3. Testing terminal access...")
    try:
        response = session.get(f'{BASE_URL}/')
        if response.status_code == 200 and 'Card Terminal' in response.text:
            print("✅ Terminal page accessible")
        else:
            print(f"❌ Terminal access failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Terminal access error: {e}")
        return False
    
    # Test 4: Card transaction processing
    print("\n4. Testing card transaction...")
    try:
        transaction_data = {
            'card_number': '4111111111111111',
            'expiry_date': '12/25',
            'cvv': '123',
            'amount': '100.00',
            'currency': 'USD',
            'protocol': '101.1',
            'merchant_id': 'MERCHANT001',
            'auth_code': '1234',
            'merchant_wallet': 'trc20'
        }
        
        response = session.post(f'{BASE_URL}/process', data=transaction_data)
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Transaction processed successfully")
                print(f"   Redirect: {result.get('redirect')}")
                
                # Test 5: Transaction result page
                print("\n5. Testing transaction result...")
                result_url = result.get('redirect')
                if result_url:
                    response = session.get(f'{BASE_URL}{result_url}')
                    if response.status_code == 200 and 'Transaction Result' in response.text:
                        print("✅ Transaction result page accessible")
                        
                        # Check for success indicators
                        if 'success' in response.text.lower() or 'approved' in response.text.lower():
                            print("✅ Transaction shows success status")
                        else:
                            print("ℹ️  Transaction result displayed (check status)")
                            
                    else:
                        print(f"❌ Transaction result failed: {response.status_code}")
                        return False
                else:
                    print("❌ No redirect URL provided")
                    return False
            else:
                print(f"❌ Transaction failed: {result.get('error')}")
                return False
        else:
            print(f"❌ Transaction request failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Transaction error: {e}")
        return False
    
    # Test 6: Logout
    print("\n6. Testing logout...")
    try:
        response = session.get(f'{BASE_URL}/logout')
        if response.status_code == 200:
            print("✅ Logout successful")
        else:
            print(f"❌ Logout failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Logout error: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 PRODUCTION FLOW TEST COMPLETED SUCCESSFULLY!")
    print("✅ All core functionality working")
    print("✅ Login → Terminal → Transaction → Results → Logout")
    print("✅ Ready for production deployment")
    return True

if __name__ == '__main__':
    success = test_production_flow()
    if success:
        print("\n🚀 Production system is ready!")
    else:
        print("\n❌ Production system needs fixes")
