import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# -------------------------
# Flask Settings
# -------------------------
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key")
FLASK_ENV = os.getenv("FLASK_ENV", "production")
PORT = int(os.getenv("PORT", 5000))

# -------------------------
# Terminal Auth
# -------------------------
TERMINAL_USERNAME = os.getenv("TERMINAL_USERNAME", "blackrock")
TERMINAL_PASSWORD = os.getenv("TERMINAL_PASSWORD", "terminal123")

# -------------------------
# ISO8583 Configuration
# -------------------------
ISO8583_HOST = os.getenv("ISO8583_HOST", "127.0.0.1")
ISO8583_PORT = int(os.getenv("ISO8583_PORT", 8583))
ISO8583_TIMEOUT = int(os.getenv("ISO8583_TIMEOUT", 30))

# -------------------------
# Blockchain Config
# -------------------------
TRON_NETWORK = os.getenv("TRON_NETWORK", "mainnet")  # "mainnet" or "testnet"
ETH_NETWORK = os.getenv("ETH_NETWORK", "mainnet")    # "mainnet" or "testnet"

# TRON
TRON_MERCHANT_WALLET = os.getenv("TRON_MERCHANT_WALLET")
TRON_PRIVATE_KEY = (
    os.getenv("TRON_PRIVATE_KEY") if TRON_NETWORK == "mainnet"
    else os.getenv("TEST_TRON_PRIVATE_KEY")
)

# ETH
ETH_MERCHANT_WALLET = os.getenv("ETH_MERCHANT_WALLET")
ETH_PRIVATE_KEY = (
    os.getenv("ETH_PRIVATE_KEY") if ETH_NETWORK == "mainnet"
    else os.getenv("TEST_ETH_PRIVATE_KEY")
)
INFURA_PROJECT_ID = os.getenv("INFURA_PROJECT_ID")

# -------------------------
# Transaction Configuration
# -------------------------
MAX_TRANSACTION_AMOUNT = float(os.getenv("MAX_TRANSACTION_AMOUNT", 10000000.00))
MIN_TRANSACTION_AMOUNT = float(os.getenv("MIN_TRANSACTION_AMOUNT", 0.01))
DAILY_TRANSACTION_LIMIT = float(os.getenv("DAILY_TRANSACTION_LIMIT", 100000000.00))
CONVERSION_FEE_PERCENT = float(os.getenv("CONVERSION_FEE_PERCENT", 2.5))
M0_TO_USDT_RATE = float(os.getenv("M0_TO_USDT_RATE", 1.0))
M1_TO_USDT_RATE = float(os.getenv("M1_TO_USDT_RATE", 1.0))

# -------------------------
# Rate Limiting
# -------------------------
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", 60))
RATE_LIMIT_PER_HOUR = int(os.getenv("RATE_LIMIT_PER_HOUR", 1000))

# -------------------------
# Security Settings
# -------------------------
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"
SESSION_COOKIE_HTTPONLY = os.getenv("SESSION_COOKIE_HTTPONLY", "true").lower() == "true"
SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Strict")

# -------------------------
# Logging Configuration
# -------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "logs/payment_terminal.log")
MAX_LOG_SIZE = int(os.getenv("MAX_LOG_SIZE", 10485760))
LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", 5))

# -------------------------
# Monitoring & Alerts
# -------------------------
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ALERT_EMAIL = os.getenv("ALERT_EMAIL", "nbkwebdevelopment@gmail.com")
