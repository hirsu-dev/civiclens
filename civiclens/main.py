import csv
import io
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .demo import sample_bundle, seed
from .models import DecisionStatus, ImportBundle, SavedSearch
from .storage import Store

STATIC_DIR = Path(__file__).parent / "static"


def create_app(db_path=None, demo=None, write_token=None):
    store = Store(db_path or os.getenv("CIVICLENS_DB", "data/civiclens.sqlite3"))
    demo = os.getenv("DEMO_DATA", "1") == "1" if demo is None else demo
    token = os.getenv("WRITE_TOKEN", "") if write_token is None else write_token

    @asynccontextmanager
    async def lifespan(app):
        if demo:
            seed(store)
        yield

    app = FastAPI(title="CivicLens", version="0.2.0", lifespan=lifespan)
    app.state.store = store

    def authorize(x_write_token: str = Header(default="")):
        if token and not secrets.compare_digest(x_write_token.encode(), token.encode()):
            raise HTTPException(401, "A valid X-Write-Token header is required")

    @app.middleware("http")
    async def security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path == "/" or request.url.path.startswith("/static"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
            )
        return response

    @app.get("/api/status")
    def status():
        return {"ok": True, "version": "0.2.0", "write_token_required": bool(token)}

    @app.get("/api/meetings")
    def meetings():
        return store.meetings()

    def filters(
        q: str = Query("", max_length=200),
        topic: str = Query("", max_length=80),
        status: DecisionStatus | None = None,
        district: str = Query("", max_length=100),
        jurisdiction: str = Query("", max_length=200),
        after: date | None = None,
        before: date | None = None,
    ):
        if after and before and after > before:
            raise HTTPException(422, "Start date must be on or before end date")
        return dict(
            q=q,
            topic=topic,
            status=status,
            district=district,
            jurisdiction=jurisdiction,
            after=after.isoformat() if after else None,
            before=before.isoformat() if before else None,
        )

    @app.get("/api/agenda")
    def agenda(
        criteria=Depends(filters),
        offset: int = Query(0, ge=0),
        limit: int = Query(30, ge=1, le=200),
    ):
        rows = store.query(**criteria)
        return {
            "items": rows[offset : offset + limit],
            "total": len(rows),
            "offset": offset,
            "limit": limit,
        }

    def require_item(identifier):
        row = next((r for r in store.records() if r["id"] == identifier), None)
        if not row:
            raise HTTPException(404, "Agenda item not found")
        return row

    @app.get("/api/agenda/{identifier}")
    def detail(identifier: str):
        item = require_item(identifier)
        return {
            "item": item,
            "timeline": store.timeline(item),
            "revisions": store.revisions(identifier),
        }

    @app.get("/api/facets")
    def facets():
        rows = store.records()
        return {
            "topics": sorted({r["topic"] for r in rows}),
            "districts": sorted({r["district"] for r in rows}),
            "jurisdictions": sorted({r["meeting"]["jurisdiction"] for r in rows}),
            "total": len(rows),
            "demo_records": sum(r["meeting"]["is_demo"] for r in rows),
        }

    @app.post("/api/import", status_code=201, dependencies=[Depends(authorize)])
    def import_records(bundle: ImportBundle):
        try:
            return store.import_bundle(bundle)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/import-template")
    def template():
        return sample_bundle()

    @app.get("/api/saved-searches")
    def searches():
        return [
            {
                **s,
                "matches": len(
                    store.query(**{k: v for k, v in s.items() if k not in {"id", "name"}})
                ),
            }
            for s in store.searches()
        ]

    @app.post("/api/saved-searches", status_code=201, dependencies=[Depends(authorize)])
    def save_search(search: SavedSearch):
        return store.save_search(search)

    @app.delete(
        "/api/saved-searches/{identifier}", status_code=204, dependencies=[Depends(authorize)]
    )
    def delete_search(identifier: str):
        if not store.delete_search(identifier):
            raise HTTPException(404, "Saved search not found")
        return Response(status_code=204)

    @app.get("/api/export.csv")
    def export(criteria=Depends(filters)):
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "meeting_date",
                "jurisdiction",
                "title",
                "reference",
                "topic",
                "status",
                "district",
                "summary",
                "source_url",
                "is_demo",
            ]
        )

        def safe(value):
            text = str(value or "")
            return (
                "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
            )

        for item in store.query(**criteria):
            writer.writerow(
                [
                    safe(v)
                    for v in (
                        item["id"],
                        item["meeting"]["date"],
                        item["meeting"]["jurisdiction"],
                        item["title"],
                        item["reference"],
                        item["topic"],
                        item["status"],
                        item["district"],
                        item["summary"],
                        item["source_url"],
                        item["meeting"]["is_demo"],
                    )
                ]
            )
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="civiclens.csv"'},
        )

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    def home():
        return FileResponse(STATIC_DIR / "index.html")

    return app


app = create_app()
