from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class RevenueIdea:
    title: str
    description: str
    hypothesis: str
    estimates: Dict[str, Any]


class IdeaGenerator:
    """Generates revenue opportunities based on available capabilities."""

    def generate_ideas(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        assets = context.get("assets") or {}
        constraints = context.get("constraints") or {}

        max_budget = float(constraints.get("max_budget", 50) or 50)
        risk_tolerance = str(constraints.get("risk_tolerance", "low") or "low")

        business = str(assets.get("primary_business", "Spartan Plumbing") or "Spartan Plumbing")

        ideas: List[RevenueIdea] = [
            RevenueIdea(
                title="Automated review response service for local businesses",
                description=(
                    "Offer a monthly service that drafts and posts review responses for Google/Yelp. "
                    "Use templated tone + simple QA; sell to other trades locally."
                ),
                hypothesis="Can convert 1 paying customer at $49/mo within 14 days",
                estimates={
                    "capital_required": min(20.0, max_budget),
                    "time_to_first_dollar_days": 14,
                    "effort_hours": 8,
                    "scalability": 7,
                    "risk_level": 3 if risk_tolerance == "low" else 5,
                    "capability_fit": 8,
                    "asset": business,
                },
            ),
            RevenueIdea(
                title="Lead qualification chatbot for trades",
                description=(
                    "A website widget / SMS flow that qualifies leads (service type, urgency, address) "
                    "and schedules calls. Start as a paid setup + monthly fee."
                ),
                hypothesis="Can book 3 qualified leads for a single trade business within 14 days",
                estimates={
                    "capital_required": min(50.0, max_budget),
                    "time_to_first_dollar_days": 21,
                    "effort_hours": 20,
                    "scalability": 8,
                    "risk_level": 5,
                    "capability_fit": 6,
                    "asset": business,
                },
            ),
            RevenueIdea(
                title="Operational dashboard setup as-a-service",
                description=(
                    "Setup a lightweight ops dashboard for small service businesses: job volume, calls, reviews, "
                    "simple KPIs. Sell as setup + retainer."
                ),
                hypothesis="Can sell 1 dashboard setup at $299 within 30 days",
                estimates={
                    "capital_required": min(0.0, max_budget),
                    "time_to_first_dollar_days": 30,
                    "effort_hours": 16,
                    "scalability": 6,
                    "risk_level": 3,
                    "capability_fit": 7,
                    "asset": business,
                },
            ),
        ]

        return [
            {
                "title": i.title,
                "description": i.description,
                "hypothesis": i.hypothesis,
                "estimates": i.estimates,
            }
            for i in ideas
        ]
