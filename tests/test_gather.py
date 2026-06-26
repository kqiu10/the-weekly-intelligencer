"""B2: issue volume/number computed from the first-issue date."""

from intelligencer.gather import build_manifest, issue_volume_number


def test_first_issue_is_vol1_no1():
    assert issue_volume_number("2026-06-26", "2026-06-26") == (1, 1)


def test_one_week_later_is_no2():
    assert issue_volume_number("2026-06-26", "2026-07-03") == (1, 2)


def test_missing_first_date_defaults():
    assert issue_volume_number(None, "2026-06-26") == (1, 1)


def test_fifty_two_weeks_rolls_to_vol2():
    # 364 days == exactly 52 weeks later
    assert issue_volume_number("2026-06-26", "2027-06-25") == (2, 1)


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
