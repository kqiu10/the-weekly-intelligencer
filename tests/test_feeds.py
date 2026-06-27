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
    # the RFC-822 pubDate is normalized to ISO YYYY-MM-DD
    assert it.published == "2026-06-26"
