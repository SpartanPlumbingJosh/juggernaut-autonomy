# ==============================================================================
# JUGGERNAUT Autonomy Engine - Dockerfile
# ==============================================================================
# The heartbeat of autonomous revenue generation
# Runs 24/7, makes decisions, takes actions
# ==============================================================================

FROM python:3.11-slim

# Labels
LABEL maintainer="JUGGERNAUT System"
LABEL version="1.3.0"
LABEL description="JUGGERNAUT Autonomy Engine - Autonomous Revenue Framework"

# Security: Create non-root user
RUN groupadd -r juggernaut && useradd -r -g juggernaut juggernaut

WORKDIR /app

# Install dependencies first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cache bust - change this to force rebuild of COPY layers
ARG CACHEBUST=20260125210000

# Copy application code (these layers will rebuild when CACHEBUST changes)
COPY main.py .
COPY core/ ./core/
COPY api/ ./api/
COPY src/ ./src/
COPY watchdog/ ./watchdog/

# Set ownership
RUN chown -R juggernaut:juggernaut /app

# Switch to non-root user
USER juggernaut

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PORT=8000
ENV WORKER_ID="autonomy-engine-1"
ENV LOOP_INTERVAL_SECONDS=60
ENV DRY_RUN=false

# Health check - verify the service responds
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Expose port
EXPOSE 8000

# Run the autonomy engine
CMD ["python", "main.py"]
