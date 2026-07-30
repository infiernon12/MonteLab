"""
License Client Module for MonteLab.

This module provides optional license checking functionality.
For Open-Source (MIT) distribution, licensing checks default to active/bypassed
unless an explicit API base URL and secret key are provided.
"""

import json
import time
import hmac
import hashlib
import random
import string
import logging
from typing import Optional, Dict, Any
from datetime import datetime
import requests

logger = logging.getLogger(__name__)


class LicenseClient:
    """Client for verifying application license with a remote licensing server."""
    
    def __init__(
        self,
        api_base_url: Optional[str] = None,
        hmac_secret_key: Optional[str] = None,
        hwid: Optional[str] = None
    ):
        self.api_base_url = api_base_url
        self.hmac_secret_key = hmac_secret_key
        self.hwid = hwid or "OPEN_SOURCE_HWID"
        self.last_check = None
        
    def _generate_hmac_signature(self, data: str) -> str:
        """Generate HMAC-SHA256 signature for request payload."""
        if not self.hmac_secret_key:
            return ""
        return hmac.new(
            self.hmac_secret_key.encode('utf-8'),
            data.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def _generate_nonce(self, length: int = 8) -> str:
        """Generate random request nonce."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=length))
    
    def check_license(self) -> bool:
        """
        Check license status.
        
        Returns:
            bool: Always True in open-source mode if no remote API URL is specified.
        """
        if not self.api_base_url or not self.hmac_secret_key:
            logger.info("Open-Source mode: Remote license server disabled, access granted.")
            return True
            
        request_data = {
            "hwid": self.hwid,
            "timestamp": int(time.time()),
            "nonce": self._generate_nonce()
        }
        
        try:
            url = f"{self.api_base_url.rstrip('/')}/license/check"
            json_data = json.dumps(request_data)
            signature = self._generate_hmac_signature(json_data)
            
            headers = {
                "Content-Type": "application/json",
                "X-Signature": signature
            }
            
            response = requests.post(url, data=json_data, headers=headers, timeout=5, verify=True)
            if response.status_code == 200:
                result = response.json()
                return result.get("is_active", False)
            else:
                logger.warning(f"License server returned HTTP status {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Failed to check license with remote server: {e}")
            return False
    
    def get_license_info(self) -> Optional[Dict[str, Any]]:
        """Retrieve detailed license info if remote server is configured."""
        if not self.api_base_url:
            return {"status": "open_source", "is_active": True}
        return None