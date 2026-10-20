import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from .models import ImportBundle, SavedSearch


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS meetings (
                    id TEXT PRIMARY KEY, date TEXT NOT NULL, jurisdiction TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agenda (
                    id TEXT PRIMARY KEY, meeting_id TEXT NOT NULL REFERENCES meetings(id),
                    reference TEXT, payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS agenda_meeting ON agenda(meeting_id);
                CREATE TABLE IF NOT EXISTS revisions (
                    sequence INTEGER PRIMARY KEY, item_id TEXT NOT NULL, changed_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS searches (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            with db:
                yield db
        finally:
            db.close()

    def import_bundle(self, bundle: ImportBundle):
        added = updated = unchanged = 0
        with self.connection() as db:
            # Validate all references before writing; a bad bundle leaves no partial data.
            known = {row[0] for row in db.execute("SELECT id FROM meetings")}
            known.update(m.id for m in bundle.meetings)
            if any(item.meeting_id not in known for item in bundle.items):
                raise ValueError("Every agenda item must reference an existing or bundled meeting")
            for meeting in bundle.meetings:
                db.execute(
                    "INSERT INTO meetings VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET date=excluded.date,jurisdiction=excluded.jurisdiction,payload=excluded.payload",
                    (
                        meeting.id,
                        meeting.date.isoformat(),
                        meeting.jurisdiction,
                        meeting.model_dump_json(),
                    ),
                )
            for item in bundle.items:
                payload = item.model_dump_json()
                previous = db.execute(
                    "SELECT payload FROM agenda WHERE id=?", (item.id,)
                ).fetchone()
                if previous and previous[0] == payload:
                    unchanged += 1
                    continue
                if previous:
                    updated += 1
                else:
                    added += 1
                db.execute(
                    "INSERT INTO agenda VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET meeting_id=excluded.meeting_id,reference=excluded.reference,payload=excluded.payload",
                    (item.id, item.meeting_id, item.reference, payload),
                )
                db.execute(
                    "INSERT INTO revisions(item_id,changed_at,payload) VALUES(?,?,?)",
                    (item.id, datetime.now(UTC).isoformat(), payload),
                )
        return {
            "added": added,
            "updated": updated,
            "unchanged": unchanged,
            "meetings": len(bundle.meetings),
        }

    def meetings(self):
        with self.connection() as db:
            return [
                json.loads(row[0])
                for row in db.execute("SELECT payload FROM meetings ORDER BY date DESC,id")
            ]

    def records(self):
        with self.connection() as db:
            rows = db.execute(
                "SELECT a.payload,m.payload AS meeting FROM agenda a JOIN meetings m ON m.id=a.meeting_id ORDER BY m.date DESC,a.id"
            ).fetchall()
        return [
            {**json.loads(row["payload"]), "meeting": json.loads(row["meeting"])} for row in rows
        ]

    def query(
        self, q="", topic="", status=None, district="", jurisdiction="", after=None, before=None
    ):
        terms = q.casefold().split()
        return [
            item
            for item in self.records()
            if all(
                term
                in " ".join(
                    str(item.get(k) or "")
                    for k in ("title", "summary", "source_excerpt", "topic", "reference")
                ).casefold()
                for term in terms
            )
            and (not topic or item["topic"] == topic)
            and (not status or item["status"] == status)
            and (not district or item["district"] == district)
            and (not jurisdiction or item["meeting"]["jurisdiction"] == jurisdiction)
            and (not after or item["meeting"]["date"] >= after)
            and (not before or item["meeting"]["date"] <= before)
        ]

    def timeline(self, item):
        return sorted(
            [
                row
                for row in self.records()
                if row["id"] == item["id"]
                or (
                    item["reference"]
                    and row["reference"] == item["reference"]
                    and row["meeting"]["jurisdiction"] == item["meeting"]["jurisdiction"]
                    and row["meeting"]["is_demo"] == item["meeting"]["is_demo"]
                )
            ],
            key=lambda row: (row["meeting"]["date"], row["id"]),
        )

    def revisions(self, item_id):
        with self.connection() as db:
            rows = db.execute(
                "SELECT changed_at,payload FROM revisions WHERE item_id=? ORDER BY sequence DESC",
                (item_id,),
            ).fetchall()
        return [{"changed_at": row[0], "item": json.loads(row[1])} for row in rows]

    def searches(self):
        with self.connection() as db:
            rows = db.execute("SELECT id,payload FROM searches ORDER BY rowid").fetchall()
        return [{"id": row[0], **json.loads(row[1])} for row in rows]

    def save_search(self, search: SavedSearch):
        identifier = uuid4().hex
        with self.connection() as db:
            db.execute("INSERT INTO searches VALUES(?,?)", (identifier, search.model_dump_json()))
        return {"id": identifier, **search.model_dump()}

    def delete_search(self, identifier):
        with self.connection() as db:
            return db.execute("DELETE FROM searches WHERE id=?", (identifier,)).rowcount > 0
