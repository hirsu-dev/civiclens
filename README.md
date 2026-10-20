# CivicLens

CivicLens makes local government decisions easier to follow. It models public meeting items, preserves source links, and gives residents a searchable timeline of what is being proposed.

## Current slice

- FastAPI API for meetings and agenda items
- Full-text search across seeded public records
- Explainable topic tags and status filters
- Browser interface built with plain JavaScript
- Source attribution on every result
- Tests, Docker setup, and a path to document ingestion

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000. API docs are at `/docs`.

## Roadmap

1. PDF/HTML ingestion adapters for municipal websites
2. PostgreSQL + full-text search and embeddings
3. District map and notification subscriptions
4. Citation-preserving summaries with human review states
5. Public data export for journalists and community groups

