"""B2: issue week number computed from the first-issue date."""

import datetime as dt

from intelligencer.gather import (
    _drop_boilerplate_images,
    _drop_contentless,
    _select_in_window,
    build_manifest,
    issue_week_number,
    issue_week_range,
)
from intelligencer.manifest import Item


def test_select_in_window_keeps_feed_order_and_drops_out_of_window():
    today = dt.date(2026, 7, 1)
    items = [
        Item(title="a", url="u1", source="mobileappdaily.com", published="2026-06-30"),
        Item(title="b", url="u2", source="scmp.com", published="2026-06-24"),
        Item(title="c", url="u3", source="reuters.com", published="2026-06-25"),
        Item(title="stale", url="u4", source="reuters.com", published="2026-06-01"),  # >7 days
        Item(title="undated", url="u5", source="reuters.com", published=None),  # can't place
    ]
    out = _select_in_window(items, today, within_days=7)
    # stale + undated dropped; the feed's own order (relevance) is taken as given
    assert [it.title for it in out] == ["a", "b", "c"]


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


def test_issue_number_buckets_by_calendar_week():
    """The core rule: Issue 1 is the Mon–Sun week containing the first issue, so it
    ends on that Sunday and the next Monday starts Issue 2 (not a rolling 7-day count
    from the launch weekday). Missing anchor falls back to Issue 1."""
    launch = "2026-06-26"  # a Friday
    assert issue_week_number(launch, "2026-06-26") == 1  # launch day
    assert issue_week_number(launch, "2026-06-28") == 1  # Sunday — still Issue 1
    assert issue_week_number(launch, "2026-06-29") == 2  # Monday — Issue 2 begins
    assert issue_week_number(launch, "2026-07-09") == 3  # a Thursday three weeks in
    assert issue_week_number(None, "2026-06-26") == 1  # no anchor → Issue 1


def test_issue_week_range_is_the_containing_mon_sun_week():
    # Wed 2026-07-01 → its week runs Mon 06-29 .. Sun 07-05
    assert issue_week_range("2026-07-01") == ("2026-06-29", "2026-07-05")
    # a Sunday is the end of its week, not the start of the next
    assert issue_week_range("2026-06-28") == ("2026-06-22", "2026-06-28")


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
