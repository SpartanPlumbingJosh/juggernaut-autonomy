# core/verification/github_verifier.py

import logging
import time
from typing import Any, Dict, List, Optional, TypedDict

import requests
from requests import Response
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

GITHUB_API_BASE_URL: str = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS: float = 10.0
MAX_REQUEST_RETRIES: int = 3
RATE_LIMIT_STATUS_CODE: int = 429
RETRY_AFTER_HEADER: