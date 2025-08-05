# bin_lookup.py - BIN to Issuer Server Mapping
import json
import os
from config import config
from logger import log_system_error

class BINLookupService:
    """Maps card BINs to their respective issuer ISO8583 servers"""
    
    def __init__(self):
        self.bin_mapping_file = "data/bin_mapping.json"
        self.bin_mapping = self._load_bin_mapping()
    
    def _load_bin_mapping(self):
        """Load BIN to server mapping"""
        try:
            if os.path.exists(self.bin_mapping_file):
                with open(self.bin_mapping_file, 'r') as f:
                    return json.load(f)
            else:
                # Create default BIN mapping for M0/M1 cards
                default_mapping = {
                    "400000": {  # Example BIN for M0 cards
                        "card_type": "M0",
                        "issuer_name": "M0 Card Issuer",
                        "iso_server_host": "m0-issuer.example.com",
                        "iso_server_port": 8583,
                        "timeout": 30,
                        "supported_protocols": ["101.1", "101.4", "101.6", "101.7", "101.8"]
                    },
                    "500000": {  # Example BIN for M1 cards
                        "card_type": "M1", 
                        "issuer_name": "M1 Card Issuer",
                        "iso_server_host": "m1-issuer.example.com",
                        "iso_server_port": 8583,
                        "timeout": 30,
                        "supported_protocols": ["201.1", "201.3", "201.5"]
                    },
                    "600000": {  # Another M0 issuer
                        "card_type": "M0",
                        "issuer_name": "Alternative M0 Issuer",
                        "iso_server_host": "alt-m0.example.com", 
                        "iso_server_port": 8583,
                        "timeout": 25,
                        "supported_protocols": ["101.1", "101.7", "101.8"]
                    }
                }
                
                # Save default mapping
                os.makedirs(os.path.dirname(self.bin_mapping_file), exist_ok=True)
                with open(self.bin_mapping_file, 'w') as f:
                    json.dump(default_mapping, f, indent=2)
                
                return default_mapping
                
        except Exception as e:
            log_system_error(e, {"context": "bin_mapping_load"})
            return {}
    
    def lookup_issuer(self, card_number):
        """
        Lookup issuer server details by card BIN
        
        Args:
            card_number (str): Full card number
            
        Returns:
            dict: Issuer server configuration or None
        """
        try:
            if not card_number or len(card_number) < 6:
                return None
            
            # Extract BIN (first 6 digits)
            bin_number = card_number[:6]
            
            # Direct BIN match
            if bin_number in self.bin_mapping:
                return self.bin_mapping[bin_number]
            
            # Try progressive BIN matching (6 digits down to 4)
            for length in range(6, 3, -1):
                partial_bin = card_number[:length]
                if partial_bin in self.bin_mapping:
                    return self.bin_mapping[partial_bin]
            
            # No match found
            return None
            
        except Exception as e:
            log_system_error(e, {"context": "bin_lookup", "card_number": f"****{card_number[-4:] if card_number else 'None'}"})
            return None
    
    def get_supported_protocols(self, card_number):
        """Get supported protocols for a card"""
        issuer_info = self.lookup_issuer(card_number)
        if issuer_info:
            return issuer_info.get("supported_protocols", [])
        return []
    
    def is_m0_card(self, card_number):
        """Check if card is M0 type"""
        issuer_info = self.lookup_issuer(card_number)
        return issuer_info and issuer_info.get("card_type") == "M0"
    
    def is_m1_card(self, card_number):
        """Check if card is M1 type"""
        issuer_info = self.lookup_issuer(card_number)
        return issuer_info and issuer_info.get("card_type") == "M1"
    
    def add_bin_mapping(self, bin_number, issuer_config):
        """Add new BIN mapping"""
        try:
            self.bin_mapping[bin_number] = issuer_config
            with open(self.bin_mapping_file, 'w') as f:
                json.dump(self.bin_mapping, f, indent=2)
            return True
        except Exception as e:
            log_system_error(e, {"context": "add_bin_mapping"})
            return False
    
    def reload_mapping(self):
        """Reload BIN mapping from file"""
        self.bin_mapping = self._load_bin_mapping()

# Global BIN lookup service
bin_lookup_service = BINLookupService()

# Convenience functions
def lookup_issuer(card_number):
    return bin_lookup_service.lookup_issuer(card_number)

def get_supported_protocols(card_number):
    return bin_lookup_service.get_supported_protocols(card_number)

def is_m0_card(card_number):
    return bin_lookup_service.is_m0_card(card_number)

def is_m1_card(card_number):
    return bin_lookup_service.is_m1_card(card_number)
