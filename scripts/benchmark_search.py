"""Disposable synthetic benchmark; run after installing CivicLens with pip install -e ."""

import json
import platform
import sqlite3
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter

from civiclens.demo import sample_bundle
from civiclens.models import ImportBundle
from civiclens.storage import Store


def measure(call):
    elapsed = []
    result = None
    for _ in range(7):
        start = perf_counter()
        result = call()
        elapsed.append((perf_counter() - start) * 1000)
    return median(elapsed), result


def main():
    print(json.dumps({"python": platform.python_version(), "sqlite": sqlite3.sqlite_version}))
    with TemporaryDirectory(prefix="civiclens-bench-") as directory:
        store = Store(Path(directory) / "bench.db")
        seed = sample_bundle()
        template = seed.items[0]
        for start in range(0, 10000, 1000):
            items = [
                template.model_copy(
                    update={
                        "id": f"bench-{number:05d}",
                        "title": f"Agenda observation {number}",
                        "summary": "neighborhoodtoken"
                        if number % 1000 == 0
                        else "Routine municipal discussion",
                    }
                )
                for number in range(start, start + 1000)
            ]
            store.import_bundle(ImportBundle(meetings=seed.meetings, items=items))
            count = start + 1000
            if count not in (1000, 10000):
                continue

            def legacy():
                rows = [
                    r
                    for r in store.records()
                    if "neighborhoodtoken"
                    in " ".join(
                        str(r.get(k) or "")
                        for k in ("title", "summary", "source_excerpt", "topic", "reference")
                    ).casefold()
                ]
                return {"items": rows[:5], "total": len(rows)}

            old_ms, old = measure(legacy)
            new_ms, new = measure(lambda: store.page(q="neighborhoodtoken", limit=5))
            assert old["total"] == new["total"]
            assert [r["id"] for r in old["items"]] == [r["id"] for r in new["items"]]
            print(
                json.dumps(
                    {
                        "records": count,
                        "matched": new["total"],
                        "scan_median_ms": round(old_ms, 3),
                        "indexed_median_ms": round(new_ms, 3),
                        "speedup": round(old_ms / new_ms, 1),
                    }
                )
            )


if __name__ == "__main__":
    main()
