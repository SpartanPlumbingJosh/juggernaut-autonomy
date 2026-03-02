"""
Automated execution of winning strategies from analysis.
Handles authentication, task execution with respect to rate limits,
payment processing, and robust error handling with exponential backoff.
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StrategyAutomator:
    """Automate execution of profitable strategies while respecting platform limits."""

    def __init__(
        self,
        api_key: str,
        payment_address: str,
        base_url: str = "https://api.example.com/v1",
        max_retries: int = 5,
        rate_limit_rpm: int = 60,
    ):
        """
        Initialize strategy automator with API credentials and payment details.

        Args:
            api_key: API authentication key
            payment_address: Crypto/partner payment address for revenue
            base_url: Base API URL
            max_retries: Max retry attempts for failed requests
            rate_limit_rpm: Max requests per minute to respect API limits
        """
        self.api_key = api_key
        self.payment_address = payment_address
        self.base_url = base_url.rstrip("/")
        self.max_retries = max_retries
        self.rate_limit_rpm = rate_limit_rpm
        
        # Initialize rate limiting tracking
        self._last_request_time = None
        self._request_count = 0
        
        # Configure retry strategy
        self.session = requests.Session()
        retries = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "POST"]
        )
        self.session.mount("https://", HTTPAdapter(max_retries=retries))

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make authenticated API request with rate limiting."""
        # Rate limit handling
        current_time = datetime.now()
        if self._last_request_time:
            time_since_last = (current_time - self._last_request_time).total_seconds()
            if time_since_last < 60:
                if self._request_count >= self.rate_limit_rpm:
                    delay = 60 - time_since_last
                    logger.warning(f"Rate limiting - waiting {delay:.1f} seconds")
                    time.sleep(delay)
                    self._request_count = 0
                    self._last_request_time = datetime.now()
        
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            logger.info(f"Making {method} request to {url}")
            self._last_request_time = datetime.now()
            self._request_count += 1

            if method.upper() == "GET":
                response = self.session.get(url, headers=headers, params=data)
            elif method.upper() == "POST":
                response = self.session.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {str(e)}")
            raise

    def execute_content_generation(
        self, 
        content_type: str,
        topic: str,
        word_count: int = 800,
        keywords: Optional[List[str]] = None
    ) -> Dict:
        """Execute automated content generation strategy."""
        payload = {
            "content_type": content_type,
            "topic": topic,
            "word_count": word_count,
            "keywords": keywords or [],
            "payment_address": self.payment_address
        }
        
        return self._make_request("POST", "/content/generate", payload)

    def execute_microtasks(
        self,
        task_type: str,
        amount: float,
        quantity: int = 1,
        params: Optional[Dict] = None
    ) -> Dict:
        """Execute microtask completion strategy."""
        payload = {
            "task_type": task_type,
            "amount": amount,
            "quantity": quantity,
            "params": params or {},
            "payment_address": self.payment_address
        }
        
        return self._make_request("POST", "/tasks/execute", payload)

    def execute_arbitrage(
        self,
        exchange_pairs: List[str],
        amount: float,
        max_cycles: int = 3
    ) -> Dict:
        """Execute crypto/fiat arbitrage strategy with safeguards."""
        if max_cycles > 5:
            raise ValueError("Max cycles limited to 5 per platform terms")
            
        payload = {
            "exchange_pairs": exchange_pairs,
            "amount": amount,
            "max_cycles": max_cycles,
            "payment_address": self.payment_address
        }
        
        return self._make_request("POST", "/arbitrage/execute", payload)

    def get_balance(self) -> Dict:
        """Get current account balance."""
        return self._make_request("GET", "/account/balance")

    def withdraw_funds(self, amount: float, address: Optional[str] = None) -> Dict:
        """Withdraw funds to specified address or default payment address."""
        payload = {
            "amount": amount,
            "address": address or self.payment_address
        }
        return self._make_request("POST", "/account/withdraw", payload)


def create_automator_from_config(config_path: str) -> StrategyAutomator:
    """Create automator instance from JSON config file."""
    with open(config_path) as f:
        config = json.load(f)
    
    return StrategyAutomator(
        api_key=config["api_key"],
        payment_address=config["payment_address"],
        base_url=config.get("base_url"),
        max_retries=config.get("max_retries", 5),
        rate_limit_rpm=config.get("rate_limit_rpm", 60)
    )
