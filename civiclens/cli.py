import argparse
import csv
import json
import os
import sys
from pathlib import Path

from .models import AgendaItem, ImportBundle, Meeting
from .storage import Store

def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate and import source-linked civic records.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Check a JSON bundle without writing to a database")
    validate.add_argument("file", type=Path)
    load = sub.add_parser("import", help="Atomically import a JSON bundle into a local database")
    load.add_argument("file", type=Path)
    load.add_argument("--db", default=os.getenv("CIVICLENS_DB", "data/civiclens.sqlite3"))
    convert = sub.add_parser(
        "convert-csv", help="Convert a single meeting's agenda CSV into a validated JSON bundle"
    )
    convert.add_argument("file", type=Path)
    convert.add_argument("--meeting-id", required=True)
    convert.add_argument("--date", required=True)
    convert.add_argument("--body", required=True)
    convert.add_argument("--title", required=True)
    convert.add_argument("--jurisdiction", required=True)
    convert.add_argument("--source-url", required=True)
    convert.add_argument("--demo", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "convert-csv":
            meeting = Meeting(
                id=args.meeting_id,
                date=args.date,
                body=args.body,
                title=args.title,
                jurisdiction=args.jurisdiction,
                source_url=args.source_url,
                is_demo=args.demo,
            )
            with args.file.open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            items = []
            for row in rows:
                data = {k: v for k, v in row.items() if v and k}
                data["meeting_id"] = meeting.id
                items.append(AgendaItem.model_validate(data))
            bundle = ImportBundle(meetings=[meeting], items=items)
            print(bundle.model_dump_json(indent=2))
            return 0
        bundle = ImportBundle.model_validate_json(args.file.read_text(encoding="utf-8-sig"))
        if args.command == "validate":

            known = {meeting.id for meeting in bundle.meetings}
            if any(item.meeting_id not in known for item in bundle.items):
                raise ValueError(
                    "Standalone validation requires all referenced meetings in this bundle"
                )
            print(
                json.dumps(
                    {"valid": True, "meetings": len(bundle.meetings), "items": len(bundle.items)}
                )
            )
        else:
            print(json.dumps(Store(args.db).import_bundle(bundle)))
        return 0
    except (ValueError, OSError, csv.Error) as error:
        print(str(error), file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
