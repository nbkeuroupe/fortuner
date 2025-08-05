# config.py - Production Configuration
import os
from dotenv import load_dotenv
import logging
from datetime import timedelta

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    
    # Flask Configuration
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    FLASK_ENV = os.getenv('FLASK_ENV', 'production')
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(seconds=int(os.getenv('SESSION_TIMEOUT', 3600)))
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
    
    # File Paths
    PASSWORD_FILE = "data/passwords.json"
    WALLETS_FILE = "data/wallets.json"
    TRANSACTIONS_FILE = "data/transactions.json"
    
    # User Management
    USERNAME = "blackrock"  # Default admin username
    MAX_LOGIN_ATTEMPTS = int(os.getenv('MAX_LOGIN_ATTEMPTS', 5))
    LOCKOUT_DURATION = int(os.getenv('LOCKOUT_DURATION', 300))
    OTP_EXPIRY = int(os.getenv('OTP_EXPIRY', 300))
    
    # ISO8583 Configuration
    ISO_SERVER_HOST = os.getenv('ISO_SERVER_HOST', 'localhost')
    ISO_SERVER_PORT = int(os.getenv('ISO_SERVER_PORT', 8583))
    ISO_TIMEOUT = int(os.getenv('ISO_TIMEOUT', 10))
    ISO_RETRY_ATTEMPTS = int(os.getenv('ISO_RETRY_ATTEMPTS', 3))
    
    # Cryptocurrency Configuration
    TRON_PRIVATE_KEY = os.getenv('TRON_PRIVATE_KEY')
    ETH_PRIVATE_KEY = os.getenv('ETH_PRIVATE_KEY')
    INFURA_PROJECT_ID = os.getenv('INFURA_PROJECT_ID')
    TRON_NETWORK = os.getenv('TRON_NETWORK', 'mainnet')
    ETH_NETWORK = os.getenv('ETH_NETWORK', 'mainnet')
    
    # Contract Addresses
    USDT_TRC20_CONTRACT = os.getenv('USDT_TRC20_CONTRACT', 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t')
    USDT_ERC20_CONTRACT = os.getenv('USDT_ERC20_CONTRACT', '0xdAC17F958D2ee523a2206206994597C13D831ec7')
    
    # Transaction Limits (High-Value M0/M1 Cards)
    MIN_TRANSACTION_AMOUNT = float(os.getenv('MIN_TRANSACTION_AMOUNT', 0.01))
    MAX_TRANSACTION_AMOUNT = float(os.getenv('MAX_TRANSACTION_AMOUNT', 10000000.00))
    MAX_TRANSACTION_AMOUNT_EUR = float(os.getenv('MAX_TRANSACTION_AMOUNT_EUR', 10000000.00))
    DAILY_TRANSACTION_LIMIT = float(os.getenv('DAILY_TRANSACTION_LIMIT', 100000000.00))
    
    # Conversion Configuration
    M0_TO_USDT_RATE = float(os.getenv('M0_TO_USDT_RATE', 1.0))
    M1_TO_USDT_RATE = float(os.getenv('M1_TO_USDT_RATE', 1.0))
    CONVERSION_FEE_PERCENT = float(os.getenv('CONVERSION_FEE_PERCENT', 0.5))
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE = int(os.getenv('RATE_LIMIT_PER_MINUTE', 60))
    RATE_LIMIT_PER_HOUR = int(os.getenv('RATE_LIMIT_PER_HOUR', 1000))
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    LOG_FILE = os.getenv('LOG_FILE', 'logs/payment_terminal.log')
    MAX_LOG_SIZE = int(os.getenv('MAX_LOG_SIZE', 10485760))
    LOG_BACKUP_COUNT = int(os.getenv('LOG_BACKUP_COUNT', 5))
    
    # Monitoring
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    ALERT_EMAIL = os.getenv('ALERT_EMAIL')

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    SESSION_COOKIE_SECURE = False

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    
    @classmethod
    def validate_config(cls):
        """Validate critical production settings"""
        required_vars = [
            'SECRET_KEY', 'TRON_PRIVATE_KEY', 'ETH_PRIVATE_KEY',
            'ISO_SERVER_HOST', 'INFURA_PROJECT_ID'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var) or getattr(cls, var) in ['your-key-here', 'localhost']:
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required production config: {', '.join(missing_vars)}")

# Configuration factory
def get_config():
    env = os.getenv('FLASK_ENV', 'production')
    if env == 'development':
        return DevelopmentConfig
    else:
        config = ProductionConfig
        if env == 'production':
            config.validate_config()
        return config

# Export current config
config = get_config()

# Legacy compatibility
USERNAME = config.USERNAME
PASSWORD_FILE = config.PASSWORD_FILE
WALLETS_FILE = config.WALLETS_FILE
