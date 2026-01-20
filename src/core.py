import logging
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Protocol, Sequence, Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

# Constants
DISCOVERY_INTERVAL_SECONDS: int = 6 * 60 * 60  # 6 hours
DEFAULT_CURRENCY: str = "USD"
DEFAULT_BUDGET_MULTIPLIER: float = 1.5
DEFAULT_DB_PATH: str = "juggernaut_discovery.db"
MIN_COMPLEXITY: int = 1
MAX_COMPLEXITY: int = 5
TOP_EXPERIMENTS_PER_CYCLE: int = 3
MIN_CAPABILITY_SCORE_FOR_EXPERIMENT: float = 0.6
MIN_EXPERIMENTS_FOR_LEARNING: int = 3
BASE_LEARNING_MIN_FACTOR: float = 0.5
BASE_LEARNING_MAX_FACTOR: float = 1.5
DEFAULT_CAPITAL_REQUIRED: float = 100.0
DEFAULT_TIME_TO_FIRST_DOLLAR: str = "weeks"
DEFAULT_COMPLEXITY: int = 3

SEARCH_QUERIES: Sequence[str] = (
    "how to make money online",
    "passive income ideas",
    "digital arbitrage opportunities",
    "ways to make money with AI tools",
    "online business ideas with low capital",
)

JUGGERNAUT_CAPABILITIES: Sequence[str] = (
    "web_search",
    "browser_automation",
    "email",
    "social_media",
    "sheets",
    "ai_generation",
    "code_generation",
    "storage",
    "database",
)

UNSUPPORTED_REQUIREMENTS_KEYWORDS: Sequence[str] = (
    "phone",
    "phone call",
    "call clients",
    "cold call",
    "in-person",
    "physical",
    "warehouse",
    "storefront",
    "retail location",
    "drive",
    "driving",
    "car",
    "vehicle",
    "deliver",
    "shipping center",
    "bank branch",
    "atm",
    "cash deposit",
    "inventory storage",
)

OPPORTUNITY_TABLE_NAME: str = "experiments"
RESULTS_TABLE_NAME: str = "experiment_results"


@dataclass
class SearchResult:
    """Represents a single search result from the web."""

    title: str
    snippet: str
    url: str
    content: str


class SearchClient(Protocol):
    """Protocol for a web search client."""

    def search(self, query: str, max_results: int) -> List[SearchResult]:
        """Search the web for the given query.

        Args:
            query: Search query string.
            max_results: Maximum number of search results to return.

        Returns:
            A list of SearchResult objects.
        """
        ...


@dataclass
class Opportunity:
    """Represents a discrete, actionable opportunity."""

    name: str
    description: str
    time_to_first_dollar: str
    capital_required: float
    capital_currency: str
    complexity_rating: int
    tools_skills: List[str]
    first_action_step: str
    category: str
    source_url: Optional[str]
    discovered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class ScoredOpportunity:
    """Represents an opportunity with capability-based scoring."""

    opportunity: Opportunity
    capability_score: float
    risk_score: float
    overall_score: float
    missing_capabilities: List[str]


@dataclass
class Experiment:
    """Represents an experiment created from an opportunity."""

    id: Optional[int]
    opportunity_name: str
    category: str
    hypothesis: str
    success_criteria: str
    budget_cap: float
    time_to_first_dollar: str
    status: str
    first_task: str
    created_at: datetime
    updated_at: datetime


@dataclass
class CategoryStats:
    """Aggregated performance statistics for a category."""

    category: str
    total_experiments: int
    successes: int
    failures: int
    average_revenue: float


class DummySearchClient:
    """Fallback search client that returns static sample data.

    This allows the module to run in environments where no real
    web search integration is available. In production JUGGERNAUT,
    this should be replaced by an MCP-backed implementation.
    """

    SAMPLE_RESULTS: Sequence[SearchResult] = (
        SearchResult(
            title="10 Ways to Make Money Online",
            snippet="From affiliate marketing to digital products...",
            url="https://example.com/make-money-online",
            content=(
                "- Start an affiliate blog reviewing software tools.\n"
                "- Create and sell Notion or spreadsheet templates.\n"
                "- Launch a low-content ebook on Amazon Kindle.\n"
                "- Offer SEO content writing as a freelancer.\n"
                "- Run Facebook ad arbitrage for local businesses.\n"
                "- Flip domain names for profit.\n"
                "- Create a niche newsletter and sell sponsorships.\n"
                "- Build a micro-SaaS using no-code tools.\n"
            ),
        ),
        SearchResult(
            title="Passive Income Ideas with Low Capital",
            snippet="Low-risk, online passive income opportunities...",
            url="https://example.com/passive-income",
            content=(
                "1. Create a digital course on a niche topic.\n"
                "2. Sell stock photos or digital assets.\n"
                "3. Build an automated dropshipping store.\n"
                "4. Set up an automated YouTube channel using AI.\n"
            ),
        ),
    )

    def search(self, query: str, max_results: int) -> List[SearchResult]:
        """Return static search results.

        Args:
            query: Search query (ignored in dummy implementation).
            max_results: Maximum number of results to return.

        Returns:
            A list of sample SearchResult objects.
        """
        LOGGER.warning(
            "Using DummySearchClient. Replace with real search integration for production."
        )
        return list(self.SAMPLE_RESULTS)[:max_results]


class DiscoveryRepository:
    """Persistence layer for discovery experiments and results."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH) -> None:
        """Initialize the repository.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Obtain a new SQLite connection.

        Returns:
            A sqlite3.Connection instance.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {OPPORTUNITY_TABLE_NAME} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        opportunity_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        hypothesis TEXT NOT NULL,
                        success_criteria TEXT NOT NULL,
                        budget_cap REAL NOT NULL,
                        time_to_first_dollar TEXT NOT NULL,
                        status TEXT NOT NULL,
                        first_task TEXT NOT NULL,
                        source_url TEXT,
                        discovered_at TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(opportunity_name, first_task)
                    )
                    """
                )
                cursor.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {RESULTS_TABLE_NAME} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        experiment_id INTEGER NOT NULL,
                        opportunity_name TEXT NOT NULL,
                        category TEXT NOT NULL,
                        outcome TEXT NOT NULL,
                        revenue REAL NOT NULL DEFAULT 0,
                        timestamp TEXT NOT NULL,
                        FOREIGN KEY (experiment_id) REFERENCES {OPPORTUNITY_TABLE_NAME}(id)
                    )
                    """
                )
                conn.commit()
        except sqlite3.Error as exc:
            LOGGER.exception("Error initializing database: %s", exc)
            raise

    def experiment_exists_for_opportunity(
        self,
        opportunity_name: str,
        first_task: str,
    ) -> bool:
        """Check if an experiment already exists for the given opportunity.

        Args:
            opportunity_name: Name of the opportunity.
            first_task: The first task associated with the opportunity.

        Returns:
            True if an experiment already exists, False otherwise.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT 1 FROM {OPPORTUNITY_TABLE_NAME}
                    WHERE opportunity_name = ? AND first_task = ?
                    LIMIT 1
                    """,
                    (opportunity_name, first_task),
                )
                row = cursor.fetchone()
                return row is not None
        except sqlite3.Error as exc:
            LOGGER.exception("Error checking experiment existence: %s", exc)
            raise

    def save_experiment(self, experiment: Experiment, source_url: Optional[str], discovered_at: datetime) -> int:
        """Persist a new