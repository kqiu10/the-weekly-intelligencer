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


def test_select_in_window_caps_start_at_the_issue_week_monday():
    # generated Wed 2026-07-01 → the issue week starts Mon 2026-06-29, so anything before that
    # Monday is dropped even if it's within 7 days (window is week-to-date, not a rolling 7 days).
    today = dt.date(2026, 7, 1)
    items = [
        Item(title="mon", url="u1", source="x.com", published="2026-06-29"),  # week Monday — in
        Item(title="tue", url="u2", source="x.com", published="2026-06-30"),  # in
        Item(title="today", url="u3", source="x.com", published="2026-07-01"),  # in
        Item(title="prev-wk", url="u4", source="x.com", published="2026-06-25"),  # last week — out
        Item(title="undated", url="u5", source="x.com", published=None),  # can't place — out
    ]
    out = _select_in_window(items, today, within_days=7)
    # feed order preserved; last-week + undated dropped
    assert [it.title for it in out] == ["mon", "tue", "today"]


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


def _youtube_cfg():
    from intelligencer.config import Config, Dimension, Output, Publication, Source

    return Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(
                name="Social",
                layout="by-source",
                max_per_source=2,
                within_days=7,
                sources=[Source(type="youtube", label="YouTube Shorts", query="AI video")],
            )
        ],
    )


def test_youtube_source_without_key_yields_empty_dimension(monkeypatch):
    """No YOUTUBE_API_KEY → the youtube source is a graceful no-op (no network, no error)."""
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    dim = build_manifest(_youtube_cfg(), date="2026-07-01").dimensions[0]
    assert dim.name == "Social" and dim.items == []  # build succeeds, card just empty


def test_youtube_candidates_land_uncapped_for_claude_to_prune(monkeypatch):
    """With a key, API candidates flow into the manifest — a pool Claude prunes later, so
    they are NOT truncated to max_per_source here — and the window drives publishedAfter."""
    import intelligencer.gather as gather

    captured = {}

    def fake_fetch(query, *, published_after, max_results, api_key, group, timeout=10.0):
        captured.update(published_after=published_after, max_results=max_results, group=group)
        return [
            Item(
                title=f"AI clip {i}",
                url=f"https://www.youtube.com/watch?v=v{i}",
                source="youtube.com",
                published="2026-06-30",
                image=f"https://i.ytimg.com/vi/v{i}/hqdefault.jpg",
                origin="youtube",
                group=group,
            )
            for i in range(4)
        ]

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    monkeypatch.setattr(gather, "fetch_youtube", fake_fetch)
    dim = build_manifest(_youtube_cfg(), date="2026-07-01").dimensions[0]
    assert [it.origin for it in dim.items] == ["youtube"] * 4  # all 4 kept, not capped to 2
    assert all(it.group == "YouTube Shorts" for it in dim.items)
    assert captured["published_after"] == "2026-06-29T00:00:00Z"  # capped at the issue-week Monday
    assert captured["max_results"] >= 4


def test_unlabeled_by_source_feed_is_a_candidate_pool_not_capped_per_source():
    """An *unlabeled* by-source feed is a candidate pool (like youtube): gather does NOT cap
    it to max_per_source — Claude prunes it at the write stage — and leaves group empty for
    Claude to set to the company each kept item is about. (A *labeled* by-source feed stays a
    display row, capped per source — see test_by_source_caps_each_lab_and_skips_empty.)"""
    from pathlib import Path

    from intelligencer.config import Config, Dimension, Output, Publication, Source

    fixtures = Path(__file__).parent / "fixtures"
    cfg = Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(
                name="Factory",
                layout="by-source",
                max_per_source=2,
                # feed_many.xml has 5 entries; unlabeled → candidate pool, all 5 survive
                sources=[Source(type="feed", url=f"file://{fixtures / 'feed_many.xml'}")],
            )
        ],
    )
    dim = build_manifest(cfg).dimensions[0]
    assert len(dim.items) == 5  # NOT capped to 2 — a candidate pool for Claude to prune
    assert all(it.group == "" for it in dim.items)  # ungrouped; Claude assigns the company


def test_unlabeled_by_source_site_is_a_candidate_pool_too(monkeypatch):
    """An *unlabeled* by-source `site` source is a candidate pool exactly like an unlabeled
    feed — not capped to max_per_source, ungrouped for Claude to reassign (e.g. a scraped
    first-party newsroom/vertical index feeding the Cross-Border pool)."""
    import intelligencer.gather as gather
    from intelligencer.config import Config, Dimension, Output, Publication, Source

    monkeypatch.setattr(
        gather,
        "list_site_articles",
        lambda url, pattern, **k: [(f"https://x.com/article/{i}", "2026-07-01") for i in range(5)],
    )
    cfg = Config(
        publication=Publication(title="T"),
        output=Output(),
        dimensions=[
            Dimension(
                name="Brand",
                layout="by-source",
                max_per_source=2,
                sources=[Source(type="site", url="https://x.com")],  # unlabeled → pool
            )
        ],
    )
    dim = build_manifest(cfg).dimensions[0]
    assert len(dim.items) == 5  # NOT capped to 2
    assert all(it.group == "" for it in dim.items)


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
