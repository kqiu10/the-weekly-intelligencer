"""B1: og:image extraction, feed-embedded images, and caching."""

import json
from pathlib import Path

import feedparser

from intelligencer.images import (
    _parse_batchexecute_url,
    cache_image,
    extract_lede,
    extract_og_image,
    extract_title,
    image_from_feed_entry,
    resolve_google_news_url,
)

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


_ARTICLE_HTML = """
<html><body>
  <nav><p>Home — About — Subscribe now to our daily newsletter for more</p></nav>
  <article>
    <p>Byline</p>
    <p>The company announced on Tuesday a sweeping new policy that will reshape
       how its largest models are trained and deployed across the whole industry.</p>
    <p>Analysts said the move could pressure rivals to follow, though questions
       about cost and safety remain unanswered for the moment.</p>
  </article>
</body></html>
"""


def test_extract_lede_joins_body_paragraphs_and_truncates():
    lede = extract_lede(_ARTICLE_HTML, max_words=10)
    words = lede.split()
    assert words[:4] == ["The", "company", "announced", "on"]
    assert len(words) == 10
    assert words[-1].endswith("…")
    assert "Subscribe" not in lede  # nav boilerplate skipped
    assert "Byline" not in lede  # short paragraph skipped


def test_extract_lede_no_truncation_when_short():
    lede = extract_lede(_ARTICLE_HTML, max_words=500)
    assert not lede.endswith("…")
    assert lede.startswith("The company announced")
    assert "Analysts said the move" in lede


def test_extract_lede_none_when_no_body_text():
    assert extract_lede("<html><body><div>no paragraphs here at all</div></body></html>") is None
    assert extract_lede("<html><body><p>tiny</p></body></html>") is None


def test_extract_lede_falls_back_to_jsonld_article_body():
    """A JS-rendered page (no <p> body) still yields text from NewsArticle JSON-LD."""
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@context":"https://schema.org","@type":"NewsArticle","headline":"H",'
        '"articleBody":"The agency approved the merger on Monday after a lengthy review. '
        'Shares of both companies rose in early trading."}'
        "</script></head><body><div>app shell, no paragraphs</div></body></html>"
    )
    lede = extract_lede(html, max_words=50)
    assert lede.startswith("The agency approved the merger on Monday")


def test_extract_lede_jsonld_graph_description_fallback():
    """When no articleBody exists, an article node's description in @graph is used."""
    html = (
        '<html><head><script type="application/ld+json">'
        '{"@graph":[{"@type":"WebPage"},'
        '{"@type":"Article","description":"A short official description of the story."}]}'
        "</script></head><body></body></html>"
    )
    assert extract_lede(html, max_words=50) == "A short official description of the story."


def test_extract_lede_ends_on_sentence_boundary():
    """A budget that lands mid-paragraph backs up to the last full sentence."""
    p = (
        "Alpha beta gamma delta epsilon zeta eta theta iota kappa. "
        "Lambda mu nu xi omicron pi rho sigma tau upsilon. "
        "Phi chi psi omega alpha beta gamma delta epsilon zeta."
    )
    html = f"<html><body><article><p>{p}</p></article></body></html>"
    lede = extract_lede(html, max_words=25)
    assert lede.endswith(".") and not lede.endswith("…")


def test_extract_title_prefers_og_then_falls_back():
    assert (
        extract_title('<meta property="og:title" content="Real Title"><title>Site | Brand</title>')
        == "Real Title"
    )
    assert (
        extract_title("<html><head><title>Fallback Title</title></head></html>") == "Fallback Title"
    )
    assert extract_title("<html><body><h1>H1 Title</h1></body></html>") == "H1 Title"
    assert extract_title("<html><body><p>no title anywhere</p></body></html>") == ""


def test_resolve_google_news_url_ignores_non_gnews():
    """A normal publisher URL isn't a Google News redirect — returns None, no network."""
    assert resolve_google_news_url("https://openai.com/index/some-post") is None
    assert resolve_google_news_url("https://news.google.com/foo") is None


def test_parse_batchexecute_extracts_real_url():
    inner = '["garturlres","https://pub.example/real-article",null,"sig"]'
    body = ")]}'\n\n" + json.dumps(
        [["wrb.fr", "Fbv4je", inner, None, None, None, "generic"], ["di", 22]]
    )
    assert _parse_batchexecute_url(body) == "https://pub.example/real-article"


def test_parse_batchexecute_missing_returns_none():
    assert _parse_batchexecute_url(")]}'\n\n" + json.dumps([["wrb.fr", "other", "[]"]])) is None
    assert _parse_batchexecute_url("not json at all") is None


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
