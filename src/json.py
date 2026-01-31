"""
JSON module for MCP tools compatible with OpenRouter function calling format.

Defines JSON schemas for MCP tools grouped by category, validated against OpenAI/OpenRouter
function calling specification.
"""

import json
from typing import Dict, List, Any, TypedDict
import logging

logger = logging.getLogger(__name__)

# Constants
MCP_SERVER_URL = "https://juggernaut-mcp-production.up.railway.app"
MAX_QUERY_LENGTH = 10000
MAX_RESULTS_DEFAULT = 10


class ToolSchema(TypedDict):
    """Type definition for OpenRouter tool schema."""
    type: str
    function: Dict[str, Any]


class MCPTools:
    """Manager for MCP tool JSON schemas grouped by category."""
    
    @classmethod
    def get_all_tools(cls) -> List[ToolSchema]:
        """Returns complete list of MCP tool definitions for OpenRouter.
        
        Returns:
            List of tool schemas compatible with OpenRouter function calling.
        """
        return [            # Database tools
            cls._sql_query(),
            # GitHub tools
            cls._github_list_prs(),
            # Railway tools
            cls._railway_get_deployments(),
            # Email tools
            cls._email_list(),
            # Web tools
            cls._web_search(),
            cls._fetch_url(),
            # Storage tools
            cls._storage_list(),
            # AI tools
            cls._ai_chat(),
        ]
    
    @classmethod
    def get_core_tools(cls) -> List[ToolSchema]:
        """Returns core 7 tools most needed for chat functionality.
        
        Returns:
            List of essential MCP tools for immediate use.
        """
        return [            cls._sql_query(),
            cls._github_list_prs(),
            cls._railway_get_deployments(),
            cls._email_list(),
            cls._web_search(),
            cls._storage_list(),
        ]
    
    @classmethod
    def get_tools_by_category(cls, category: str) -> List[ToolSchema]:
        """Returns tools filtered by category.
        
        Args:
            category: One of 'database', 'github', 'railway', 'email', 'web', 'storage', 'ai'
            
        Raises:
            ValueError: Invalid category specified
            
        Returns:
            List of tool schemas for specified category.
        """
        category_map = {
            'database': [cls._sql_query()],
            'github': [cls._github_list_prs()],
            'railway': [cls._railway_get_deployments()],
            'email': [cls._email_list()],
            'web': [cls._web_search(), cls._fetch_url()],
            'storage': [cls._storage_list()],
            'ai': [cls._ai_chat()],
        }
        
        tools = category_map.get(category.lower())
        if not tools:
            valid_categories = ', '.join(category_map.keys())
            raise ValueError(f"Invalid category '{category}'. Must be one of: {valid_categories}")
        
        return tools
    
    @classmethod
    def validate_tool_schema(cls, tool: ToolSchema) -> bool:
        """Validates tool schema against OpenRouter/OpenAI function calling spec.
        
        Args:
            tool: Tool schema to validate
            
        Returns:
            True if schema is valid, False otherwise
        """
        try:
            required_fields = ['type', 'function']
            if tool.get('type') != 'function':
                logger.warning("Tool type must be 'function'")
                return False
            
            func = tool['function']
            required_func_fields = ['name', 'description', 'parameters']
            for field in required_func_fields:
                if field not in func:
                    logger.warning(f"Missing required function field: {field}")
                    return False
            
            # Validate parameters structure
            params = func['parameters']
            if params.get('type') != 'object':
                logger.warning("Parameters type must be 'object'")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Tool validation failed: {e}")
            return False
    
    # Database Tools
    @classmethod
    def _sql_query(cls) -> ToolSchema:
        """SQL query tool for database operations."""
        return {
            "type": "function",
            "function": {
                "name": "sql_query",
                "description": "Execute SQL query against MCP database. Use for data analysis, lookups, and reporting.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "SQL query to execute (SELECT statements recommended for safety)"
                        },
                        "database": {
                            "type": "string",
                            "description": "Database name (default: primary)",
                            "default": "primary"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return",
                            "default": 100,
                            "minimum": 1,
                            "maximum": 1000
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    # GitHub Tools
    @classmethod
    def _github_list_prs(cls) -> ToolSchema:
        """List GitHub pull requests for repositories."""
        return {
            "type": "function",
            "function": {
                "name": "github_list_prs",
                "description": "List open pull requests for GitHub repositories. Supports multiple repos.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repos": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Repository names in org/repo format, e.g. ['juggernaut/core', 'juggernaut/mcp']"
                        },
                        "state": {
                            "type": "string",
                            "enum": ["open", "closed", "all"],
                            "description": "PR state filter",
                            "default": "open"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Max PRs per repo",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50
                        }
                    },
                    "required": ["repos"]
                }
            }
        }
    
    # Railway Tools
    @classmethod
    def _railway_get_deployments(cls) -> ToolSchema:
        """Get Railway deployments status."""
        return {
            "type": "function",
            "function": {
                "name": "railway_get_deployments",
                "description": "Get deployment status for Railway projects/services.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Railway project IDs or slugs"
                        },
                        "service_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Railway service IDs (optional)"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 20,
                            "minimum": 1,
                            "maximum": 100
                        }
                    },
                    "required": ["project_ids"]
                }
            }
        }
    
    # Email Tools
    @classmethod
    def _email_list(cls) -> ToolSchema:
        """List recent emails."""
        return {
            "type": "function",
            "function": {
                "name": "email_list",
                "description": "List recent emails from connected accounts. Supports Gmail, Outlook, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account": {
                            "type": "string",
                            "description": "Email account identifier (e.g. 'primary', 'work')"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 50
                        },
                        "unread_only": {
                            "type": "boolean",
                            "description": "Filter to unread emails only",
                            "default": False
                        }
                    }
                }
            }
        }
    
    # Web Tools
    @classmethod
    def _web_search(cls) -> ToolSchema:
        """Web search tool."""
        return {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web using integrated search engine.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query"
                        },
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 30
                        }
                    },
                    "required": ["query"]
                }
            }
        }
    
    @classmethod
    def _fetch_url(cls) -> ToolSchema:
        """Fetch URL content."""
        return {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch and parse content from any URL.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to fetch"
                        },
                        "extract": {
                            "type": "string",
                            "description": "CSS selector or text to extract (optional)"
                        }
                    },
                    "required": ["url"]
                }
            }
        }
    
    # Storage Tools
    @classmethod
    def _storage_list(cls) -> ToolSchema:
        """List storage files."""
        return {
            "type": "function",
            "function": {
                "name": "storage_list",
                "description": "List files in MCP storage buckets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bucket": {
                            "type": "string",
                            "description": "Storage bucket name",
                            "default": "default"
                        },
                        "prefix": {
                            "type": "string",
                            "description": "File prefix/path filter"
                        },
                        "limit": {
                            "type": "integer",
                            "default": 50,
                            "minimum": 1,
                            "maximum": 1000
                        }
                    }
                }
            }
        }
    
    # AI Tools
    @classmethod
    def _ai_chat(cls) -> ToolSchema:
        """AI chat completion."""
        return {
            "type": "function",
            "function": {
                "name": "ai_chat",
                "description": "Generate AI chat completion using configured models.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "messages": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "role": {"type": "string", "enum": ["system", "user", "assistant"]},
                                    "content": {"type": "string"}
                                },
                                "required": ["role", "content"]
                            },
                            "description": "Chat messages"
                        },
                        "model": {
                            "type": "string",
                            "description": "Model identifier (default uses system default)"
                        }
                    },
                    "required": ["messages"]
                }
            }
        }


def get_mcp_tools_json(core_only: bool = False) -> str:
    """Generate JSON string of MCP tools for OpenRouter API.
    
    Args:
        core_only: If True, return only essential 6 tools for chat
        
    Returns:
        JSON string of tool definitions
        
    Raises:
        Exception: JSON serialization failed
    """
    try:
        tools = MCPTools.get_core_tools() if core_only else MCPTools.get_all_tools()
        
        # Validate all tools
        valid_tools = [tool for tool in tools if MCPTools.validate_tool_schema(tool)]
        if len(valid_tools) != len(tools):
            logger.warning(f"Some tools failed validation. Valid: {len(valid_tools)}/{len(tools)}")
        
        return json.dumps(valid_tools, indent=2)
    except Exception as e:
        logger.error(f"Failed to generate MCP tools JSON: {e}")
        raise


def main():
    """CLI entrypoint for testing tool generation."""
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--core":
        print(get_mcp_tools_json(core_only=True))
    else:
        print(get_mcp_tools_json(core_only=False))


if __name__ == "__main__":
    main()