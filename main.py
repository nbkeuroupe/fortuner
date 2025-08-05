#!/usr/bin/env python3
"""
M0/M1 Card Terminal - Production Entry Point
Production-ready Flask app for deployment
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import the production app
from test_app import app

if __name__ == '__main__':
    # Production configuration
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    print("🏦 M0/M1 Card Terminal - Production Server")
    print(f"🌐 Port: {port}")
    print(f"🔧 Debug: {debug}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug
    )
