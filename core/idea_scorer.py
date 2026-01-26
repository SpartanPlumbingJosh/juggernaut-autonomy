from __future__ import annotations

from typing import Any, Dict


SCORING_FACTORS = {
    "capital_required": {"weight": 0.15, "prefer": "low"},
    "time_to_first_dollar_days": {"weight": 0.25, "prefer": "low"},
    "effort_hours": {"weight": 0.15, "prefer": "low"},
    "scalability": {"weight": 0.20, "prefer": "high"},
    "risk_level": {"weight": 0.10, "prefer": "low"},
    "capability_fit": {"weight": 0.15, "prefer": "high"},
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _score_low_better(value: float, good: float, bad: float) -> float:
    if value <= good:
        return 100.0
    if value >= bad:
        return 0.0
    return _clamp(100.0 * (1.0 - ((value - good) / (bad - good))))


def _score_high_better(value: float, good: float, bad: float) -> float:
    if value >= good:
        return 100.0
    if value <= bad:
        return 0.0
    return _clamp(100.0 * ((value - bad) / (good - bad)))


class IdeaScorer:
    """Score ideas on capital/time/effort/scalability/risk/capability fit."""

    def score_idea(self, idea: Dict[str, Any]) -> Dict[str, Any]:
        estimates = idea.get("estimates") or {}

        capital = float(estimates.get("capital_required", 50) or 50)
        ttf = float(estimates.get("time_to_first_dollar_days", 30) or 30)
        effort = float(estimates.get("effort_hours", 20) or 20)
        scalability = float(estimates.get("scalability", 5) or 5)
        risk = float(estimates.get("risk_level", 5) or 5)
        fit = float(estimates.get("capability_fit", 5) or 5)

        breakdown: Dict[str, float] = {
            "capital_required": _score_low_better(capital, good=0, bad=200),
            "time_to_first_dollar": _score_low_better(ttf, good=3, bad=60),
            "effort_hours": _score_low_better(effort, good=2, bad=80),
            "scalability": _score_high_better(scalability, good=10, bad=1),
            "risk_level": _score_low_better(risk, good=1, bad=10),
            "capability_fit": _score_high_better(fit, good=10, bad=1),
        }

        score = 0.0
        score += breakdown["capital_required"] * SCORING_FACTORS["capital_required"]["weight"]
        score += breakdown["time_to_first_dollar"] * SCORING_FACTORS["time_to_first_dollar_days"]["weight"]
        score += breakdown["effort_hours"] * SCORING_FACTORS["effort_hours"]["weight"]
        score += breakdown["scalability"] * SCORING_FACTORS["scalability"]["weight"]
        score += breakdown["risk_level"] * SCORING_FACTORS["risk_level"]["weight"]
        score += breakdown["capability_fit"] * SCORING_FACTORS["capability_fit"]["weight"]

        return {
            "score": round(_clamp(score), 2),
            "breakdown": {k: round(v, 2) for k, v in breakdown.items()},
        }
