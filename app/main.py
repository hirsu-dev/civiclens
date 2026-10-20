from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .models import AgendaItem, Meeting

app = FastAPI(title="CivicLens", version="0.1.0")
meetings = [
    Meeting(id="m-2026-10-14", date="2026-10-14", body="City Council", title="Regular City Council Meeting", source_url="https://example.gov/meetings/2026-10-14"),
    Meeting(id="m-2026-10-07", date="2026-10-07", body="Planning Commission", title="Planning Commission Hearing", source_url="https://example.gov/meetings/2026-10-07"),
]
items = [
    AgendaItem(id="a-101", meeting_id="m-2026-10-14", title="Protected bike lane pilot on Franklin Avenue", summary="A twelve-month pilot would add a protected lane between 3rd and 9th Streets and measure safety outcomes.", topic="transportation", status="proposed", source_url="https://example.gov/agenda/a-101", district="Central"),
    AgendaItem(id="a-102", meeting_id="m-2026-10-14", title="Affordable housing preservation fund", summary="The council approved a fund to preserve 240 existing rental units near transit corridors.", topic="housing", status="approved", source_url="https://example.gov/agenda/a-102", district="North"),
    AgendaItem(id="a-103", meeting_id="m-2026-10-07", title="Stormwater resilience design standards", summary="New planning standards would require larger developments to retain and reuse more stormwater on site.", topic="environment", status="tabled", source_url="https://example.gov/agenda/a-103", district="Citywide"),
]


@app.get("/api/meetings", response_model=list[Meeting])
def list_meetings() -> list[Meeting]:
    return meetings


@app.get("/api/agenda", response_model=list[AgendaItem])
def search_agenda(q: str = Query(default="", max_length=100), topic: str | None = None, status: str | None = None) -> list[AgendaItem]:
    query = q.lower().strip()
    return [item for item in items if (not query or query in f"{item.title} {item.summary} {item.topic}".lower()) and (not topic or item.topic == topic) and (not status or item.status == status)]


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    with open(STATIC_DIR / "index.html", encoding="utf-8") as file:
        return file.read()

