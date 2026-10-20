import sqlite3

import pytest

from civiclens.demo import sample_bundle
from civiclens.storage import Store


def test_legacy_database_backfills_without_losing_revisions(tmp_path):
    path = tmp_path / "legacy.db"
    bundle = sample_bundle()
    with sqlite3.connect(path) as db:
        db.executescript("""CREATE TABLE meetings(id TEXT PRIMARY KEY,date TEXT,jurisdiction TEXT,payload TEXT);
            CREATE TABLE agenda(id TEXT PRIMARY KEY,meeting_id TEXT,reference TEXT,payload TEXT);
            CREATE TABLE revisions(sequence INTEGER PRIMARY KEY,item_id TEXT,changed_at TEXT,payload TEXT);""")
        m = bundle.meetings[0]
        item = bundle.items[0]
        db.execute(
            "INSERT INTO meetings VALUES(?,?,?,?)",
            (m.id, str(m.date), m.jurisdiction, m.model_dump_json()),
        )
        db.execute(
            "INSERT INTO agenda VALUES(?,?,?,?)",
            (item.id, item.meeting_id, item.reference, item.model_dump_json()),
        )
        db.execute(
            "INSERT INTO revisions(item_id,changed_at,payload) VALUES(?,?,?)",
            (item.id, "2026-01-01", item.model_dump_json()),
        )
    migrated = Store(path)
    assert migrated.count(q="protected lane") == 1
    assert len(migrated.revisions(item.id)) == 1
    assert Store(path).page(q="protected")["total"] == 1
    with migrated.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 1
        assert (
            db.execute(
                "INSERT INTO agenda_fts(agenda_fts,rank) VALUES('integrity-check',1)"
            ).rowcount
            == 1
        )


@pytest.mark.parametrize(
    "q",
    [
        "HO-26-07",
        "hous trans",
        "OR",
        '"housing"',
        "NEAR(foo)",
        "***",
        "x' OR 1=1 --",
        "CAFÉ",
        "STRASSE",
        "a",
        "housing\x00",
    ],
)
def test_index_preserves_literal_casefold_substring_search(tmp_path, q):
    store = Store(tmp_path / "db")
    bundle = sample_bundle()
    bundle.items[0].summary = '"housing" NEAR(foo) Straße café ***'
    store.import_bundle(bundle)
    rows = store.records()
    expected = [
        r["id"]
        for r in rows
        if all(
            t
            in " ".join(
                str(r.get(k) or "")
                for k in ("title", "summary", "source_excerpt", "topic", "reference")
            ).casefold()
            for t in q.casefold().split()
        )
    ]
    assert [r["id"] for r in store.query(q=q)] == expected
    assert store.count(q=q) == len(expected)


def test_revision_updates_index_and_failed_import_does_not_pollute_it(tmp_path):
    store = Store(tmp_path / "db")
    bundle = sample_bundle()
    bundle.items[0].summary = "Old uniqueword"
    store.import_bundle(bundle)
    bundle.items[0].summary = "New searchableword"
    store.import_bundle(bundle)
    assert store.count(q="uniqueword") == 0
    assert store.count(q="searchableword") == 1
    bundle.items[-1].meeting_id = "missing"
    bundle.items[0].summary = "Must never index rollbackword"
    with pytest.raises(ValueError):
        store.import_bundle(bundle)
    assert store.count(q="rollbackword") == 0
    assert store.count(q="searchableword") == 1


def test_sql_pagination_count_and_stable_order_agree(tmp_path):
    store = Store(tmp_path / "db")
    store.import_bundle(sample_bundle())
    all_rows = store.query(topic="housing")
    first = store.page(topic="housing", limit=2)
    second = store.page(topic="housing", offset=2, limit=2)
    assert first["total"] == second["total"] == 3
    assert [r["id"] for r in first["items"] + second["items"]] == [r["id"] for r in all_rows]
    assert store.page(q="absent")["items"] == []
    assert store.facets()["demo_records"] == 6


def test_unavailable_fts_rolls_back_search_schema(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    original_connect = sqlite3.connect
    with original_connect(path) as db:
        db.execute(
            "CREATE TABLE agenda(id TEXT PRIMARY KEY,meeting_id TEXT,reference TEXT,payload TEXT)"
        )

    class NoFTSConnection(sqlite3.Connection):
        def execute(self, sql, parameters=()):
            if sql.startswith("CREATE VIRTUAL TABLE"):
                raise sqlite3.OperationalError("no such module: fts5")
            return super().execute(sql, parameters)

    monkeypatch.setattr(
        sqlite3,
        "connect",
        lambda *args, **kwargs: original_connect(*args, **kwargs, factory=NoFTSConnection),
    )
    with pytest.raises(sqlite3.OperationalError, match="fts5"):
        Store(path)
    with original_connect(path) as db:
        assert [r[1] for r in db.execute("PRAGMA table_info(agenda)")] == [
            "id",
            "meeting_id",
            "reference",
            "payload",
        ]
        assert db.execute("PRAGMA user_version").fetchone()[0] == 0
