"""B1: og:image extraction, feed-embedded images, lede/title parsing, and caching."""

import json
import logging
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


def _stub_httpx_status(monkeypatch, status):
    """Force images.httpx.get to return a bare response with the given status code."""
    import httpx

    import intelligencer.images as images

    monkeypatch.setattr(
        images.httpx,
        "get",
        lambda url, **k: httpx.Response(status, request=httpx.Request("GET", url)),
    )
    return images


def test_extract_og_image_reads_resolves_and_rejects_placeholder():
    present = (FIXTURES / "article_with_og.html").read_text()
    absent = (FIXTURES / "article_without_og.html").read_text()
    assert extract_og_image(present) == "http://img.example/og.jpg"
    assert extract_og_image(absent) is None
    # a relative og:image is resolved against the page URL
    assert (
        extract_og_image(
            '<meta property="og:image" content="/img/pic.jpg">',
            base_url="https://site.example/article",
        )
        == "https://site.example/img/pic.jpg"
    )
    # an unfilled og:image template must not become a (404-bound) URL
    placeholder = (
        '<meta property="og:image" '
        'content="<link or path of image for opengraph, twitter-cards>">'
    )
    assert extract_og_image(placeholder) is None


def test_image_from_feed_entry_enclosure():
    parsed = feedparser.parse((FIXTURES / "sample_feed.xml").read_bytes())
    assert image_from_feed_entry(parsed.entries[0]) == "http://example.com/first.jpg"
    assert image_from_feed_entry(parsed.entries[1]) is None


def test_cache_image_downloads_and_failsofts(tmp_path):
    rel = cache_image(f"file://{FIXTURES / 'pixel.png'}", tmp_path, "2026-06-26")
    assert rel and rel.startswith("assets/2026-06-26/")
    assert (tmp_path / rel).exists()
    # a missing source fails soft (None), never raises
    assert cache_image("file:///nonexistent/none.png", tmp_path, "2026-06-26") is None


def _png_bytes(w, h):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (w, h), (200, 30, 30)).save(buf, "PNG")
    return buf.getvalue()


def test_shrink_image_downsizes_oversized_preserving_format():
    """A 2880px publisher og:image serves a 132×88 slot — shrink to ≤600px longest side,
    same format (cached filenames keep their extension)."""
    import io

    from PIL import Image

    from intelligencer.images import shrink_image

    out = shrink_image(_png_bytes(1200, 800))
    img = Image.open(io.BytesIO(out))
    assert img.format == "PNG"
    assert img.size == (600, 400)  # ≤600 longest side, aspect preserved
    assert len(out) < len(_png_bytes(1200, 800))


def test_shrink_image_flattens_animated_gif_to_first_frame():
    """A 10.8 MB 203-frame GIF in a thumbnail slot → static, resized first frame."""
    import io

    from PIL import Image

    from intelligencer.images import shrink_image

    frames = [Image.new("RGB", (900, 500), c) for c in ((255, 0, 0), (0, 255, 0))]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:])
    out = shrink_image(buf.getvalue())
    img = Image.open(io.BytesIO(out))
    assert img.format == "GIF"
    assert getattr(img, "n_frames", 1) == 1  # static now
    assert max(img.size) <= 600


def test_shrink_image_strips_jpeg_metadata():
    import io

    from PIL import Image

    from intelligencer.images import shrink_image

    exif = Image.Exif()
    exif[0x0110] = "TestCam 9000"  # Model tag
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (10, 20, 30)).save(buf, "JPEG", exif=exif)
    out = shrink_image(buf.getvalue())
    img = Image.open(io.BytesIO(out))
    assert img.format == "JPEG"
    assert not img.getexif()  # metadata gone


def test_shrink_image_leaves_small_static_images_untouched():
    from intelligencer.images import shrink_image

    data = _png_bytes(100, 80)
    assert shrink_image(data) == data  # no churn when nothing to fix


def test_shrink_image_failsofts_on_garbage_bytes():
    from intelligencer.images import shrink_image

    junk = b"not an image at all"
    assert shrink_image(junk) == junk


def test_og_fetch_403_is_quiet(monkeypatch, caplog):
    """A scraper block (403) returns None quietly (debug, not warning)."""
    images = _stub_httpx_status(monkeypatch, 403)
    with caplog.at_level(logging.DEBUG, logger="intelligencer.images"):
        assert images.fetch_og_image_url("https://blocked.example/a") is None
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)
    assert any(r.levelno == logging.DEBUG for r in caplog.records)


def test_cache_image_404_is_quiet(monkeypatch, caplog, tmp_path):
    """A 404 on the image download fails soft and stays quiet (debug, not warning)."""
    images = _stub_httpx_status(monkeypatch, 404)
    with caplog.at_level(logging.DEBUG, logger="intelligencer.images"):
        assert images.cache_image("https://x.example/a.jpg", tmp_path, "2026-06-27") is None
    assert not any(r.levelno >= logging.WARNING for r in caplog.records)


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
