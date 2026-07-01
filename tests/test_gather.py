"""B2: issue week number computed from the first-issue date."""

from intelligencer.gather import (
    _drop_boilerplate_images,
    _drop_contentless,
    build_manifest,
    issue_week_number,
)
from intelligencer.manifest import Item


def test_drop_contentless_keeps_items_with_image_or_blurb():
    """A bare headline (no image, text only echoes the title) is dropped; items
    with a preview image or a real blurb survive."""
    has_image = Item(title="T1", url="u1", image="assets/x.jpg", raw_text="T1 Publisher")
    has_blurb = Item(title="T2", url="u2", raw_text="A real lede sentence about the news.")
    echo_only = Item(title="T3 - Publisher", url="u3", source="pub.com", raw_text="T3 Publisher")
    bare = Item(title="T4", url="u4")
    no_title = Item(title="", url="u5", image="assets/y.jpg")  # scrape failed to get a title
    kept = _drop_contentless([has_image, has_blurb, echo_only, bare, no_title])
    assert kept == [has_image, has_blurb]


def test_shared_image_is_dropped_unique_kept():
    """An image reused across items (feed boilerplate) is nulled; a unique one stays."""
    shared = "https://cdn.example/generic-thumb.png"
    unique = "https://cdn.example/real-article.jpg"
    items = [
        Item(title="a", url="https://x/a", image=shared),
        Item(title="b", url="https://x/b", image=shared),
        Item(title="c", url="https://x/c", image=unique),
        Item(title="d", url="https://x/d", image=None),
    ]
    _drop_boilerplate_images(items)
    assert [it.image for it in items] == [None, None, unique, None]


def test_first_issue_is_week1():
    assert issue_week_number("2026-06-26", "2026-06-26") == 1


def test_one_week_later_is_week2():
    assert issue_week_number("2026-06-26", "2026-07-03") == 2


def test_missing_first_date_defaults_to_week1():
    assert issue_week_number(None, "2026-06-26") == 1


def test_fifty_two_weeks_later_is_week53():
    # 364 days == exactly 52 weeks later
    assert issue_week_number("2026-06-26", "2027-06-25") == 53


def test_raw_summary_uses_feed_text():
    from pathlib import Path

    from intelligencer.config import Config, Dimension, Output, Publication, Source

    fixtures = Path(__file__).parent / "fixtures"
    cfg = Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(
                name="D",
                summary="raw",
                sources=[Source(type="feed", url=f"file://{fixtures / 'sample_feed.xml'}")],
            )
        ],
    )
    item = build_manifest(cfg).dimensions[0].items[0]
    assert item.summary and item.summary == item.raw_text


def test_og_discovery_only_probes_kept_items(monkeypatch):
    from pathlib import Path

    import intelligencer.gather as gather
    from intelligencer.config import Config, Dimension, Output, Publication, Source

    fixtures = Path(__file__).parent / "fixtures"
    calls: list[str] = []
    monkeypatch.setattr(
        gather, "fetch_article_preview", lambda url, **k: (calls.append(url), (None, None, None))[1]
    )
    cfg = Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(
                name="D",
                max_items=2,
                sources=[Source(type="feed", url=f"file://{fixtures / 'feed_many.xml'}")],
            )
        ],
    )
    manifest = build_manifest(cfg, discover_og=True)
    assert len(manifest.dimensions[0].items) == 2
    # feed has 5 entries; og:image must be probed only for the 2 kept items
    assert len(calls) <= 2


def test_by_source_caps_each_lab_and_skips_empty():
    """Each source is capped independently; a source with no items is skipped."""
    from pathlib import Path

    from intelligencer.config import Config, Dimension, Output, Publication, Source

    fixtures = Path(__file__).parent / "fixtures"
    cfg = Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(
                name="Labs",
                layout="by-source",
                max_per_source=2,
                sources=[
                    # feed_many.xml has 5 entries → capped to 2
                    Source(type="feed", url=f"file://{fixtures / 'feed_many.xml'}", label="LabA"),
                    # empty feed → contributes nothing, so LabB never appears
                    Source(type="feed", url=f"file://{fixtures / 'feed_empty.xml'}", label="LabB"),
                ],
            )
        ],
    )
    dim = build_manifest(cfg).dimensions[0]
    assert dim.layout == "by-source"
    groups = [it.group for it in dim.items]
    assert groups == ["LabA", "LabA"]  # capped at 2, and LabB skipped entirely
    assert "LabB" not in groups


def test_within_days_window_filters_sorts_and_drops_undated():
    """Strict past-week window: drop stale + undated items, most-recent first."""
    from pathlib import Path

    from intelligencer.config import Config, Dimension, Output, Publication, Source

    fixtures = Path(__file__).parent / "fixtures"
    cfg = Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(
                name="Labs",
                layout="by-source",
                within_days=7,
                max_per_source=5,
                sources=[
                    Source(type="feed", url=f"file://{fixtures / 'feed_dated.xml'}", label="Lab")
                ],
            )
        ],
    )
    items = build_manifest(cfg, date="2026-06-27").dimensions[0].items
    # feed order is D2,D1,D3,D4; today=06-27 keeps only D1 (06-26) and D2 (06-22),
    # sorted newest-first; D3 (06-17, stale) and D4 (undated) are dropped.
    assert [it.title for it in items] == ["D1 recent", "D2 older-recent"]
