"""Manifest schema (de)serialization — one round-trip covering every optional field,
plus backwards-compat defaults for older manifests (consolidated, not one test
per field)."""

from intelligencer.manifest import DimensionContent, Issue, Item, Manifest


def test_manifest_round_trips_all_fields_and_defaults_for_older_dicts():
    item = Item(
        title="Anker lists in HK",
        url="u",
        stats={"views": 1000000, "likes": 12000, "comments": 840},
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

    it = back.dimensions[0].items[0]
    assert it.stats == {"views": 1000000, "likes": 12000, "comments": 840}
    assert it.i18n["zh"]["title"] == "安克登陆港交所"
    dim = back.dimensions[0]
    assert dim.name_i18n["zh"] == "重塑跨境品牌"
    assert dim.blurb_i18n["en"] == "How AI reshapes brands abroad"
    assert back.issue.tldr == "week" and back.issue.tldr_i18n["zh"] == "本周"
    assert back.issue.title_i18n["zh"] == "周悉智能"
    assert back.issue.subtitle_i18n["zh"] == "每周简报"

    # An older manifest dict still loads: missing optional fields get defaults, and stale
    # keys from removed schema versions (heat_tier/trends) are tolerated rather than
    # crashing Item(**...).
    older = {
        "issue": {"date": "2026-07-05", "title": "T"},
        "dimensions": [
            {
                "name": "D",
                "trends": [{"descriptor": "stale"}],
                "items": [{"title": "v", "url": "u", "heat_tier": 2}],
            }
        ],
    }
    old = Manifest.from_dict(older)
    assert old.issue.tldr == "" and old.issue.tldr_i18n == {}
    assert old.issue.title_i18n == {} and old.issue.subtitle_i18n == {}
    assert old.dimensions[0].name_i18n == {} and old.dimensions[0].blurb_i18n == {}
    assert old.dimensions[0].items[0].stats == {} and old.dimensions[0].items[0].i18n == {}
