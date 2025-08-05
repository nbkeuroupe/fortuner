# iso_client.py - Production ISO8583 Client
import socket
import json
import time
import uuid
import hashlib
from datetime import datetime
from retrying import retry
from config import config
from logger import log_iso8583_request, log_iso8583_response, log_system_error
from bin_lookup import lookup_issuer, get_supported_protocols, is_m0_card, is_m1_card
import threading
from queue import Queue, Empty

class ISO8583Client:
    """Production-grade ISO8583 client with connection pooling and retry logic"""
    
    def __init__(self):
        # Default fallback configuration
        self.default_host = config.ISO_SERVER_HOST
        self.default_port = config.ISO_SERVER_PORT
        self.default_timeout = config.ISO_TIMEOUT
        self.retry_attempts = config.ISO_RETRY_ATTEMPTS
        
        # Connection pools per issuer (host:port -> Queue)
        self.connection_pools = {}
        self.pool_lock = threading.Lock()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        for _ in range(5):  # Start with 5 connections
            try:
                conn = self._create_connection()
                self.connection_pool.put(conn)
            except Exception as e:
                log_system_error(e, {"context": "connection_pool_init"})
    
    def _create_connection(self):
        """Create a new socket connection"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.connect((self.host, self.port))
        return sock
    
    def _get_connection(self):
        """Get connection from pool or create new one"""
        try:
            return self.connection_pool.get_nowait()
        except Empty:
            return self._create_connection()
    
    def _return_connection(self, conn):
        """Return connection to pool"""
        try:
            if self.connection_pool.qsize() < 10:
                self.connection_pool.put_nowait(conn)
            else:
                conn.close()
        except:
            conn.close()
    
    def _generate_transaction_id(self):
        """Generate unique transaction ID"""
        timestamp = str(int(time.time()))
        random_part = str(uuid.uuid4())[:8]
        return f"TXN{timestamp}{random_part}".upper()
    
    def _generate_arn(self):
        """Generate Acquirer Reference Number"""
        timestamp = datetime.now().strftime("%y%m%d%H%M%S")
        return f"ARN{timestamp}{str(uuid.uuid4())[:6].upper()}"
    
    def _calculate_checksum(self, data):
        """Calculate message checksum for integrity"""
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]
    
    def _build_iso8583_message(self, card_number, amount, merchant_id, auth_code, protocol_version=None):
        """Build ISO8583 message with proper fields"""
        transaction_id = self._generate_transaction_id()
        arn = self._generate_arn()
        timestamp = datetime.now().strftime("%m%d%H%M%S")
        
        # Determine MTI based on protocol version
        mti = "0100"  # Financial Transaction Request
        if protocol_version and "201" in protocol_version:
            mti = "0200"  # Financial Transaction Request (Acquirer)
        
        message = {
            "mti": mti,
            "field_2": card_number,  # Primary Account Number
            "field_3": "000000",    # Processing Code
            "field_4": f"{int(float(amount) * 100):012d}",  # Transaction Amount
            "field_7": timestamp,   # Transmission Date/Time
            "field_11": str(int(time.time()) % 1000000).zfill(6),  # STAN
            "field_12": datetime.now().strftime("%H%M%S"),  # Local Transaction Time
            "field_13": datetime.now().strftime("%m%d"),    # Local Transaction Date
            "field_18": "6011",     # Merchant Category Code
            "field_22": "051",      # POS Entry Mode
            "field_25": "00",       # POS Condition Code
            "field_32": "123456",   # Acquiring Institution ID
            "field_37": auth_code,  # Retrieval Reference Number
            "field_41": "TERMID01", # Card Acceptor Terminal ID
            "field_42": merchant_id, # Card Acceptor ID
            "field_49": "840",      # Transaction Currency Code (USD)
            "transaction_id": transaction_id,
            "arn": arn,
            "protocol_version": protocol_version or "POS Terminal -101.1",
            "checksum": ""
        }
        
        # Add checksum
        message["checksum"] = self._calculate_checksum(message)
        return message
    
    @retry(stop_max_attempt_number=3, wait_exponential_multiplier=1000, wait_exponential_max=10000)
    def _send_message_with_retry(self, message):
        """Send message with retry logic"""
        conn = None
        start_time = time.time()
        
        try:
            conn = self._get_connection()
            
            # Send message
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            
            # Send length prefix (4 bytes) + message
            length_prefix = len(message_bytes).to_bytes(4, byteorder='big')
            conn.sendall(length_prefix + message_bytes)
            
            # Log request
            log_iso8583_request(message, self.host, self.port)
            
            # Receive response length
            length_bytes = conn.recv(4)
            if len(length_bytes) != 4:
                raise Exception("Invalid response length header")
            
            response_length = int.from_bytes(length_bytes, byteorder='big')
            
            # Receive response data
            response_data = b''
            while len(response_data) < response_length:
                chunk = conn.recv(min(4096, response_length - len(response_data)))
                if not chunk:
                    raise Exception("Connection closed unexpectedly")
                response_data += chunk
            
            response = json.loads(response_data.decode('utf-8'))
            response_time_ms = int((time.time() - start_time) * 1000)
            
            # Log response
            log_iso8583_response(response, response_time_ms)
            
            # Return connection to pool
            self._return_connection(conn)
            
            return response
            
        except Exception as e:
            if conn:
                conn.close()
            log_system_error(e, {"context": "iso8583_send_message", "message": message})
            raise
    
    def send_authorization_request(self, card_number, amount, merchant_id, auth_code, protocol_version=None):
        """Send authorization request to ISO8583 server"""
        try:
            # Validate inputs
            if not card_number or len(card_number) < 13:
                return {"field_39": "30", "error": "Invalid card number"}
            
            if float(amount) <= 0:
                return {"field_39": "13", "error": "Invalid amount"}
            
            if not merchant_id:
                return {"field_39": "03", "error": "Invalid merchant"}
            
            # Build and send message
            message = self._build_iso8583_message(
                card_number, amount, merchant_id, auth_code, protocol_version
            )
            
            response = self._send_message_with_retry(message)
            
            # Validate response
            if not response.get('field_39'):
                response['field_39'] = '96'  # System error
            
            # Add transaction metadata
            response['transaction_id'] = message['transaction_id']
            response['arn'] = message['arn']
            response['card_type'] = self._detect_card_type(card_number)
            response['processing_time'] = datetime.now().isoformat()
            
            return response
            
        except Exception as e:
            log_system_error(e, {"context": "authorization_request"})
            return {
                "field_39": "96",  # System error
                "error": str(e),
                "transaction_id": self._generate_transaction_id(),
                "arn": self._generate_arn()
            }
    
    def _detect_card_type(self, card_number):
        """Detect card type from PAN"""
        if card_number.startswith('4'):
            return 'VISA'
        elif card_number.startswith(('51', '52', '53', '54', '55')):
            return 'MASTERCARD'
        elif card_number.startswith(('34', '37')):
            return 'AMEX'
        elif card_number.startswith('6011'):
            return 'DISCOVER'
        else:
            return 'UNKNOWN'
    
    def close_connections(self):
        """Close all connections in pool"""
        while not self.connection_pool.empty():
            try:
                conn = self.connection_pool.get_nowait()
                conn.close()
            except Empty:
                break

# Global client instance
_iso_client = None
_client_lock = threading.Lock()

def get_iso_client():
    """Get singleton ISO8583 client instance"""
    global _iso_client
    if _iso_client is None:
        with _client_lock:
            if _iso_client is None:
                _iso_client = ISO8583Client()
    return _iso_client

# Legacy compatibility function
def send_iso8583_request(card_number, amount, merchant_id, auth_code, protocol_version=None):
    """Legacy function for backward compatibility"""
    client = get_iso_client()
    return client.send_authorization_request(
        card_number, amount, merchant_id, auth_code, protocol_version
    )

