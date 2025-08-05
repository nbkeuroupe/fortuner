#!/usr/bin/env python3
"""
Simple test to verify the complete M0/M1 card terminal flow
"""

import requests
import json

BASE_URL = "http://localhost:5000"

def test_complete_flow():
    """Test the complete user flow"""
    session = requests.Session()
    
    print("🧪 Testing M0/M1 Card Terminal Flow...")
    
    # Step 1: Login
    print("\n1. Testing login...")
    login_data = {
        'username': 'blackrock',
        'password': 'terminal123'
    }
    
    login_response = session.post(f"{BASE_URL}/login", data=login_data)
    if login_response.status_code == 200:
        print("✅ Login successful")
    else:
        print(f"❌ Login failed: {login_response.status_code}")
        return
    
    # Step 2: Process transaction
    print("\n2. Testing card transaction...")
    transaction_data = {
        'card_number': '4111111111111111',
        'expiry_date': '12/25',
        'cvv': '123',
        'amount': '1000.00',
        'currency': 'USD',
        'protocol': '101.1',
        'merchant_id': 'MERCHANT001',
        'auth_code': '1234',
        'merchant_wallet': 'tron_main'
    }
    
    process_response = session.post(f"{BASE_URL}/process", data=transaction_data)
    if process_response.status_code == 200:
        response_data = process_response.json()
        print(f"✅ Transaction processed: {response_data}")
        
        if response_data.get('success') and response_data.get('redirect'):
            # Step 3: Check transaction result page
            print("\n3. Testing transaction result page...")
            result_url = f"{BASE_URL}{response_data['redirect']}"
            result_response = session.get(result_url)
            
            if result_response.status_code == 200:
                print("✅ Transaction result page accessible")
                print("🎉 Complete flow working!")
            else:
                print(f"❌ Transaction result page failed: {result_response.status_code}")
        else:
            print(f"❌ Invalid response format: {response_data}")
    else:
        print(f"❌ Transaction processing failed: {process_response.status_code}")
        print(f"Response: {process_response.text}")

if __name__ == "__main__":
    test_complete_flow()
