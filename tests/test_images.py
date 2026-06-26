"""B1: og:image extraction, feed-embedded images, and caching."""

from pathlib import Path

import feedparser

from intelligencer.images import cache_image, extract_og_image, image_from_feed_entry

FIXTURES = Path(__file__).parent / "fixtures"


def test_extract_og_image_present():
    html = (FIXTURES / "article_with_og.html").read_text()
    assert extract_og_image(html) == "http://img.example/og.jpg"


def test_extract_og_image_absent():
    html = (FIXTURES / "article_without_og.html").read_text()
    assert extract_og_image(html) is None


def test_extract_og_image_relative_resolved():
    html = '<meta property="og:image" content="/img/pic.jpg">'
    got = extract_og_image(html, base_url="https://site.example/article")
    assert got == "https://site.example/img/pic.jpg"


def test_image_from_feed_entry_enclosure():
    parsed = feedparser.parse((FIXTURES / "sample_feed.xml").read_bytes())
    assert image_from_feed_entry(parsed.entries[0]) == "http://example.com/first.jpg"
    assert image_from_feed_entry(parsed.entries[1]) is None


def test_cache_image_downloads(tmp_path):
    src = f"file://{FIXTURES / 'pixel.png'}"
    rel = cache_image(src, tmp_path, "2026-06-26")
    assert rel is not None
    assert rel.startswith("assets/2026-06-26/")
    assert (tmp_path / rel).exists()


def test_cache_image_failsoft(tmp_path):
    assert cache_image("file:///nonexistent/none.png", tmp_path, "2026-06-26") is None
