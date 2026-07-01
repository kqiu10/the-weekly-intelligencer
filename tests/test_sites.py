"""Official newsroom listing crawl: link + date extraction."""

from intelligencer.sites import _parse_date, default_link_pattern, parse_listing

_LISTING = """
<html><body>
  <a href="/news">News</a>
  <ul>
    <li><a href="/news/claude-sonnet-5">Introducing Claude Sonnet 5</a><span>Jun 30, 2026</span></li>
    <li><a href="/news/older-post">Old</a><time>2026-06-01</time></li>
    <li><a href="/about">About</a></li>
    <li><a href="/news/claude-sonnet-5">dup link, same URL</a><span>Jun 30, 2026</span></li>
  </ul>
</body></html>
"""


def test_parse_listing_extracts_urls_and_dates():
    pairs = parse_listing(_LISTING, "https://www.anthropic.com/news", "/news/")
    # section root (/news), non-matching (/about), and the dup are all excluded
    assert pairs == [
        ("https://www.anthropic.com/news/claude-sonnet-5", "2026-06-30"),
        ("https://www.anthropic.com/news/older-post", "2026-06-01"),
    ]


def test_parse_listing_undated_link_kept_with_none():
    html = '<a href="/blog/x">A post with no visible date</a>'
    assert parse_listing(html, "https://ai.meta.com/blog/", "/blog/") == [
        ("https://ai.meta.com/blog/x", None)
    ]


def test_parse_date_formats():
    assert _parse_date("Jun 30, 2026") == "2026-06-30"
    assert _parse_date("June 30, 2026") == "2026-06-30"
    assert _parse_date("2026-06-30") == "2026-06-30"
    assert _parse_date("sometime soon") is None


def test_default_link_pattern():
    assert default_link_pattern("https://x.ai/news") == "/news/"
    assert default_link_pattern("https://ai.meta.com/blog/") == "/blog/"
