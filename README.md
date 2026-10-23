# CivicLens

[![Tests](https://github.com/hrushikbarani-hub/civiclens/actions/workflows/test.yml/badge.svg)](https://github.com/hrushikbarani-hub/civiclens/actions/workflows/test.yml)

CivicLens helps organize public meeting decisions and connect them to their source records. It keeps a timeline of each decision and shows where summaries came from.

![CivicLens explorer](docs/images/explorer.jpg)

## Features

- Search meeting records and filter by topic, status, district, or community.
- Follow a decision across meetings using its reference.
- Read source excerpts and see how each summary was made.
- Import JSON records and convert agenda CSV files.
- Save searches and export results as CSV.

The starter records are fictional examples for “Sample City.” CivicLens does not include real city data, crawl websites, or generate AI summaries. Check imported information against its source.

The app uses Python, FastAPI, and SQLite with a plain JavaScript interface. It can run locally without a hosted service or model key.

## Run it

Requires Python 3.11 or newer and SQLite with FTS5 trigram support. From the project folder:

```sh
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python -m uvicorn civiclens.main:app --host 127.0.0.1 --port 8002
```

Open [http://localhost:8002](http://localhost:8002). API docs are at `/docs`. You can also use `./run.ps1` on Windows or run the app with Docker:

```sh
docker compose up --build
```

## Import records

Start with the example files in `examples/`. A CSV agenda can be converted to JSON:

```sh
python -m civiclens.cli convert-csv examples/agenda.csv --meeting-id sample-session --date 2026-10-14 --body "City Council" --title "Sample session" --jurisdiction "Sample City" --source-url https://example.invalid/meeting --demo
```

Validate and import the resulting file:

```sh
python -m civiclens.cli validate bundle.json
python -m civiclens.cli import bundle.json
```

Use stable IDs and decision references to connect records across meetings. Check the source before importing real information.

## Settings and safety

Copy `.env.example` to `.env` for Docker Compose. Settings include the database path, demo data, and an optional write token.

Keep the server on your own computer unless you add HTTPS and access control. This app has one shared workspace, so everyone who can access it can read its records and saved searches.

Back up your database before upgrading. See [search notes](docs/search.md) for details about the current search version.

## Development

```sh
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python -m build
```

See [contributing](CONTRIBUTING.md), [architecture](docs/architecture.md), and [roadmap](docs/roadmap.md). This project uses the MIT license.
