from .models import ImportBundle


def sample_bundle():
    meetings = [
        {
            "id": "demo-council-oct",
            "date": "2026-10-14",
            "body": "City Council",
            "title": "October regular session",
        },
        {
            "id": "demo-planning-sep",
            "date": "2026-09-09",
            "body": "Planning Commission",
            "title": "September public hearing",
        },
        {
            "id": "demo-council-aug",
            "date": "2026-08-12",
            "body": "City Council",
            "title": "August regular session",
        },
    ]
    for meeting in meetings:
        meeting.update(
            jurisdiction="Sample City",
            source_url="https://example.invalid/meetings/" + meeting["id"],
            is_demo=True,
        )
    examples = [
        (
            "demo-bike",
            "demo-council-oct",
            "Protected bike lane pilot on Franklin Avenue",
            "A twelve-month pilot would connect 3rd and 9th Streets. Staff will report safety outcomes before a permanent design is considered.",
            "transportation",
            "proposed",
            "Central",
            "TR-26-18",
        ),
        (
            "demo-housing-final",
            "demo-council-oct",
            "Housing preservation fund receives approval",
            "The council approved a fund to preserve 240 rental units near transit. The next step is an application process for eligible buildings.",
            "housing",
            "approved",
            "North",
            "HO-26-07",
        ),
        (
            "demo-housing-hearing",
            "demo-planning-sep",
            "Public hearing: housing preservation fund",
            "The commission tabled the proposal and requested clearer eligibility rules and tenant protections before the council vote.",
            "housing",
            "tabled",
            "North",
            "HO-26-07",
        ),
        (
            "demo-housing-start",
            "demo-council-aug",
            "Proposal to preserve transit-adjacent rental housing",
            "Staff proposed a preservation fund and referred the plan to a public hearing. The proposal targets existing rental homes rather than new construction.",
            "housing",
            "proposed",
            "North",
            "HO-26-07",
        ),
        (
            "demo-water",
            "demo-planning-sep",
            "Stormwater resilience design standards",
            "The commission tabled new retention standards pending a cost analysis for small developments.",
            "environment",
            "tabled",
            "Citywide",
            "EN-26-03",
        ),
        (
            "demo-library",
            "demo-council-oct",
            "Extended evening hours at Westside Library",
            "A six-month trial of evening library hours was approved, with attendance and staffing reviewed monthly.",
            "public services",
            "approved",
            "West",
            "PS-26-12",
        ),
    ]
    items = [
        dict(
            id=id,
            meeting_id=meeting_id,
            title=title,
            summary=summary,
            source_excerpt="FICTIONAL DEMONSTRATION RECORD: " + summary,
            topic=topic,
            status=status,
            district=district,
            reference=reference,
            summary_method="demo",
            source_url="https://example.invalid/agenda/" + id,
        )
        for id, meeting_id, title, summary, topic, status, district, reference in examples
    ]
    return ImportBundle(meetings=meetings, items=items)


def seed(store):
    if not store.meetings():
        store.import_bundle(sample_bundle())
