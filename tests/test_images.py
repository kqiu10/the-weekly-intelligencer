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


def test_og_fetch_403_is_quiet(monkeypatch, caplog):
    """A scraper block (403) returns None without logging a WARNING."""
    import logging

    import httpx

    import intelligencer.images as images

    def fake_get(url, **kwargs):
        return httpx.Response(403, request=httpx.Request("GET", url))

    monkeypatch.setattr(images.httpx, "get", fake_get)
    with caplog.at_level(logging.DEBUG, logger="intelligencer.images"):
        result = images.fetch_og_image_url("https://blocked.example/a")

    assert result is None
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)
    assert any(r.levelno == logging.DEBUG for r in caplog.records)


def test_og_fetch_500_warns(monkeypatch, caplog):
    """An unexpected server error (500) still surfaces as a WARNING."""
    import logging

    import httpx

    import intelligencer.images as images

    def fake_get(url, **kwargs):
        return httpx.Response(500, request=httpx.Request("GET", url))

    monkeypatch.setattr(images.httpx, "get", fake_get)
    with caplog.at_level(logging.DEBUG, logger="intelligencer.images"):
        result = images.fetch_og_image_url("https://broken.example/a")

    assert result is None
    assert any(r.levelno >= logging.WARNING for r in caplog.records)


def test_extract_og_image_rejects_placeholder():
    """An unfilled og:image template must not become a (404-bound) image URL."""
    html = (
        '<meta property="og:image" content="<link or path of image for opengraph, twitter-cards>">'
    )
    assert extract_og_image(html) is None


def test_cache_image_404_is_quiet(monkeypatch, caplog, tmp_path):
    """A 404 on the image download fails soft and stays quiet (debug, not warning)."""
    import logging

    import httpx

    import intelligencer.images as images

    def fake_get(url, **kwargs):
        return httpx.Response(404, request=httpx.Request("GET", url))

    monkeypatch.setattr(images.httpx, "get", fake_get)
    with caplog.at_level(logging.DEBUG, logger="intelligencer.images"):
        out = images.cache_image("https://x.example/a.jpg", tmp_path, "2026-06-27")

    assert out is None
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)
