"""B2: issue week number computed from the first-issue date."""

from intelligencer.gather import build_manifest, issue_week_number


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
    monkeypatch.setattr(gather, "fetch_og_image_url", lambda url, **k: calls.append(url) or None)
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
