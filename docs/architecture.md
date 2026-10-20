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

Queries split search text into case-insensitive terms; every term must appear somewhere in title, summary, source excerpt, topic, or reference. Filters are exact matches. The API supports inclusive date bounds and paginated results. Current implementation loads the joined records and filters in Python, which is simple and testable for small curated collections. Large imports will need indexed full-text search and SQL pagination.

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
