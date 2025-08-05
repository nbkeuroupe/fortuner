# logger.py - Production Logging System
import logging
import logging.handlers
import structlog
import coloredlogs
import os
import json
from datetime import datetime
from config import config

# Create logs directory
os.makedirs('logs', exist_ok=True)

class PaymentTerminalLogger:
    """Centralized logging system for payment terminal operations"""
    
    def __init__(self):
        self.setup_logging()
        self.logger = structlog.get_logger("payment_terminal")
    
    def setup_logging(self):
        """Configure structured logging with file rotation"""
        
        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="ISO"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
        
        # Configure standard logging
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.LOG_LEVEL))
        
        # File handler with rotation
        file_handler = logging.handlers.RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=config.MAX_LOG_SIZE,
            backupCount=config.LOG_BACKUP_COUNT
        )
        
        # Console handler with colors
        console_handler = logging.StreamHandler()
        
        # Formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Add handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Configure colored logs for console
        coloredlogs.install(
            level=config.LOG_LEVEL,
            logger=root_logger,
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    
    def log_transaction_start(self, card_number, amount, merchant_id, protocol):
        """Log transaction initiation"""
        self.logger.info(
            "transaction_started",
            card_number_masked=f"****{card_number[-4:]}",
            amount=amount,
            merchant_id=merchant_id,
            protocol=protocol,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_iso8583_request(self, request_data, server_host, server_port):
        """Log ISO8583 request"""
        safe_request = request_data.copy()
        if 'field_2' in safe_request:
            safe_request['field_2'] = f"****{safe_request['field_2'][-4:]}"
        
        self.logger.info(
            "iso8583_request_sent",
            request_data=safe_request,
            server_host=server_host,
            server_port=server_port,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_iso8583_response(self, response_data, response_time_ms):
        """Log ISO8583 response"""
        self.logger.info(
            "iso8583_response_received",
            response_code=response_data.get('field_39'),
            response_time_ms=response_time_ms,
            transaction_id=response_data.get('transaction_id'),
            arn=response_data.get('arn'),
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_crypto_payout_start(self, wallet_address, amount, network, token):
        """Log crypto payout initiation"""
        self.logger.info(
            "crypto_payout_started",
            wallet_address=wallet_address,
            amount=amount,
            network=network,
            token=token,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_crypto_payout_success(self, tx_hash, wallet_address, amount, network):
        """Log successful crypto payout"""
        self.logger.info(
            "crypto_payout_success",
            tx_hash=tx_hash,
            wallet_address=wallet_address,
            amount=amount,
            network=network,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_crypto_payout_failure(self, error, wallet_address, amount, network):
        """Log failed crypto payout"""
        self.logger.error(
            "crypto_payout_failed",
            error=str(error),
            wallet_address=wallet_address,
            amount=amount,
            network=network,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_security_event(self, event_type, user_id, ip_address, details=None):
        """Log security-related events"""
        self.logger.warning(
            "security_event",
            event_type=event_type,
            user_id=user_id,
            ip_address=ip_address,
            details=details or {},
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_system_error(self, error, context=None):
        """Log system errors"""
        self.logger.error(
            "system_error",
            error=str(error),
            error_type=type(error).__name__,
            context=context or {},
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_performance_metric(self, metric_name, value, unit="ms"):
        """Log performance metrics"""
        self.logger.info(
            "performance_metric",
            metric_name=metric_name,
            value=value,
            unit=unit,
            timestamp=datetime.utcnow().isoformat()
        )

# Global logger instance
payment_logger = PaymentTerminalLogger()

# Convenience functions
def log_transaction_start(card_number, amount, merchant_id, protocol):
    payment_logger.log_transaction_start(card_number, amount, merchant_id, protocol)

def log_iso8583_request(request_data, server_host, server_port):
    payment_logger.log_iso8583_request(request_data, server_host, server_port)

def log_iso8583_response(response_data, response_time_ms):
    payment_logger.log_iso8583_response(response_data, response_time_ms)

def log_crypto_payout_start(wallet_address, amount, network, token):
    payment_logger.log_crypto_payout_start(wallet_address, amount, network, token)

def log_crypto_payout_success(tx_hash, wallet_address, amount, network):
    payment_logger.log_crypto_payout_success(tx_hash, wallet_address, amount, network)

def log_crypto_payout_failure(error, wallet_address, amount, network):
    payment_logger.log_crypto_payout_failure(error, wallet_address, amount, network)

def log_security_event(event_type, user_id, ip_address, details=None):
    payment_logger.log_security_event(event_type, user_id, ip_address, details)

def log_system_error(error, context=None):
    payment_logger.log_system_error(error, context)

def log_performance_metric(metric_name, value, unit="ms"):
    payment_logger.log_performance_metric(metric_name, value, unit)
