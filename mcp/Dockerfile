# ==============================================================================
# JUGGERNAUT MCP Server - Dockerfile
# ==============================================================================
# SSE-based Model Context Protocol server for Claude.ai integration
# ==============================================================================

FROM python:3.11-slim

LABEL maintainer="JUGGERNAUT System"
LABEL version="1.0.0"
LABEL description="JUGGERNAUT MCP Server - Claude.ai Integration"

# Security: Create non-root user
RUN groupadd -r juggernaut && useradd -r -g juggernaut juggernaut

WORKDIR /app

# Install dependencies first (for caching)
COPY mcp/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY mcp/server.py ./server.py

# Set ownership
RUN chown -R juggernaut:juggernaut /app

# Switch to non-root user
USER juggernaut

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8080
ENV MCP_AUTH_TOKEN=""
ENV DATABASE_URL=""
ENV SLACK_BOT_TOKEN=""
ENV WAR_ROOM_CHANNEL="C0A5WTBHX1A"

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

EXPOSE 8080

CMD ["python", "server.py"]
