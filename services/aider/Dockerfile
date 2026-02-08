FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install aider-chat
RUN pip install --no-cache-dir aider-chat

# Set git config
RUN git config --global user.name "JUGGERNAUT Engine" && \
    git config --global user.email "engine@juggernaut.dev"

# Create workspace directory
RUN mkdir -p /workspace
WORKDIR /workspace

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD aider --version || exit 1

# Default command (will be overridden by Railway)
CMD ["sleep", "infinity"]
