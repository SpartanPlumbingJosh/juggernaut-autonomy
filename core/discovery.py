"""
Autonomous Opportunity Discovery System

This module implements self-directed opportunity discovery:
1. Searches the web for money-making methods (no predefined sources)
2. Extracts discrete, actionable opportunities from search results  
3. Evaluates each opportunity against JUGGERNAUT's actual capabilities
4. Creates experiments for top-scoring opportunities
5. Tracks results and learns from outcomes

The goal is TRUE AUTONOMY - the system figures out HOW to make money,
not just scan predefined sources.
"""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .database import query_db, log_execution


# =============================================================================
# JUGGERNAUT'S CAPABILITIES
# =============================================================================

# What JUGGERNAUT can actually DO with its MCP tools
JUGGERNAUT_CAPABILITIES = {
    "web_search": {
        "description": "Search the internet for information",
        "use_cases": ["research", "find opportunities", "market analysis", "competitor research"]
    },
    "browser_automation": {
        "description": "Navigate websites, fill forms, click buttons, take screenshots",
        "use_cases": ["sign up for services", "create accounts", "submit listings", "scrape data"]
    },
    "email": {
        "description": "Send, receive, and search emails",
        "use_cases": ["outreach", "follow-ups", "customer communication", "affiliate signups"]
    },
    "social_media": {
        "description": "Post to Twitter and Facebook",
        "use_cases": ["content marketing", "promotion", "brand building", "traffic generation"]
    },
    "google_sheets": {
        "description": "Read and write spreadsheets",
        "use_cases": ["data tracking", "reporting", "analysis", "record keeping"]
    },
    "ai_generation": {
        "description": "Generate text and images with AI",
        "use_cases": ["content creation", "copywriting", "image generation", "automation"]
    },
    "code_generation": {
        "description": "Write and deploy code",
        "use_cases": ["build tools", "create websites", "automate processes", "APIs"]
    },
    "file_storage": {
        "description": "Store and retrieve files",
        "use_cases": ["asset management", "backups", "content library"]
    },
    "database": {
        "description": "Store and query structured data",
        "use_cases": ["tracking", "analytics", "CRM", "inventory"]
    }
}

# What JUGGERNAUT CANNOT do (requires human intervention)
JUGGERNAUT_LIMITATIONS = [
    "physical actions",
    "phone calls",
    "face-to-face meetings", 
    "sign legal contracts",
    "access bank accounts directly",
    "make purchases over $50 without approval",
    "long-term commitments",
    "anything requiring physical presence"
]


# =============================================================================
# DISCOVERY SEARCH QUERIES
# =============================================================================

# These are the search queries the system uses to discover opportunities
DISCOVERY_QUERIES = [
    # Low-effort online income
    "easy ways to make money online 2024 low effort",
    "passive income ideas that actually work",
    "how to make money online with no experience",
    "automated income streams for beginners",
    
    # Digital arbitrage
    "digital arbitrage opportunities",
    "buy low sell high online strategies",
    "domain flipping for beginners",
    "website flipping guide",
    
    # AI-powered income
    "make money with AI tools 2024",
    "AI content creation business",
    "ChatGPT money making ideas",
    "AI automation side hustles",
    
    # Quick wins
    "make money online in 24 hours",
    "fastest ways to earn money online",
    "low capital online business ideas",
    "zero investment online income",
    
    # Specific methods
    "affiliate marketing without a website",
    "print on demand profitability",
    "dropshipping alternatives 2024",
    "digital product ideas that sell",
    
    # Platform specific
    "how to make money on Fiverr",
    "Upwork success strategies",
    "Etsy digital products guide",
    "Amazon affiliate for beginners"
]


# =============================================================================
# OPPORTUNITY EXTRACTION
# =============================================================================

def extract_opportunities_from_search(
    search_results: str,
    search_query: str
) -> List[Dict[str, Any]]:
    """
    Use AI to extract discrete, actionable opportunities from search results.
    
    Args:
        search_results: Raw search results text
        search_query: The query that produced these results
        
    Returns:
        List of extracted opportunities with metadata
    """
    # This would call the AI to parse results
    # For now, define the extraction logic
    
    extraction_prompt = f"""
    Analyze these search results and extract SPECIFIC, ACTIONABLE money-making opportunities.
    
    Search Query: {search_query}
    
    For each opportunity found, provide:
    1. NAME: Short descriptive name
    2. DESCRIPTION: What it is and how it works
    3. TIME_TO_FIRST_DOLLAR: Estimate (hours/days/weeks/months)
    4. CAPITAL_REQUIRED: Estimate in USD (0 if free)
    5. COMPLEXITY: simple/medium/complex
    6. SCALABILITY: one-time/repeatable/highly-scalable
    7. TOOLS_NEEDED: What tools/skills are required
    8. FIRST_STEP: The very first action to take
    
    Only include opportunities that:
    - Are SPECIFIC (not vague like "start a business")
    - Are ACTIONABLE (clear first step)
    - Can be done ONLINE (no physical presence required)
    - Don't require special licenses or certifications
    
    Search Results:
    {search_results[:5000]}
    """
    
    # This would be processed by AI - for now return empty
    # The actual implementation would call ai_chat tool
    return []


def score_opportunity_for_juggernaut(opportunity: Dict) -> Dict[str, Any]:
    """
    Score an opportunity based on how well JUGGERNAUT can execute it.
    
    Args:
        opportunity: The opportunity to score
        
    Returns:
        Dict with scores and reasoning
    """
    scores = {
        "time_to_first_dollar": 0,
        "capital_required": 0,
        "tool_match": 0,
        "complexity": 0,
        "scalability": 0,
        "automation_potential": 0
    }
    
    # Time to first dollar (faster = better)
    time_map = {
        "hours": 1.0,
        "days": 0.8,
        "weeks": 0.5,
        "months": 0.2
    }
    time_estimate = opportunity.get("time_to_first_dollar", "weeks").lower()
    for key, score in time_map.items():
        if key in time_estimate:
            scores["time_to_first_dollar"] = score
            break
    
    # Capital required (less = better)
    capital = opportunity.get("capital_required", 100)
    if capital == 0:
        scores["capital_required"] = 1.0
    elif capital <= 20:
        scores["capital_required"] = 0.9
    elif capital <= 50:
        scores["capital_required"] = 0.7
    elif capital <= 100:
        scores["capital_required"] = 0.5
    else:
        scores["capital_required"] = 0.3
    
    # Tool match (can JUGGERNAUT do this?)
    tools_needed = opportunity.get("tools_needed", [])
    if isinstance(tools_needed, str):
        tools_needed = [tools_needed]
    
    matched_tools = 0
    for tool in tools_needed:
        tool_lower = tool.lower()
        for cap_name, cap_info in JUGGERNAUT_CAPABILITIES.items():
            if any(use.lower() in tool_lower or tool_lower in use.lower() 
                   for use in cap_info["use_cases"]):
                matched_tools += 1
                break
    
    if tools_needed:
        scores["tool_match"] = matched_tools / len(tools_needed)
    else:
        scores["tool_match"] = 0.5  # Unknown
    
    # Complexity (simpler = better for automation)
    complexity_map = {"simple": 1.0, "medium": 0.6, "complex": 0.3}
    scores["complexity"] = complexity_map.get(
        opportunity.get("complexity", "medium").lower(), 0.5
    )
    
    # Scalability (more scalable = better)
    scale_map = {"highly-scalable": 1.0, "repeatable": 0.7, "one-time": 0.3}
    scores["scalability"] = scale_map.get(
        opportunity.get("scalability", "repeatable").lower(), 0.5
    )
    
    # Automation potential (based on whether it needs human intervention)
    first_step = opportunity.get("first_step", "").lower()
    limitations_mentioned = sum(
        1 for limit in JUGGERNAUT_LIMITATIONS 
        if limit.lower() in first_step
    )
    scores["automation_potential"] = max(0, 1.0 - (limitations_mentioned * 0.3))
    
    # Calculate weighted final score
    weights = {
        "time_to_first_dollar": 0.20,
        "capital_required": 0.15,
        "tool_match": 0.25,
        "complexity": 0.15,
        "scalability": 0.10,
        "automation_potential": 0.15
    }
    
    final_score = sum(
        scores[key] * weights[key] 
        for key in scores
    )
    
    return {
        "final_score": round(final_score, 3),
        "scores": scores,
        "weights": weights,
        "can_execute": scores["tool_match"] >= 0.5 and scores["automation_potential"] >= 0.5
    }


# =============================================================================
# DISCOVERY EXECUTION
# =============================================================================

def run_discovery_cycle(
    max_queries: int = 5,
    min_score: float = 0.6,
    create_experiments: bool = True,
    triggered_by: str = "DISCOVERY_AGENT"
) -> Dict[str, Any]:
    """
    Run a full discovery cycle:
    1. Search for money-making opportunities
    2. Extract and parse opportunities
    3. Score against JUGGERNAUT capabilities
    4. Create experiments for top scorers
    
    Args:
        max_queries: Maximum number of search queries to run
        min_score: Minimum score to create an experiment
        create_experiments: Whether to auto-create experiments
        triggered_by: Who/what triggered this cycle
        
    Returns:
        Dict with discovery results
    """
    discovery_id = str(uuid4())
    
    log_execution(
        worker_id=triggered_by,
        action="discovery.start",
        message=f"Starting discovery cycle {discovery_id}",
        output_data={"discovery_id": discovery_id, "max_queries": max_queries}
    )
    
    # Record start
    query_db(
        """
        INSERT INTO discovery_cycles (id, started_at, triggered_by, config)
        VALUES ($1, NOW(), $2, $3)
        """,
        [discovery_id, triggered_by, json.dumps({
            "max_queries": max_queries,
            "min_score": min_score,
            "create_experiments": create_experiments
        })]
    )
    
    all_opportunities = []
    queries_run = 0
    
    # Rotate through queries (don't always start at the same one)
    import random
    queries_to_run = random.sample(
        DISCOVERY_QUERIES, 
        min(max_queries, len(DISCOVERY_QUERIES))
    )
    
    for query in queries_to_run:
        queries_run += 1
        
        # This would call web_search MCP tool
        # search_results = mcp.web_search(query)
        
        # For now, log intent
        log_execution(
            worker_id=triggered_by,
            action="discovery.search",
            message=f"Would search: {query}",
            output_data={"query": query, "discovery_id": discovery_id}
        )
        
        # Extract opportunities from results
        # opportunities = extract_opportunities_from_search(search_results, query)
        
        # Score each opportunity
        # for opp in opportunities:
        #     score_result = score_opportunity_for_juggernaut(opp)
        #     opp["score"] = score_result
        #     all_opportunities.append(opp)
    
    # Sort by score
    all_opportunities.sort(
        key=lambda x: x.get("score", {}).get("final_score", 0),
        reverse=True
    )
    
    # Filter to top scorers
    qualified = [
        opp for opp in all_opportunities 
        if opp.get("score", {}).get("final_score", 0) >= min_score
        and opp.get("score", {}).get("can_execute", False)
    ]
    
    experiments_created = []
    
    if create_experiments:
        for opp in qualified[:3]:  # Top 3
            exp_result = create_experiment_from_opportunity(opp, discovery_id)
            if exp_result.get("success"):
                experiments_created.append(exp_result["experiment_id"])
    
    # Record completion
    query_db(
        """
        UPDATE discovery_cycles 
        SET completed_at = NOW(),
            queries_run = $2,
            opportunities_found = $3,
            opportunities_qualified = $4,
            experiments_created = $5,
            status = 'completed'
        WHERE id = $1
        """,
        [
            discovery_id,
            queries_run,
            len(all_opportunities),
            len(qualified),
            json.dumps(experiments_created)
        ]
    )
    
    log_execution(
        worker_id=triggered_by,
        action="discovery.complete",
        message=f"Discovery cycle complete: {len(all_opportunities)} found, {len(qualified)} qualified, {len(experiments_created)} experiments created",
        output_data={
            "discovery_id": discovery_id,
            "opportunities_found": len(all_opportunities),
            "qualified": len(qualified),
            "experiments": experiments_created
        }
    )
    
    return {
        "success": True,
        "discovery_id": discovery_id,
        "queries_run": queries_run,
        "opportunities_found": len(all_opportunities),
        "opportunities_qualified": len(qualified),
        "experiments_created": experiments_created,
        "top_opportunities": qualified[:5]
    }


def create_experiment_from_opportunity(
    opportunity: Dict,
    discovery_id: str
) -> Dict[str, Any]:
    """
    Create an experiment from a discovered opportunity.
    
    Args:
        opportunity: The scored opportunity
        discovery_id: Reference to the discovery cycle
        
    Returns:
        Dict with experiment details
    """
    experiment_id = str(uuid4())
    
    name = opportunity.get("name", "Unnamed Opportunity")
    description = opportunity.get("description", "")
    first_step = opportunity.get("first_step", "Research and validate")
    capital = opportunity.get("capital_required", 0)
    
    # Create hypothesis
    hypothesis = f"We can generate revenue by {name.lower()} within 30 days with minimal capital investment."
    
    # Define success criteria
    success_criteria = {
        "minimum_revenue": max(capital * 2, 10),  # At least 2x ROI or $10
        "max_days": 30,
        "max_hours_invested": 20
    }
    
    # Build metadata
    metadata = {
        "discovery_id": discovery_id,
        "opportunity": opportunity,
        "first_step": first_step
    }
    
    try:
        result = query_db(
            """
            INSERT INTO experiments (
                id, name, experiment_type, hypothesis, 
                success_criteria, status, budget_allocated,
                metadata, created_at
            ) VALUES (
                $1, $2, 'revenue_generation', $3,
                $4, 'proposed', $5,
                $6, NOW()
            )
            RETURNING id
            """,
            [
                experiment_id,
                name,
                hypothesis,
                json.dumps(success_criteria),
                capital,
                json.dumps(metadata)
            ]
        )
        
        log_execution(
            worker_id="DISCOVERY_AGENT",
            action="discovery.experiment_created",
            message=f"Created experiment {experiment_id} from opportunity: {name}",
            output_data={
                "experiment_id": experiment_id,
                "discovery_id": discovery_id,
                "opportunity_name": name
            }
        )
        
        return {
            "success": True,
            "experiment_id": experiment_id,
            "name": name,
            "hypothesis": hypothesis,
            "success_criteria": success_criteria
        }
        
    except Exception as e:
        log_execution(
            worker_id="DISCOVERY_AGENT",
            action="discovery.experiment_failed",
            message=f"Failed to create experiment from opportunity: {name}",
            level="error",
            error_data={"error": str(e), "opportunity": name}
        )
        
        return {
            "success": False,
            "error": str(e),
            "opportunity_name": name
        }
