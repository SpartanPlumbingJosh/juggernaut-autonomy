# JUGGERNAUT Development Setup

## Prerequisites

- Python 3.11+
- Git
- Access to Neon PostgreSQL database

## Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/SpartanPlumbingJosh/juggernaut-autonomy.git
cd juggernaut-autonomy
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
cp .env.example .env
# Edit .env with your credentials
```

5. **Verify database connection**
```python
from core.database import query_db
result = query_db("SELECT 1")
print(result)  # Should return {"rows": [{"?column?": 1}]}
```

## Project Structure

```
juggernaut-autonomy/
├── core/              # Core functionality
│   ├── __init__.py
│   └── database.py    # Database operations
├── agents/            # Agent implementations
├── experiments/       # Revenue experiments
├── api/              # API endpoints
├── docs/             # Documentation
│   └── SCHEMA.md     # Database schema
├── tests/            # Test files
├── .env.example      # Environment template
├── requirements.txt  # Dependencies
└── README.md         # Project overview
```

## Database

Using Neon PostgreSQL with SQL over HTTP.

- **Endpoint**: https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql
- **Connection**: Via `Neon-Connection-String` header
- **Tables**: 21 tables (see docs/SCHEMA.md)

## Running Tests

```bash
pytest tests/ -v
```

## Code Style

- Follow PEP 8
- Max line length: 127 characters
- Use type hints where possible

## Key Functions

### database.py

- `query_db(sql)` - Execute raw SQL
- `log_execution(...)` - Log an action
- `create_opportunity(...)` - Create pipeline opportunity
- `get_logs(...)` - Query execution logs
- `get_opportunities(...)` - Query opportunities
