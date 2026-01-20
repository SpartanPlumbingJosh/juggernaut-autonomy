import logging
import sqlite3
from datetime import datetime, timezone

import pytest

import core
from core import (
    CategoryStats,
    DiscoveryRepository,
    DummySearchClient,
    Experiment,
    JUGGERNAUT_CAPABILITIES,
    MIN_COMPLEXITY,
    MAX_COMPLEXITY,
    MIN_CAPABILITY_SCORE_FOR_EXPERIMENT,
    MIN_EXPERIMENTS_FOR_LEARNING,
    Opportunity,
    OPPORTUNITY_TABLE_NAME,
    RESULTS_TABLE_NAME,
    ScoredOpportunity,
    SearchResult,
)


@pytest.fixture
def dummy_search_client() -> DummySearchClient:
    return DummySearchClient()


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_discovery.db")


@pytest.fixture
def repository(db_path) -> DiscoveryRepository:
    return DiscoveryRepository(db_path=db_path)


def test_search_result_dataclass_fields():
    result = SearchResult(
        title="Title",
        snippet="Snippet",
        url="https://example.com",
        content="Content",
    )
    assert result.title == "Title"
    assert result.snippet == "Snippet"
    assert result.url == "https://example.com"
    assert result.content == "Content"


def test_opportunity_default_discovered_at_timezone_aware():
    opp = Opportunity(
        name="Test Opp",
        description="Desc",
        time_to_first_dollar="days",
        capital_required=50.0,
        capital_currency="USD",
        complexity_rating=3,
        tools_skills=["skill1"],
        first_action_step="Do something",
        category="test",
        source_url=None,
    )
    assert isinstance(opp.discovered_at, datetime)
    assert opp.discovered_at.tzinfo is not None
    # check close to "now"
    now = datetime.now(timezone.utc)
    assert abs((now - opp.discovered_at).total_seconds()) < 5


def test_scored_opportunity_dataclass_links_opportunity_and_scores():
    opp = Opportunity(
        name="Test Opp",
        description="Desc",
        time_to_first_dollar="days",
        capital_required=50.0,
        capital_currency="USD",
        complexity_rating=3,
        tools_skills=["skill1"],
        first_action_step="Do something",
        category="test",
        source_url="https://example.com",
    )
    scored = ScoredOpportunity(
        opportunity=opp,
        capability_score=0.8,
        risk_score=0.3,
        overall_score=0.75,
        missing_capabilities=["missing1"],
    )
    assert scored.opportunity is opp
    assert scored.capability_score == 0.8
    assert scored.risk_score == 0.3
    assert scored.overall_score == 0.75
    assert scored.missing_capabilities == ["missing1"]


def test_experiment_dataclass_creation():
    created = datetime(2024, 1, 1, tzinfo=timezone.utc)
    updated = datetime(2024, 1, 2, tzinfo=timezone.utc)
    exp = Experiment(
        id=None,
        opportunity_name="Opp",
        category="cat",
        hypothesis="hypothesis",
        success_criteria="criteria",
        budget_cap=100.0,
        time_to_first_dollar="weeks",
        status="new",
        first_task="Do something",
        created_at=created,
        updated_at=updated,
    )
    assert exp.id is None
    assert exp.opportunity_name == "Opp"
    assert exp.category == "cat"
    assert exp.hypothesis == "hypothesis"
    assert exp.success_criteria == "criteria"
    assert exp.budget_cap == 100.0
    assert exp.time_to_first_dollar == "weeks"
    assert exp.status == "new"
    assert exp.first_task == "Do something"
    assert exp.created_at is created
    assert exp.updated_at is updated


def test_category_stats_dataclass_creation():
    stats = CategoryStats(
        category="email_marketing",
        total_experiments=10,
        successes=4,
        failures=6,
        average_revenue=123.45,
    )
    assert stats.category == "email_marketing"
    assert stats.total_experiments == 10
    assert stats.successes == 4
    assert stats.failures == 6
    assert stats.average_revenue == 123.45


def test_dummy_search_client_returns_sample_results(dummy_search_client, caplog):
    with caplog.at_level(logging.WARNING):
        results = dummy_search_client.search("any query", max_results=10)

    assert isinstance(results, list)
    assert len(results) == len(DummySearchClient.SAMPLE_RESULTS)
    assert all(isinstance(r, SearchResult) for r in results)
    assert "Using DummySearchClient" in caplog.text


def test_dummy_search_client_respects_max_results_less_than_sample(dummy_search_client):
    max_results = 1
    results = dummy_search_client.search("query", max_results=max_results)
    assert len(results) == max_results
    assert results[0].title == DummySearchClient.SAMPLE_RESULTS[0].title


def test_dummy_search_client_respects_max_results_greater_than_sample(dummy_search_client):
    max_results = len(DummySearchClient.SAMPLE_RESULTS) + 5
    results = dummy_search_client.search("query", max_results=max_results)
    # Should not exceed number of sample results
    assert len(results) == len(DummySearchClient.SAMPLE_RESULTS)


def test_dummy_search_client_with_zero_max_results_returns_empty(dummy_search_client):
    results = dummy_search_client.search("query", max_results=0)
    assert results == []


def test_dummy_search_client_with_negative_max_results_returns_sliced(dummy_search_client):
    # Python slicing with negative end index should drop items from the end
    full_count = len(DummySearchClient.SAMPLE_RESULTS)
    results = dummy_search_client.search("query", max_results=-1)
    assert len(results) == max(0, full_count - 1)


def test_discovery_repository_initializes_db_and_tables_exist(db_path):
    repo = DiscoveryRepository(db_path=db_path)
    with repo._get_connection() as conn:  # accessing private for verification
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        table_names = {row["name"] for row in cursor.fetchall()}

    assert OPPORTUNITY_TABLE_NAME in table_names
    assert RESULTS_TABLE_NAME in table_names


def test__get_connection_uses_row_factory(repository):
    with repository._get_connection() as conn:  # private for verification
        assert conn.row_factory == sqlite3.Row


def _insert_experiment_row(repo: DiscoveryRepository, opportunity_name: str, first_task: str):
    now = datetime.now(timezone.utc).isoformat()
    with repo._get_connection() as conn:
        conn.execute(
            f"""
            INSERT INTO {OPPORTUNITY_TABLE_NAME} (
                opportunity_name,
                category,
                hypothesis,
                success_criteria,
                budget_cap,
                time_to_first_dollar,
                status,
                first_task,
                source_url,
                discovered_at,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                opportunity_name,
                "test_category",
                "Test hypothesis",
                "Test success",
                100.0,
                "weeks",
                "new",
                first_task,
                "https://example.com",
                now,
                now,
                now,
            ),
        )
        conn.commit()


def test_experiment_exists_for_opportunity_returns_false_when_not_found(repository):
    exists = repository.experiment_exists_for_opportunity(
        opportunity_name="Nonexistent",
        first_task="Do something",
    )
    assert exists is False


def test_experiment_exists_for_opportunity_returns_true_when_found(repository):
    opportunity_name = "Existing Opp"
    first_task = "Do something"
    _insert_experiment_row(repository, opportunity_name, first_task)

    exists = repository.experiment_exists_for_opportunity(
        opportunity_name=opportunity_name,
        first_task=first_task,
    )
    assert exists is True


def test_experiment_exists_for_opportunity_uses_exact_match(repository):
    opportunity_name = "Case Sensitive Opp"
    first_task = "Task A"
    _insert_experiment_row(repository, opportunity_name, first_task)

    # Slightly different name and task should not match
    assert not repository.experiment_exists_for_opportunity(
        opportunity_name=opportunity_name.lower(),
        first_task=first_task,
    )
    assert not repository.experiment_exists_for_opportunity(
        opportunity_name=opportunity_name,
        first_task=first_task + " extra",
    )


def test_experiment_exists_for_opportunity_logs_and_raises_on_sqlite_error(repository, monkeypatch, caplog):
    def failing_get_connection():
        raise sqlite3.Error("Simulated DB error")

    monkeypatch.setattr(repository, "_get_connection", failing_get_connection)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.Error):
            repository.experiment_exists_for_opportunity(
                opportunity_name="Opp",
                first_task="Task",
            )

    assert "Error checking experiment existence" in caplog.text


def test_discovery_repository_init_logs_and_raises_on_init_db_error(monkeypatch, caplog, db_path):
    def failing_connect(*args, **kwargs):
        raise sqlite3.Error("Simulated init error")

    # Patch the sqlite3.connect used inside the core module
    monkeypatch.setattr(core.sqlite3, "connect", failing_connect)

    with caplog.at_level(logging.ERROR):
        with pytest.raises(sqlite3.Error):
            DiscoveryRepository(db_path=db_path)

    assert "Error initializing database" in caplog.text


def test_constants_have_expected_constraints():
    assert isinstance(JUGGERNAUT_CAPABILITIES, tuple)
    assert MIN_COMPLEXITY <= MAX_COMPLEXITY
    assert 0.0 < MIN_CAPABILITY_SCORE_FOR_EXPERIMENT <= 1.0
    assert MIN_EXPERIMENTS_FOR_LEARNING >= 1