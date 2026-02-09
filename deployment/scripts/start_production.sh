#!/bin/bash

# Initialize environment
export DB_PASSWORD=$(openssl rand -hex 32)
export SECRET_KEY=$(openssl rand -hex 32)

# Start services
docker-compose -f docker-compose.prod.yaml up -d --build

# Initialize database
docker-compose -f docker-compose.prod.yaml exec db psql -U postgres -d revenue -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"

# Create database indexes
docker-compose -f docker-compose.prod.yaml run --rm revenue_api python -c "from core.database import init_db; init_db()"

# Create background worker queues
docker-compose -f docker-compose.prod.yaml exec redis redis-cli config set notify-keyspace-events KEA

# Start periodic tasks
docker-compose -f docker-compose.prod.yaml exec revenue_worker python -m core.tasks schedule_tasks

echo "Production system deployed successfully"
echo "Access monitoring dashboard at http://localhost:9090"
