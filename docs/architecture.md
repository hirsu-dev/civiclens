# Architecture

```text
Source records ─ CSV converter / JSON bundle
                            │
                     Pydantic validation
                            │
Browser or CLI ─ FastAPI ─ transactional SQLite store
      │                     ├─ meetings
      └─ filtered records   ├─ agenda observations
         decision timeline  ├─ observation revisions
         saved searches     └─ saved searches
```

## Model and provenance

A meeting has a stable ID, date, jurisdiction, body, source URL, and demo flag. An agenda observation belongs to one meeting and carries its own source URL, excerpt, summary method, topic, district and status. A decision reference links observations across meetings, but only within an exact jurisdiction and matching demo flag. Each new meeting observation needs its own item ID.

The app does not infer whether a motion passed. Status and summary are supplied by the importer and must be verified against the source. `summary_method=extractive` is a provenance label, not an instruction to run an extraction model. Source URLs accept HTTP/HTTPS only. CivicLens does not fetch these URLs or render imported HTML.

## Import transaction

1. Validate the bundle schema, field bounds and unique IDs.
2. Verify all referenced meeting IDs exist in the database or bundle.
3. Upsert the meetings and agenda observations in one transaction.
4. Append a revision for every new or changed observation. Exact repeats create no revision.
5. Commit all changes together; validation/reference errors leave no partial data.

An item's revision history records changes to that observation, not a new legislative event. Meeting metadata is updated in place and has no separate revision history. Timelines describe separate observations ordered by meeting date, with stable ID tie-breaking for same-day meetings.

## Querying

Queries split search text into case-insensitive literal terms; every term must appear somewhere in title, summary, source excerpt, topic, or reference. Python casefolding is applied at ingestion and query time, preserving Unicode matching. The denormalized text is indexed with an FTS5 case-sensitive trigram tokenizer. Terms of at least three characters narrow candidate row IDs; parameterized `instr` predicates confirm every term literally. Short/NUL-containing terms skip FTS. Quoted FTS terms prevent query-operator injection. Filters and inclusive date bounds run in SQL.

The API counts and pages matching rows in one read transaction, decoding only the returned page. Watchlists use SQL counts rather than loading all records. B-tree indexes cover topic, status, district, meeting/reference and jurisdiction/date lookups. CSV export still materializes all matching records; it is not a streaming large-dataset export.

The first 0.3 startup transaction adds search columns, backfills legacy records, creates triggers and rebuilds the external-content index. Agenda upserts and index triggers share the import transaction. Failed imports cannot expose partial search results. Source JSON and existing revisions are unchanged. Subsequent startups do not rebuild the index. SQLite with FTS5 trigram support is required; migration errors roll back the search-schema transaction. Details and a reproducible synthetic benchmark are in [search.md](search.md).

Watchlists persist a query and compute a current match count. They have no per-user ownership or notification delivery in this version. CSV exports use the same filters and neutralize spreadsheet formula prefixes.

## Endpoints

| Endpoint | Behavior |
| --- | --- |
| `GET /api/agenda` | Search/filter results, total count, offset and limit |
| `GET /api/agenda/{id}` | Observation, decision timeline and import revisions |
| `GET /api/meetings` | Meetings ordered by date |
| `GET /api/facets` | Available topics, communities and districts |
| `POST /api/import` | Validate and import a bundle atomically |
| `GET /api/import-template` | Clearly fictional sample bundle |
| `GET/POST /api/saved-searches` | List queries with counts, or save one |
| `DELETE /api/saved-searches/{id}` | Remove a saved query |
| `GET /api/export.csv` | Export matching records |

Configured write tokens protect imports and saved-query writes. Reads remain workspace-wide. CSP, text escaping, parameterized SQL and HTTP-only source schemes provide boundaries; they are not substitutes for account authentication when hosting publicly.

Back up with the service stopped or with SQLite's online backup API so active WAL state is not lost.
