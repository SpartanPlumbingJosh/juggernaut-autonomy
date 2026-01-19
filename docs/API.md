# JUGGERNAUT Dashboard API Documentation

The JUGGERNAUT Dashboard API provides REST endpoints for the Executive Dashboard.

## Endpoints

- GET /health - Health check
- GET /v1/overview - Dashboard overview
- GET /v1/revenue - Revenue summary
- GET /v1/experiments - Experiments
- GET /v1/agents - Agent health
- GET /v1/goals - Goal progress
- GET /v1/pnl - Profit and loss
- GET /v1/approvals - Pending approvals
- GET /v1/alerts - System alerts

## Authentication

API keys use format: jug_{user_id}_{timestamp}_{signature}
