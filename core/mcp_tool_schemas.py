"""
MCP Tool Schemas for OpenRouter Function Calling

Defines tool schemas in OpenRouter/OpenAI function calling format.
These are passed to the LLM to enable tool use during Brain consultations.
"""

from typing import Any, Dict, List

# Core tools for Brain consultation
# These map to the tools available in mcp/server.py
BRAIN_TOOLS: List[Dict[str, Any]] = [
    # ============================================================
    # DATABASE TOOLS
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": "Execute a SQL query against the JUGGERNAUT PostgreSQL database. Use for checking task counts, worker status, revenue data, execution logs, experiments, and any system metrics. Always use SELECT queries for safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "The SQL SELECT query to execute. Examples: 'SELECT status, COUNT(*) FROM governance_tasks GROUP BY status', 'SELECT * FROM worker_registry WHERE status = \\'active\\''",
                    }
                },
                "required": ["sql"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hq_execute",
            "description": "Execute pre-defined HQ actions like creating tasks or updating task status. Use this for write operations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["task.create", "task.complete"],
                        "description": "The action to execute",
                    },
                    "params": {
                        "type": "object",
                        "description": "Action parameters. For task.create: {title, description, priority, task_type, assigned_worker, created_by}. Priority accepts enum strings (critical/high/medium/normal/low/background) and numeric levels (0-5). For task.complete: {id, evidence}",
                    },
                },
                "required": ["action", "params"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_executor",
            "description": "Execute the built-in autonomous code executor pipeline (generate code, commit, open PR). Use this for code changes instead of low-level github_put_file choreography.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "Optional task id for tracking. If omitted, one will be generated.",
                    },
                    "task_title": {
                        "type": "string",
                        "description": "Short title for the work item (used for PR title and branch naming).",
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Full description of what to build/change.",
                    },
                    "task_payload": {
                        "type": "object",
                        "description": "Optional executor payload. Supported fields include target_repo/repo, module_name, target_path, requirements, existing_code.",
                    },
                    "auto_merge": {
                        "type": "boolean",
                        "description": "Whether to attempt auto-merge after PR creation (default: false).",
                    },
                },
                "required": ["task_title", "task_description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learning_query",
            "description": "Query recent learnings (without writing raw SQL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Optional learning category filter (e.g., failure_pattern, optimization_opportunity).",
                    },
                    "days_back": {
                        "type": "integer",
                        "description": "How many days back to search (default: 7).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum rows to return (default: 20).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "learning_apply",
            "description": "Apply recent learnings by converting them into actionable governance tasks.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "experiment_list",
            "description": "List experiments (without writing raw SQL).",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "Optional status filter (e.g., running, paused, completed, failed).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "experiment_progress",
            "description": "Progress running experiments by creating any needed phase tasks.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "opportunity_scan_run",
            "description": "Run the opportunity scan pipeline and (optionally) create evaluation tasks for high-scoring opportunities.",
            "parameters": {
                "type": "object",
                "properties": {
                    "config": {
                        "type": "object",
                        "description": "Optional scan config object (min_confidence_score, create_tasks_for_high_scoring, dedupe_hours, etc.).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "puppeteer_healthcheck",
            "description": "Check whether the puppeteer service is configured and healthy.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    # ============================================================
    # GITHUB TOOLS
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "github_list_prs",
            "description": "List pull requests in the juggernaut-autonomy repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "string",
                        "enum": ["open", "closed", "all"],
                        "description": "Filter PRs by state (default: open)",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_put_file",
            "description": "Create or update a file in the juggernaut-autonomy repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file in the repository (e.g., 'core/brain.py')",
                    },
                    "content": {
                        "type": "string",
                        "description": "New content for the file",
                    },
                    "message": {"type": "string", "description": "Commit message"},
                    "branch": {"type": "string", "description": "Branch to commit to"},
                    "sha": {
                        "type": "string",
                        "description": "SHA of the file to update (required for updating existing files)",
                    },
                },
                "required": ["path", "content", "message", "branch"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_get_file",
            "description": "Get the contents of a file from the juggernaut-autonomy repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file in the repository (e.g., 'core/brain.py')",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name (default: main)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_files",
            "description": "List files in a directory of the juggernaut-autonomy repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path (e.g., 'core/' or empty for root)",
                    },
                    "branch": {
                        "type": "string",
                        "description": "Branch name (default: main)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_branch",
            "description": "Create a new branch in the juggernaut-autonomy repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "branch_name": {
                        "type": "string",
                        "description": "Name for the new branch",
                    },
                    "from_branch": {
                        "type": "string",
                        "description": "Base branch to create from (default: main)",
                    },
                },
                "required": ["branch_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_pr",
            "description": "Create a pull request in the juggernaut-autonomy repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "head": {
                        "type": "string",
                        "description": "Branch containing changes",
                    },
                    "title": {"type": "string", "description": "PR title"},
                    "body": {"type": "string", "description": "PR description"},
                    "base": {
                        "type": "string",
                        "description": "Target branch (default: main)",
                    },
                },
                "required": ["head", "title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_merge_pr",
            "description": "Merge a pull request in the juggernaut-autonomy repository",
            "parameters": {
                "type": "object",
                "properties": {
                    "pr_number": {
                        "type": "integer",
                        "description": "Pull request number to merge",
                    },
                    "merge_method": {
                        "type": "string",
                        "enum": ["merge", "squash", "rebase"],
                        "description": "Merge method to use (default: squash)",
                    },
                },
                "required": ["pr_number"],
            },
        },
    },
    # ============================================================
    # RAILWAY TOOLS
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "railway_list_services",
            "description": "List all Railway services in the JUGGERNAUT project",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "railway_get_deployments",
            "description": "Get recent deployments for a Railway service",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_id": {
                        "type": "string",
                        "description": "Railway service ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of deployments to return (default: 5)",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "railway_get_logs",
            "description": "Get logs from a Railway deployment",
            "parameters": {
                "type": "object",
                "properties": {
                    "deployment_id": {
                        "type": "string",
                        "description": "Railway deployment ID",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of log lines (default: 100)",
                    },
                },
                "required": ["deployment_id"],
            },
        },
    },
    # ============================================================
    # COMMUNICATION TOOLS
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "war_room_post",
            "description": "Post a message to the Slack #war-room channel",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Message to post"},
                    "bot": {
                        "type": "string",
                        "description": "Bot name to post as (e.g., 'JUGGERNAUT', 'BRAIN')",
                    },
                },
                "required": ["message", "bot"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "war_room_history",
            "description": "Get recent messages from the Slack #war-room channel",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Number of messages to retrieve (default: 20)",
                    }
                },
            },
        },
    },
    # ============================================================
    # WEB/SEARCH TOOLS
    # ============================================================
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web using Perplexity AI for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "detailed": {
                        "type": "boolean",
                        "description": "Whether to return detailed results (default: false)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "Fetch content from a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "description": "HTTP method (default: GET)",
                    },
                },
                "required": ["url"],
            },
        },
    },
]


def get_tool_schemas(categories: List[str] = None) -> List[Dict[str, Any]]:
    """
    Get tool schemas for OpenRouter function calling.

    Args:
        categories: Optional list of categories to filter by.
                   Currently unused - returns all tools.

    Returns:
        List of tool schemas in OpenRouter format.
    """
    # TODO: Implement category filtering if needed
    return BRAIN_TOOLS


def get_tool_names() -> List[str]:
    """Get list of available tool names."""
    return [tool["function"]["name"] for tool in BRAIN_TOOLS]
"""
MCP Tool Schemas for Customer Acquisition Pipeline
"""
from typing import List, Dict, Any

def get_tool_schemas() -> List[Dict[str, Any]]:
    """Get all tool schemas including customer acquisition tools."""
    base_tools = [
        # ... existing tools ...
    ]
    
    acquisition_tools = [
        {
            "name": "seo_content_generate",
            "description": "Generate SEO-optimized content for customer acquisition",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "Primary topic/keyword"},
                    "target_keywords": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of target keywords to include"
                    },
                    "word_count": {
                        "type": "integer",
                        "description": "Target word count",
                        "default": 1500
                    },
                    "tone": {
                        "type": "string",
                        "enum": ["professional", "conversational", "authoritative"],
                        "default": "professional"
                    }
                },
                "required": ["topic", "target_keywords"]
            }
        },
        {
            "name": "ad_campaign_manage",
            "description": "Create or optimize ad campaigns",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_name": {"type": "string", "description": "Campaign identifier"},
                    "platform": {
                        "type": "string",
                        "enum": ["google", "facebook", "linkedin", "twitter"],
                        "description": "Advertising platform"
                    },
                    "daily_budget": {
                        "type": "number",
                        "description": "Daily budget in USD"
                    },
                    "target_metrics": {
                        "type": "object",
                        "description": "Key performance targets",
                        "properties": {
                            "cpa": {"type": "number", "description": "Target cost per acquisition"},
                            "roas": {"type": "number", "description": "Target return on ad spend"},
                            "ctr": {"type": "number", "description": "Target click-through rate"}
                        }
                    },
                    "creative_assets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "URLs to creative assets"
                    }
                },
                "required": ["campaign_name", "platform", "daily_budget"]
            }
        },
        {
            "name": "onboarding_flow_optimize",
            "description": "Optimize self-serve onboarding flow with A/B tests",
            "parameters": {
                "type": "object",
                "properties": {
                    "flow_name": {"type": "string", "description": "Onboarding flow identifier"},
                    "variants": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "changes": {"type": "string"}
                            }
                        },
                        "description": "Test variants to compare"
                    },
                    "primary_metric": {
                        "type": "string",
                        "enum": ["conversion_rate", "time_to_value", "activation_rate"],
                        "default": "conversion_rate"
                    },
                    "sample_size": {
                        "type": "integer",
                        "description": "Number of users to include in test"
                    }
                },
                "required": ["flow_name", "variants"]
            }
        }
    ]
    
    return base_tools + acquisition_tools
