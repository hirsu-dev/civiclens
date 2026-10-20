# Roadmap

## Shipped in 0.2

Atomic JSON imports, single-meeting CSV conversion, search/filtering, source excerpts, decision timelines, item revisions, shared watchlists, CSV export, CLI, package builds and CI.

## Shipped in 0.3

FTS5 trigram indexing with legacy-data migration, literal/Unicode search equivalence, SQL filtering/counting/pagination and live watchlist counts without loading all records.

## Next focused increments

1. Add one municipal adapter with documented source licensing, fixtures and update semantics.
2. Add cursor pagination and streaming exports for larger collections.
3. Add meeting metadata revisions and explicit links for amended/replaced decision references.
4. Add reviewed extractive summaries with page-level citations and correction flags.
5. Add opt-in saved-search digests after user accounts and notification preferences exist.

Maps and automated document extraction should wait until source coverage and provenance are reliable. Never silently infer a vote outcome from ambiguous minutes.
