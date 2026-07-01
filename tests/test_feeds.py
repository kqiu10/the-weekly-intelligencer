"""Feed parsing: publisher attribution and ISO date normalization."""

from pathlib import Path

from intelligencer.feeds import fetch_feed

FIXTURES = Path(__file__).parent / "fixtures"


def test_google_news_uses_real_publisher_and_iso_date():
    items = fetch_feed(f"file://{FIXTURES / 'feed_google_news.xml'}")
    assert items, "expected at least one item"
    it = items[0]
    # the <source> names the real outlet — not the ambiguous news.google.com
    assert it.source == "reuters.com"
    # the ' - Reuters' publisher suffix Google News appends is stripped
    assert it.title == "Anthropic ships something"
    # the RFC-822 pubDate is normalized to ISO YYYY-MM-DD
    assert it.published == "2026-06-26"


def test_strip_publisher_only_removes_the_source_tail():
    from intelligencer.feeds import _strip_publisher

    entry = {"source": {"title": "The Motley Fool"}}
    assert (
        _strip_publisher("DSpark Made Nvidia's Bet Harder - The Motley Fool", entry)
        == "DSpark Made Nvidia's Bet Harder"
    )
    # native RSS (no <source>) is left alone, even with a dash in the title
    assert _strip_publisher("Introducing X - Y", {}) == "Introducing X - Y"
    # a title that doesn't end with the publisher is untouched
    assert (
        _strip_publisher("A clean headline", {"source": {"title": "Reuters"}}) == "A clean headline"
    )
