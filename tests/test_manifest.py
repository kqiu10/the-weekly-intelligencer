"""Manifest schema (de)serialization for the v2 fields."""

from intelligencer.manifest import DimensionContent, Issue, Item, Manifest


def test_item_stats_round_trips_and_defaults():
    d = DimensionContent(
        name="Social",
        items=[Item(title="v", url="u", stats={"views": 1000000, "likes": 12000, "comments": 840})],
    )
    m = Manifest(issue=Issue(date="2026-07-02", title="T"), dimensions=[d])
    back = Manifest.from_dict(m.to_dict())
    assert back.dimensions[0].items[0].stats == {"views": 1000000, "likes": 12000, "comments": 840}
    # an older manifest item without 'stats' still loads (defaults to {})
    older = {
        "issue": {"date": "2026-07-02", "title": "T"},
        "dimensions": [{"name": "D", "items": [{"title": "v", "url": "u"}]}],
    }
    assert Manifest.from_dict(older).dimensions[0].items[0].stats == {}


def test_issue_tldr_round_trips_and_defaults():
    m = Manifest(issue=Issue(date="2026-07-01", title="T", tldr="A short executive summary."))
    assert Manifest.from_dict(m.to_dict()).issue.tldr == "A short executive summary."
    # an older manifest dict without 'tldr' still loads (defaults to empty)
    older = Manifest.from_dict({"issue": {"date": "2026-07-01", "title": "T"}, "dimensions": []})
    assert older.issue.tldr == ""


def test_i18n_fields_round_trip_and_default_empty():
    """SPEC §10.9: items carry per-language {title, summary, raw_text}; dimensions carry
    name/blurb pairs; the issue carries a TL;DR pair. All optional — an older manifest
    without them loads with empty dicts (monolingual render unchanged)."""
    item = Item(
        title="Anker lists in HK",
        url="u",
        i18n={
            "zh": {"title": "安克登陆港交所", "summary": "上市了", "raw_text": "7月2日…"},
            "en": {"title": "Anker lists in HK", "summary": "Listed.", "raw_text": "On July 2…"},
        },
    )
    d = DimensionContent(
        name="Rewriting Cross-Border Branding",
        name_i18n={"zh": "重塑跨境品牌", "en": "Rewriting Cross-Border Branding"},
        blurb_i18n={"zh": "AI 如何重塑品牌出海", "en": "How AI reshapes brands abroad"},
        items=[item],
    )
    issue = Issue(
        date="2026-07-05",
        title="The Weekly Intelligencer",
        title_i18n={"zh": "周悉智能"},
        subtitle="A weekly briefing",
        subtitle_i18n={"zh": "每周简报"},
        tldr="week",
        tldr_i18n={"zh": "本周", "en": "week"},
    )
    back = Manifest.from_dict(Manifest(issue=issue, dimensions=[d]).to_dict())
    assert back.dimensions[0].items[0].i18n["zh"]["title"] == "安克登陆港交所"
    assert back.dimensions[0].name_i18n["zh"] == "重塑跨境品牌"
    assert back.dimensions[0].blurb_i18n["en"] == "How AI reshapes brands abroad"
    assert back.issue.tldr_i18n["zh"] == "本周"
    assert back.issue.title_i18n["zh"] == "周悉智能"
    assert back.issue.subtitle_i18n["zh"] == "每周简报"

    older = {
        "issue": {"date": "2026-07-05", "title": "T"},
        "dimensions": [{"name": "D", "items": [{"title": "v", "url": "u"}]}],
    }
    old = Manifest.from_dict(older)
    assert old.issue.tldr_i18n == {}
    assert old.issue.title_i18n == {} and old.issue.subtitle_i18n == {}
    assert old.dimensions[0].name_i18n == {} and old.dimensions[0].blurb_i18n == {}
    assert old.dimensions[0].items[0].i18n == {}


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
