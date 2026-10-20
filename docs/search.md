# Indexed search

## Semantics

Search is an AND of literal casefolded substrings, not a full-text query language. It covers titles, summaries, source excerpts, topics and decision references. For example, `hous trans` can match a housing record that mentions transit. `OR` and quotation marks have no special user-facing meaning. Unicode casefolding matches `Straße` with `STRASSE`; accents are preserved, so `cafe` does not equal `café`.

Stored text is casefolded in Python and indexed by SQLite FTS5's case-sensitive trigram tokenizer. Quoted terms of at least three characters select candidate row IDs. Parameterized SQL `instr` checks enforce the literal contract for all terms. One/two-character and NUL-containing terms skip the trigram candidate step; they can require scanning text. Exact filters have B-tree indexes. Results are date-descending, then item-ID ascending, not relevance ranked.

`Store.page` counts and selects a bounded page in a single read transaction. It decodes only that page's source JSON. Watchlists use SQL counts. Exports still materialize all matches, and offset pagination can become expensive at deep offsets. Neither this version nor its benchmark establishes million-record capacity.

## Migration and recovery

SQLite 3.34+ with FTS5 trigram support is required. Stop older CivicLens instances and make a database backup before installing 0.3. Do not run older code against the new schema. First startup adds denormalized columns, backfills existing records, creates the external-content FTS index and its triggers, and sets `user_version=1`. These search-schema operations are transactional; a missing FTS module/tokenizer or other migration failure rolls them back. Source payloads, revision history and watchlists are not rewritten. Later startups do not rebuild the index.

Imports update observations and search triggers in the same transaction, including revision changes. Repeated unchanged imports do not add revisions or index entries. The test suite covers upgrades from the four-column agenda table, literal/Unicode equivalence, failed imports, missing FTS rollback and stable pagination.

Back up a live workspace with SQLite's online backup API, or copy it only when all writers have stopped. Do not copy an active main database without its WAL state. If migration fails, retain the backup, use a supported SQLite build and restart; do not delete source records to repair an index.

## Reproduce a small synthetic benchmark

After installing the package, run from the repository root:

```sh
python scripts/benchmark_search.py
```

The script creates a temporary database, inserts fictional observations in 1,000-item batches, and removes only its own temporary files on completion. It prints Python/SQLite versions and compares the median of seven warm runs: loading/decoding every joined record and filtering in Python versus indexed SQL count plus a five-item page. Both paths must return identical IDs and totals. Setup/import time is excluded. The selective term matches one item per thousand; this favors an index and does not represent every workload.

An initial local Windows run with 10,000 records measured roughly 106 ms for the scan versus 3 ms for indexed pagination (about 36×). This is one synthetic experiment, not a performance guarantee. Broad queries, short terms, long excerpts, disk speed and deep offsets can change the result substantially. Run the script on your own deployment before setting capacity expectations.
