import importlib
import sys
import uuid
import logging
from typing import List, Dict

import pytest

import core


@pytest.fixture
def sample_search_result() -> core.SearchResult:
    return core.SearchResult(
        title="Test Title",
        snippet="This is a test snippet.",
        url="https://example.com/test",
    )


@pytest.fixture
def sample_opportunity() -> core.Opportunity:
    return core.Opportunity(
        id=str(uuid.uuid4()),
        name="Test Opportunity",
        description="A description of a test opportunity.",
        time_to_first_dollar="days",
        capital_required=100.0,
        complexity_rating=3,
        tools_skills=["tool1", "skill1"],
        first_action_step="Do something as the first step.",
        source_url="https://example.com/opportunity",
    )


def test_discovery_interval_seconds_value():
    assert core.DISCOVERY_INTERVAL_SECONDS == 6 * 60 * 60


def test_db_file_path_value():
    assert core.DB_FILE_PATH == "juggernaut_discovery.db"


def test_search_queries_non_empty_and_strings():
    assert isinstance(core.SEARCH_QUERIES, list)
    assert len(core.SEARCH_QUERIES) > 0
    for query in core.SEARCH_QUERIES:
        assert isinstance(query, str)
        assert query.strip() != ""


def test_max_search_results_and_experiments_constants():
    assert core.MAX_SEARCH_RESULTS_PER_QUERY == 10
    assert core.MAX_EXPERIMENTS_PER_CYCLE == 3
    assert core.MIN_SCORE_FOR_EXPERIMENT == pytest.approx(0.4)


def test_default_capital_and_complexity_constants():
    assert core.DEFAULT_CAPITAL_REQUIRED == pytest.approx(50.0)
    assert core.DEFAULT_COMPLEXITY_RATING == 3


def test_budget_thresholds_and_caps():
    assert core.BASE_BUDGET_CAP == pytest.approx(100.0)
    assert core.LOW_CAPITAL_THRESHOLD == pytest.approx(50.0)
    assert core.MEDIUM_CAPITAL_THRESHOLD == pytest.approx(200.0)
    assert core.LOW_CAPITAL_THRESHOLD < core.MEDIUM_CAPITAL_THRESHOLD <= core.BASE_BUDGET_CAP * 3


def test_scoring_weights_sum_reasonable():
    total_weight = (
        core.CAPABILITY_WEIGHT
        + core.COMPLEXITY_WEIGHT
        + core.TIME_WEIGHT
        + core.CAPITAL_WEIGHT
        + core.LEARNING_WEIGHT
    )
    # Not necessarily 1.0, but should be positive and not absurd
    assert total_weight > 0
    assert total_weight < 5.0


def test_time_score_map_contents_and_order():
    expected_keys = {"hours", "days", "weeks", "months"}
    assert set(core.TIME_SCORE_MAP.keys()) == expected_keys
    assert core.TIME_SCORE_MAP["hours"] < core.TIME_SCORE_MAP["days"] < core.TIME_SCORE_MAP["weeks"] < core.TIME_SCORE_MAP["months"]


def test_duckduckgo_search_url_and_user_agent():
    assert core.DUCKDUCKGO_SEARCH_URL.startswith("https://duckduckgo.com")
    assert "JuggernautBot/1.0" in core.USER_AGENT
    assert core.USER_AGENT.startswith("Mozilla/5.0")


def test_opportunity_type_keywords_structure():
    assert isinstance(core.OPPORTUNITY_TYPE_KEYWORDS, dict)
    assert len(core.OPPORTUNITY_TYPE_KEYWORDS) > 0
    for key, keywords in core.OPPORTUNITY_TYPE_KEYWORDS.items():
        assert isinstance(key, str)
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        for kw in keywords:
            assert isinstance(kw, str)
            assert kw.strip() != ""


def test_capability_keywords_structure():
    assert isinstance(core.CAPABILITY_KEYWORDS, dict)
    assert len(core.CAPABILITY_KEYWORDS) > 0
    for key, keywords in core.CAPABILITY_KEYWORDS.items():
        assert isinstance(key, str)
        assert isinstance(keywords, list)
        assert len(keywords) > 0
        for kw in keywords:
            assert isinstance(kw, str)
            assert kw.strip() != ""


def test_blocked_physical_keywords_list():
    assert isinstance(core.BLOCKED_PHYSICAL_KEYWORDS, list)
    assert "visit" in core.BLOCKED_PHYSICAL_KEYWORDS
    for kw in core.BLOCKED_PHYSICAL_KEYWORDS:
        assert isinstance(kw, str)
        assert kw.strip() != ""


def test_blocked_phone_keywords_list():
    assert isinstance(core.BLOCKED_PHONE_KEYWORDS, list)
    assert "call" in core.BLOCKED_PHONE_KEYWORDS
    for kw in core.BLOCKED_PHONE_KEYWORDS:
        assert isinstance(kw, str)
        assert kw.strip() != ""


def test_blocked_bank_keywords_list():
    assert isinstance(core.BLOCKED_BANK_KEYWORDS, list)
    assert "open a bank account" in core.BLOCKED_BANK_KEYWORDS
    for kw in core.BLOCKED_BANK_KEYWORDS:
        assert isinstance(kw, str)
        assert kw.strip() != ""


def test_search_result_dataclass_fields(sample_search_result: core.SearchResult):
    sr = sample_search_result
    assert sr.title == "Test Title"
    assert sr.snippet == "This is a test snippet."
    assert sr.url == "https://example.com/test"


def test_search_result_equality():
    sr1 = core.SearchResult(
        title="Same",
        snippet="Same snippet",
        url="https://example.com",
    )
    sr2 = core.SearchResult(
        title="Same",
        snippet="Same snippet",
        url="https://example.com",
    )
    sr3 = core.SearchResult(
        title="Different",
        snippet="Different snippet",
        url="https://example.com/other",
    )
    assert sr1 == sr2
    assert sr1 != sr3


def test_opportunity_dataclass_minimal_required_fields(sample_opportunity: core.Opportunity):
    opp = sample_opportunity
    assert isinstance(opp.id, str)
    assert opp.name == "Test Opportunity"
    assert opp.description.startswith("A description of a test opportunity")
    assert opp.time_to_first_dollar == "days"
    assert opp.capital_required == pytest.approx(100.0)
    assert opp.complexity_rating == 3
    assert isinstance(opp.tools_skills, list)
    assert "tool1" in opp.tools_skills
    assert opp.first_action_step.startswith("Do something")
    assert opp.source_url == "https://example.com/opportunity"


def test_opportunity_default_flags_and_optional_fields():
    opp = core.Opportunity(
        id="id-123",
        name="Name",
        description="Desc",
        time_to_first_dollar="hours",
        capital_required=10.0,
        complexity_rating=1,
        tools_skills=[],
        first_action_step="Start",
        source_url="https://example.com",
    )
    # These should rely on their default values
    assert opp.requires_physical_presence is False
    assert opp.requires_phone_calls is False
    assert opp.requires_bank_access is False
    assert opp.opportunity_type is None


def test_opportunity_can_override