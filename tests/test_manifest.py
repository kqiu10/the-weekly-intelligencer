"""Manifest schema (de)serialization for the v2 fields."""

from intelligencer.manifest import Issue, Manifest


def test_issue_tldr_round_trips_and_defaults():
    m = Manifest(issue=Issue(date="2026-07-01", title="T", tldr="A short executive summary."))
    assert Manifest.from_dict(m.to_dict()).issue.tldr == "A short executive summary."
    # an older manifest dict without 'tldr' still loads (defaults to empty)
    older = Manifest.from_dict({"issue": {"date": "2026-07-01", "title": "T"}, "dimensions": []})
    assert older.issue.tldr == ""
