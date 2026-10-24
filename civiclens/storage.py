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
                CREATE INDEX IF NOT EXISTS agenda_reference ON agenda(reference);
                CREATE INDEX IF NOT EXISTS meeting_date ON meetings(date DESC,id);
                CREATE INDEX IF NOT EXISTS meeting_jurisdiction ON meetings(jurisdiction);
                CREATE TABLE IF NOT EXISTS revisions (
                    sequence INTEGER PRIMARY KEY, item_id TEXT NOT NULL, changed_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS searches (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)
            self._migrate_search(db)

    @staticmethod
    def _search_fields(item):
        text = " ".join(
            str(item.get(k) or "")
            for k in ("title", "summary", "source_excerpt", "topic", "reference")
        ).casefold()
        return (text, item["topic"], item["status"], item.get("district", "Citywide"))

    def _migrate_search(self, db):
        db.execute("BEGIN IMMEDIATE")
        columns = {row[1] for row in db.execute("PRAGMA table_info(agenda)")}
        needs_backfill = "search_text" not in columns
        for name in ("search_text", "topic", "status", "district"):
            if name not in columns:
                db.execute(f"ALTER TABLE agenda ADD COLUMN {name} TEXT NOT NULL DEFAULT ''")
        if needs_backfill:
            for row in db.execute("SELECT id,payload FROM agenda").fetchall():
                fields = self._search_fields(json.loads(row["payload"]))
                db.execute(
                    "UPDATE agenda SET search_text=?,topic=?,status=?,district=? WHERE id=?",
                    (*fields, row["id"]),
                )
        had_index = db.execute("SELECT 1 FROM sqlite_master WHERE name='agenda_fts'").fetchone()
        db.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS agenda_fts USING fts5(search_text,content='agenda',content_rowid='rowid',tokenize='trigram case_sensitive 1')"
        )
        db.execute("""CREATE TRIGGER IF NOT EXISTS agenda_fts_insert AFTER INSERT ON agenda BEGIN
            INSERT INTO agenda_fts(rowid,search_text) VALUES(new.rowid,new.search_text);
        END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS agenda_fts_delete AFTER DELETE ON agenda BEGIN
            INSERT INTO agenda_fts(agenda_fts,rowid,search_text) VALUES('delete',old.rowid,old.search_text);
        END""")
        db.execute("""CREATE TRIGGER IF NOT EXISTS agenda_fts_update AFTER UPDATE OF search_text ON agenda BEGIN
            INSERT INTO agenda_fts(agenda_fts,rowid,search_text) VALUES('delete',old.rowid,old.search_text);
            INSERT INTO agenda_fts(rowid,search_text) VALUES(new.rowid,new.search_text);
        END""")
        if not had_index:
            db.execute("INSERT INTO agenda_fts(agenda_fts) VALUES('rebuild')")
        for field in ("topic", "status", "district"):
            db.execute(f"CREATE INDEX IF NOT EXISTS agenda_{field} ON agenda({field})")
        db.execute("PRAGMA user_version=1")

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
                    "INSERT INTO agenda(id,meeting_id,reference,payload,search_text,topic,status,district) VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET meeting_id=excluded.meeting_id,reference=excluded.reference,payload=excluded.payload,search_text=excluded.search_text,topic=excluded.topic,status=excluded.status,district=excluded.district",
                    (
                        item.id,
                        item.meeting_id,
                        item.reference,
                        payload,
                        *self._search_fields(item.model_dump()),
                    ),
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
        return self.query()

    @staticmethod
    def _decode(rows):
        return [
            {**json.loads(row["payload"]), "meeting": json.loads(row["meeting"])} for row in rows
        ]

    @staticmethod
    def _where(q="", topic="", status=None, district="", jurisdiction="", after=None, before=None):
        clauses = []
        parameters = []
        terms = q.casefold().split()
        indexed = [term for term in terms if len(term) >= 3 and "\x00" not in term]
        if indexed:
            clauses.append("a.rowid IN (SELECT rowid FROM agenda_fts WHERE agenda_fts MATCH ?)")
            parameters.append(" AND ".join('"' + term.replace('"', '""') + '"' for term in indexed))
        for term in terms:
            clauses.append("instr(a.search_text,?)>0")
            parameters.append(term)
        for field, value in (
            ("a.topic", topic),
            ("a.status", status),
            ("a.district", district),
            ("m.jurisdiction", jurisdiction),
        ):
            if value:
                clauses.append(f"{field}=?")
                parameters.append(value)
        if after:
            clauses.append("m.date>=?")
            parameters.append(after)
        if before:
            clauses.append("m.date<=?")
            parameters.append(before)
        return (" WHERE " + " AND ".join(clauses) if clauses else ""), parameters

    def page(self, *, offset=0, limit=30, **criteria):
        where, parameters = self._where(**criteria)
        base = " FROM agenda a JOIN meetings m ON m.id=a.meeting_id"
        with self.connection() as db:
            db.execute("BEGIN")
            total = db.execute("SELECT COUNT(*)" + base + where, parameters).fetchone()[0]
            rows = db.execute(
                "SELECT a.payload,m.payload AS meeting"
                + base
                + where
                + " ORDER BY m.date DESC,a.id LIMIT ? OFFSET ?",
                (*parameters, limit, offset),
            ).fetchall()
        return {"items": self._decode(rows), "total": total, "offset": offset, "limit": limit}

    def count(self, **criteria):
        where, parameters = self._where(**criteria)
        with self.connection() as db:
            return db.execute(
                "SELECT COUNT(*) FROM agenda a JOIN meetings m ON m.id=a.meeting_id" + where,
                parameters,
            ).fetchone()[0]

    def query(
        self, q="", topic="", status=None, district="", jurisdiction="", after=None, before=None
    ):
        where, parameters = self._where(
            q=q,
            topic=topic,
            status=status,
            district=district,
            jurisdiction=jurisdiction,
            after=after,
            before=before,
        )
        with self.connection() as db:
            rows = db.execute(
                "SELECT a.payload,m.payload AS meeting FROM agenda a JOIN meetings m ON m.id=a.meeting_id"
                + where
                + " ORDER BY m.date DESC,a.id",
                parameters,
            ).fetchall()
        return self._decode(rows)

    def get_item(self, identifier):
        with self.connection() as db:
            rows = db.execute(
                "SELECT a.payload,m.payload AS meeting FROM agenda a JOIN meetings m ON m.id=a.meeting_id WHERE a.id=?",
                (identifier,),
            ).fetchall()
        return self._decode(rows)[0] if rows else None

    def facets(self):
        with self.connection() as db:
            return {
                "topics": [
                    r[0] for r in db.execute("SELECT DISTINCT topic FROM agenda ORDER BY topic")
                ],
                "districts": [
                    r[0]
                    for r in db.execute("SELECT DISTINCT district FROM agenda ORDER BY district")
                ],
                "jurisdictions": [
                    r[0]
                    for r in db.execute(
                        "SELECT DISTINCT m.jurisdiction FROM meetings m JOIN agenda a ON a.meeting_id=m.id ORDER BY m.jurisdiction"
                    )
                ],
                "total": db.execute("SELECT COUNT(*) FROM agenda").fetchone()[0],
                "demo_records": db.execute(
                    "SELECT COUNT(*) FROM agenda a JOIN meetings m ON a.meeting_id=m.id WHERE json_extract(m.payload,'$.is_demo')=1"
                ).fetchone()[0],
            }

    def timeline(self, item):
        with self.connection() as db:
            rows = db.execute(
                """SELECT a.payload,m.payload AS meeting FROM agenda a
                JOIN meetings m ON m.id=a.meeting_id WHERE a.id=? OR
                (a.reference=? AND m.jurisdiction=? AND json_extract(m.payload,'$.is_demo')=?)
                ORDER BY m.date,a.id""",
                (
                    item["id"],
                    item["reference"],
                    item["meeting"]["jurisdiction"],
                    item["meeting"]["is_demo"],
                ),
            ).fetchall()
        return self._decode(rows)

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
