import logging
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional, Protocol, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

# Configure module-level logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

# Constants
DISCOVERY_INTERVAL_SECONDS: int = 6 * 60 * 60  # 6 hours
DB_FILE_PATH: str = "juggernaut_discovery.db"

SEARCH_QUERIES: List[str] = [
    "how to make money online",
    "passive income ideas",
    "digital arbitrage",
    "online side hustle ideas",
    "automated online businesses",
]

MAX_SEARCH_RESULTS_PER_QUERY: int = 10
MAX_EXPERIMENTS_PER_CYCLE: int = 3
MIN_SCORE_FOR_EXPERIMENT: float = 0.4

DEFAULT_CAPITAL_REQUIRED: float = 50.0
DEFAULT_COMPLEXITY_RATING: int = 3

BASE_BUDGET_CAP: float = 100.0
LOW_CAPITAL_THRESHOLD: float = 50.0
MEDIUM_CAPITAL_THRESHOLD: float = 200.0

# Scoring weights
CAPABILITY_WEIGHT: float = 0.5
COMPLEXITY_WEIGHT: float = 0.2
TIME_WEIGHT: float = 0.2
CAPITAL_WEIGHT: float = 0.1
LEARNING_WEIGHT: float = 0.2

# Time scores (lower is better)
TIME_SCORE_MAP: Dict[str, int] = {
    "hours": 1,
    "days": 2,
    "weeks": 3,
    "months": 4,
}

DUCKDUCKGO_SEARCH_URL: str = "https://duckduckgo.com/html/"

USER_AGENT: str = (
    "Mozilla/5.0 (compatible; JuggernautBot/1.0; +https://example.com/bot)"
)

OPPORTUNITY_TYPE_KEYWORDS: Dict[str, List[str]] = {
    "affiliate_marketing": ["affiliate"],
    "dropshipping": ["dropshipping", "drop shipping"],
    "print_on_demand": ["print on demand", "pod business"],
    "online_courses": ["online course", "create a course", "sell a course"],
    "freelancing": ["freelance", "upwork", "fiverr"],
    "content_sites": ["blog", "niche site", "content site"],
    "social_media": ["instagram", "tiktok", "youtube", "twitter", "x.com", "social media"],
    "email_marketing": ["email list", "newsletter", "email marketing"],
    "saas": ["saas", "subscription software", "software as a service"],
}

CAPABILITY_KEYWORDS: Dict[str, List[str]] = {
    "web_search": ["research", "find", "search"],
    "browser_automation": ["scrape", "scraping", "automation", "automate"],
    "email": ["email", "newsletter", "mailing list"],
    "social_media": ["social media", "twitter", "x.com", "instagram", "tiktok", "facebook", "youtube"],
    "sheets": ["spreadsheet", "sheets", "excel", "google sheets"],
    "ai_generation": ["ai", "generate content", "text generation"],
    "code_generation": ["script", "bot", "automation script", "coding"],
    "storage": ["store data", "file storage"],
    "database": ["database", "structured data"],
}

BLOCKED_PHYSICAL_KEYWORDS: List[str] = [
    "visit",
    "in person",
    "storefront",
    "warehouse",
    "physical inventory",
    "drive",
    "delivery truck",
]

BLOCKED_PHONE_KEYWORDS: List[str] = [
    "call",
    "phone",
    "cold call",
    "telemarketing",
]

BLOCKED_BANK_KEYWORDS: List[str] = [
    "open a bank account",
    "wire transfer",
    "visit your bank",
    "loan officer",
    "mortgage broker",
]


@dataclass
class SearchResult:
    """Represents a single web search result."""

    title: str
    snippet: str
    url: str


@dataclass
class Opportunity:
    """Represents a discrete money-making opportunity."""

    id: str
    name: str
    description: str
    time_to_first_dollar: str
    capital_required: float
    complexity_rating: int
    tools_skills: List[str]
    first_action_step: str
    source_url: str
    requires_physical_presence: bool = False
    requires_phone_calls: bool = False
    requires_bank_access: bool = False
    opportunity_type: Optional[str] = None
    created