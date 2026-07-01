"""Manifest schema (de)serialization for the v2 fields."""

from intelligencer.manifest import DimensionContent, Issue, Manifest


def test_issue_tldr_round_trips_and_defaults():
    m = Manifest(issue=Issue(date="2026-07-01", title="T", tldr="A short executive summary."))
    assert Manifest.from_dict(m.to_dict()).issue.tldr == "A short executive summary."
    # an older manifest dict without 'tldr' still loads (defaults to empty)
    older = Manifest.from_dict({"issue": {"date": "2026-07-01", "title": "T"}, "dimensions": []})
    assert older.issue.tldr == ""


def test_dimension_trends_round_trips():
    d = DimensionContent(
        name="Social",
        trends=[
            {
                "descriptor": "AI cats flying jets",
                "tags": ["cats"],
                "magnitude": 7,
                "heat_tier": 2,
                "direction": "up",
                "recurring": True,
                "samples": ["https://x"],
            }
        ],
    )
    m = Manifest(issue=Issue(date="2026-07-06", title="T"), dimensions=[d])
    back = Manifest.from_dict(m.to_dict())
    assert back.dimensions[0].trends[0]["heat_tier"] == 2
    assert back.dimensions[0].trends[0]["descriptor"] == "AI cats flying jets"
