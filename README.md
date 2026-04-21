# Intern Prep Agent

AI-powered internship preparation system for CS graduate students.

A two-agent system that finds internship postings, tailors your CV to each JD, and adapts your study plan based on your daily progress.

## Quick Start

### Prerequisites
- Python 3.11+
- Docker Desktop

### Setup

1. **Start the database:**
```bash
docker-compose up -d
```

2. **Create a virtual environment and install dependencies:**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

3. **Set up environment variables:**
```bash
cp .env.example .env
```

4. **Run the API server:**
```bash
uvicorn api.main:app --reload
```

5. **Verify it works:**
- Open http://localhost:8000/health → should return `{"status": "ok"}`
- Open http://localhost:8000/health/db → should return `{"database": "connected"}`
- Open http://localhost:8000/docs → interactive API documentation

## Project Structure

```
intern-prep-agent/
├── collector/          # Job Collector Agent
│   └── scrapers/       # Per-company API clients
├── prep/               # Core Prep Agent
├── api/                # FastAPI app
│   ├── main.py         # Entry point
│   ├── routes/         # API endpoints
│   └── schemas/        # Pydantic models
├── db/                 # Database models & session
├── templates/          # CV HTML templates
├── tests/              # Test suite
├── docker-compose.yml  # PostgreSQL + pgvector
└── requirements.txt    # Python dependencies
```

## Tech Stack

- **Backend:** FastAPI + Python 3.11
- **Database:** PostgreSQL + pgvector
- **LLM:** Claude API (claude-sonnet-4-20250514)
- **Embeddings:** sentence-transformers (all-MiniLM-L6-v2)
- **PDF:** WeasyPrint
