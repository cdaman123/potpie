# Potpie Project

## Quick Start

### Prerequisites

- Python 3.12
- Redis server
- PostgreSQL
- Gemini API

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd potpie
```

2. **Install Poetry** (if not already installed)

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. **Install dependencies**

```bash
poetry install
```

4. **Setup environment**

```bash
poetry run python run.py setup
```

4. **Configure environment variables**
Edit `.env` file with your settings:

```env
# Database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/potpie

# Redis
REDIS_URL=redis://localhost:6379/0


# Google Gemini
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-2.5-flash

# Application
DEBUG=True
LOG_LEVEL=INFO

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
```

5. **Start services**

Using Docker Compose (recommended):

```bash
docker-compose up -d
```

Or manually:

```bash
# Terminal 1: Start API
poetry run python main.py

# Terminal 2: Start worker
poetry run celery -A potpie.celery_app worker --loglevel=info

```

## API Usage

### Analyze a Pull Request

```bash
curl -X POST "http://localhost:8000/analyze-pr" \
  -H "Content-Type: application/json" \
  -d '{
    "repo_url": "https://github.com/owner/repo",
    "pr_number": 123,
    "github_token": "optional_token"
  }'
```

Response:

```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "pending",
  "message": "Analysis started",
  "status_url": "/status/abc123-def456-ghi789",
  "results_url": "/results/abc123-def456-ghi789"
}
```

### Check Task Status

```bash
curl "http://localhost:8000/status/abc123-def456-ghi789"
```

### Get Results

```bash
curl "http://localhost:8000/results/abc123-def456-ghi789"
```

Example response:

```json
{
  "task_id": "abc123-def456-ghi789",
  "status": "completed",
  "results": {
    "files": [
      {
        "name": "main.py",
        "path": "src/main.py",
        "lines_analyzed": 150,
        "issues": [
          {
            "type": "style",
            "line": 15,
            "description": "Line too long (125 characters)",
            "suggestion": "Break line into multiple lines",
            "severity": "low"
          },
          {
            "type": "bug",
            "line": 23,
            "description": "Potential null pointer exception",
            "suggestion": "Add null check before accessing object",
            "severity": "high"
          }
        ]
      }
    ],
    "summary": {
      "total_files": 1,
      "total_issues": 2,
      "critical_issues": 0,
      "high_issues": 1,
      "medium_issues": 0,
      "low_issues": 1,
      "languages_detected": ["python"]
    },
    "recommendations": [
      "⚠️ Review 1 high-priority issues before merging",
      "🐍 Consider running black, flake8, and mypy for Python code quality"
    ]
  }
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite fallback |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `GOOGLE_API_KEY` | Google Gemini API key | None |
| `GEMINI_MODEL` | Gemini model name | `gemini-pro` |
| `DEBUG` | Debug mode | `True` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Development

### Running Tests

```bash
poetry run pytest tests/
```
