# JUGGERNAUT API Documentation

JUGGERNAUT provides multiple API interfaces:

1. **Dashboard API** - REST endpoints for the Executive Dashboard
2. **Unified Brain API** - Neural interface with tool execution capabilities
3. **MCP API** - Model Context Protocol for standardized tool execution

## Dashboard API Endpoints

- GET /health - Health check
- GET /v1/overview - Dashboard overview
- GET /v1/revenue - Revenue summary
- GET /v1/experiments - Experiments
- GET /v1/agents - Agent health
- GET /v1/goals - Goal progress
- GET /v1/pnl - Profit and loss
- GET /v1/approvals - Pending approvals
- GET /v1/alerts - System alerts

## Unified Brain API Endpoints

- POST /api/brain/unified/consult - Main consultation endpoint with tool execution
- POST /api/brain/unified/stream - Streaming version of consult endpoint
- GET /api/brain/sessions - List all brain sessions
- GET /api/brain/sessions/{id} - Get specific session
- POST /api/brain/sessions - Create new session

### Unified Brain Request Format

```json
{
  "question": "What's the status of our revenue experiments?",
  "session_id": "optional-session-uuid",
  "context": {},
  "include_memories": true,
  "enable_tools": true,
  "auto_execute": true
}
```

### Unified Brain Response Format

```json
{
  "response": "Detailed answer to the question...",
  "session_id": "session-uuid",
  "tool_executions": [
    {
      "tool": "sql_query",
      "arguments": { "query": "SELECT * FROM experiments" },
      "result": { "rows": [...] }
    }
  ],
  "iterations": 3,
  "input_tokens": 1250,
  "output_tokens": 450
}
```

## MCP Tool Schemas

The Unified Brain supports 68+ tools, including the high-level `code_executor` tool:

```json
{
  "type": "function",
  "function": {
    "name": "code_executor",
    "description": "Execute the built-in autonomous code executor pipeline (generate code, commit, open PR)",
    "parameters": {
      "type": "object",
      "properties": {
        "task_id": {
          "type": "string",
          "description": "Optional task id for tracking"
        },
        "task_title": {
          "type": "string",
          "description": "Short title for the work item (PR title)"
        },
        "task_description": {
          "type": "string",
          "description": "Full description of what to build/change"
        },
        "task_payload": {
          "type": "object",
          "description": "Optional executor payload"
        },
        "auto_merge": {
          "type": "boolean",
          "description": "Whether to attempt auto-merge after PR creation"
        }
      },
      "required": ["task_title", "task_description"]
    }
  }
}

## Authentication

### Dashboard API
API keys use format: jug_{user_id}_{timestamp}_{signature}

### Unified Brain API
Supports multiple authentication methods:
1. Query parameter: `?token=YOUR_TOKEN`
2. Authorization header: `Authorization: Bearer YOUR_TOKEN`
3. API key header: `x-api-key: YOUR_TOKEN`

Valid tokens include `MCP_AUTH_TOKEN` and `INTERNAL_API_SECRET`
