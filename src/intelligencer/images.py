"""og:image extraction, feed-embedded image discovery, and local caching."""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import re
from pathlib import Path
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .net import BROWSER_HEADERS, DEFAULT_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")

# Company logos ship with the package as brand-colored SVGs, keyed by slug
# (assets/logos/<slug>.svg). They are copied into each issue's dist/ so the
# rendered HTML stays self-contained and portable.
LOGO_DIR = Path(__file__).parent / "assets" / "logos"


def logo_asset_path(slug: str | None) -> str | None:
    """Map a logo ``slug`` to its dist-relative path (``assets/logos/<slug>.svg``)
    if the packaged SVG exists, else None. Keeps a typo'd slug from becoming a
    broken <img> — it simply renders name-only. SVG-only by design; a brand whose
    only real artwork is raster ships it embedded as a data URI inside the SVG."""
    if slug and (LOGO_DIR / f"{slug}.svg").exists():
        return f"assets/logos/{slug}.svg"
    return None


def copy_logo(rel_path: str, output_dir: str | Path) -> bool:
    """Copy a packaged logo (referenced by its dist-relative ``rel_path``) into
    ``output_dir``. Copies on first use or when the packaged logo has changed
    (e.g. recolored), so dist/ never keeps a stale asset. Returns whether the
    file exists at the destination afterward."""
    src = Path(__file__).parent / rel_path
    dest = Path(output_dir) / rel_path
    if not src.exists():
        logger.warning("logo asset missing: %s", rel_path)
        return dest.exists()
    data = src.read_bytes()
    if not dest.exists() or dest.read_bytes() != data:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    return True


# Statuses that mean "this site won't give us its preview image" — expected and
# unrecoverable (scraper blocks like Cloudflare 403, or no such page). We treat
# these as a quiet "no image", not a warning, so a normal run stays clean.
_BLOCKED_STATUS = {401, 403, 404, 410, 451}


def _is_real_image_ref(value: str) -> bool:
    """Reject unfilled template placeholders some sites leave in their og:image
    meta (e.g. Qwen's literal '<link or path of image for opengraph ...>'), which
    would otherwise become a guaranteed-404 image URL."""
    if not value:
        return False
    if any(c in value for c in "<>\"'") or any(c.isspace() for c in value):
        return False
    return True


def extract_og_image(html: str | bytes, base_url: str = "") -> str | None:
    """Return the page's og:image (or twitter:image) URL, or None."""
    soup = BeautifulSoup(html, "html.parser")
    for attrs in (
        {"property": "og:image"},
        {"name": "og:image"},
        {"property": "twitter:image"},
        {"name": "twitter:image"},
    ):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            content = tag["content"].strip()
            if not _is_real_image_ref(content):
                continue
            return urljoin(base_url, content) if base_url else content
    return None


def _looks_image(url: str | None, mime: str | None) -> bool:
    if mime and mime.startswith("image/"):
        return True
    if url and url.lower().rsplit("?", 1)[0].endswith(_IMAGE_EXTS):
        return True
    return False


def image_from_feed_entry(entry) -> str | None:
    """Pull a preview image from a feedparser entry (no network)."""
    for key in ("media_thumbnail", "media_content"):
        for media in entry.get(key, []) or []:
            url = media.get("url")
            if _looks_image(url, media.get("type")):
                return url
    for enc in entry.get("enclosures", []) or []:
        href = enc.get("href") or enc.get("url")
        if _looks_image(href, enc.get("type")):
            return href
    return None


def _get_article(article_url: str, timeout: float) -> httpx.Response | None:
    """GET an article page, fail-soft → None. Expected blocks/absences
    (Cloudflare 403, missing page, …) are logged at debug, not as a warning, so a
    normal run isn't buried in expected noise; anything else warns."""
    try:
        resp = httpx.get(
            article_url,
            headers=BROWSER_HEADERS,
            follow_redirects=True,
            timeout=timeout,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        level = logging.DEBUG if code in _BLOCKED_STATUS else logging.WARNING
        logger.log(level, "article fetch failed for %s (HTTP %s)", article_url, code)
        return None
    except Exception as exc:  # noqa: BLE001 - network/timeout, fail soft
        logger.warning("article fetch failed for %s: %s", article_url, exc)
        return None
    return resp


def fetch_og_image_url(article_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Fetch an article page and return its og:image URL. Fail-soft → None."""
    resp = _get_article(article_url, timeout)
    return extract_og_image(resp.text, base_url=str(resp.url)) if resp is not None else None


_LEDE_SKIP_TAGS = (
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "figure",
    "figcaption",
    "noscript",
    "button",
)
_LEDE_SKIP_HINTS = (
    "cookie",
    "subscribe",
    "sign up",
    "advertisement",
    "newsletter",
    "all rights reserved",
    "©",
)


# JSON-LD article types whose body/description we accept as a lede fallback.
_ARTICLE_LD_TYPES = {
    "NewsArticle",
    "Article",
    "ReportageNewsArticle",
    "BlogPosting",
    "LiveBlogPosting",
    "AnalysisNewsArticle",
    "OpinionNewsArticle",
}
_SENT_END = re.compile(r"[.!?][\"'”’)\]]?(?=\s|$)")


def _clean_text(value: str) -> str:
    """Strip any tags/entities and collapse whitespace (JSON-LD body may carry
    HTML entities like ``&mdash;`` or stray markup)."""
    return " ".join(BeautifulSoup(value, "html.parser").get_text(" ").split())


def _lede_from_paragraphs(root, max_words: int) -> str:
    """Join the leading substantive <p> paragraphs (skipping short captions and
    boilerplate) until about ``max_words`` words are gathered."""
    parts: list[str] = []
    words = 0
    for para in root.find_all("p"):
        text = " ".join(para.get_text(" ", strip=True).split())
        if len(text) < 40:  # skip captions, bylines, and other short boilerplate
            continue
        if any(hint in text.lower() for hint in _LEDE_SKIP_HINTS):
            continue
        parts.append(text)
        words += len(text.split())
        if words >= max_words:
            break
    return " ".join(parts)


def _lede_from_structured_data(html: str | bytes) -> str:
    """Article text from a page's ``NewsArticle`` JSON-LD — the fallback for
    JavaScript-rendered pages, whose served HTML has no <p> body but still ships
    a JSON-LD block for SEO. Prefers ``articleBody``, else the ``description``."""
    soup = BeautifulSoup(html, "html.parser")
    best_desc = ""
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or tag.get_text() or "")
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        stack = [data]
        while stack:
            node = stack.pop()
            if isinstance(node, list):
                stack.extend(node)
                continue
            if not isinstance(node, dict):
                continue
            if isinstance(node.get("@graph"), list):
                stack.extend(node["@graph"])
            node_type = node.get("@type", "")
            types = {node_type} if isinstance(node_type, str) else set(node_type or ())
            if not (types & _ARTICLE_LD_TYPES):
                continue
            body = node.get("articleBody")
            if isinstance(body, str) and body.strip():
                return _clean_text(body)
            desc = node.get("description")
            if isinstance(desc, str) and desc.strip() and not best_desc:
                best_desc = _clean_text(desc)
    return best_desc


def _clip_lede(text: str, max_words: int) -> str:
    """Trim to about ``max_words`` words, ending on a sentence boundary when one
    falls in range (so short blurbs read cleanly), else a hard cut with an ellipsis."""
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    clipped = " ".join(words[:max_words])
    ends = [m.end() for m in _SENT_END.finditer(clipped)]
    if ends and ends[-1] >= len(clipped) * 0.6:
        return clipped[: ends[-1]].strip()
    return clipped.rstrip(",.;:—- ") + "…"


def extract_lede(html: str | bytes, max_words: int = 50) -> str | None:
    """Return the article's own opening (about ``max_words`` words) — its lede,
    verbatim, *not* a generated summary. Reads the leading <p> paragraphs and, for
    JavaScript-rendered pages with no readable body, falls back to the NewsArticle
    JSON-LD (article body, else the publisher's description). Fail-soft → None."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(list(_LEDE_SKIP_TAGS)):
        tag.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    text = _lede_from_paragraphs(root, max_words)
    if len(text.split()) < max_words:  # thin/empty body → try structured data
        structured = _lede_from_structured_data(html)
        if len(structured.split()) > len(text.split()):
            text = structured
    if not text.strip():
        return None
    return _clip_lede(text, max_words)


def extract_title(html: str | bytes) -> str:
    """The article's own title: og:title (cleanest), else <title>, else the first
    <h1>. Used for scraped ``site`` sources, which have no feed-supplied title."""
    soup = BeautifulSoup(html, "html.parser")
    for attrs in ({"property": "og:title"}, {"name": "twitter:title"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and (tag.get("content") or "").strip():
            return tag["content"].strip()
    if soup.title and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    h1 = soup.find("h1")
    return h1.get_text(" ", strip=True) if h1 else ""


def fetch_article_preview(
    article_url: str, *, timeout: float = DEFAULT_TIMEOUT, max_words: int = 50
) -> tuple[str | None, str | None, str | None]:
    """Fetch an article page once and return ``(title, og:image URL, lede text)``
    — any may be None. One request feeds the headline, preview image, and blurb."""
    resp = _get_article(article_url, timeout)
    if resp is None:
        return None, None, None
    html = resp.text
    return (
        extract_title(html) or None,
        extract_og_image(html, base_url=str(resp.url)),
        extract_lede(html, max_words),
    )


_GNEWS_BATCHEXECUTE = "https://news.google.com/_/DotsSplashUi/data/batchexecute"


def _parse_batchexecute_url(text: str) -> str | None:
    """Pull the resolved article URL out of a Google ``batchexecute`` response
    (an XSSI-guarded, doubly JSON-encoded blob)."""
    start = text.find("[")
    if start == -1:
        return None
    try:
        rows = json.loads(text[start:])
    except json.JSONDecodeError:
        return None
    for row in rows:
        if (
            isinstance(row, list)
            and len(row) > 2
            and row[1] == "Fbv4je"
            and isinstance(row[2], str)
        ):
            try:
                payload = json.loads(row[2])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, list) and len(payload) > 1 and payload[0] == "garturlres":
                return payload[1]
    return None


def resolve_google_news_url(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Resolve a Google News RSS redirect (``news.google.com/rss/articles/...``)
    to the real publisher article URL via Google's ``batchexecute`` endpoint.

    Fail-soft → None: a non-Google-News URL, a layout change, or any network
    error just yields None, and the caller keeps the original link. Only worth
    calling on feed items — native publisher feeds return None immediately."""
    if "news.google.com" not in url or "/articles/" not in url:
        return None
    try:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=timeout
        ) as client:
            page = client.get(url)
            page.raise_for_status()
            div = BeautifulSoup(page.text, "html.parser").select_one("c-wiz > div")
            if div is None:
                return None
            aid, ts, sig = (
                div.get("data-n-a-id"),
                div.get("data-n-a-ts"),
                div.get("data-n-a-sg"),
            )
            if not (aid and ts and sig):
                return None
            inner = [
                "garturlreq",
                [
                    [
                        "X",
                        "X",
                        ["X", "X"],
                        None,
                        None,
                        1,
                        1,
                        "US:en",
                        None,
                        1,
                        None,
                        None,
                        None,
                        None,
                        None,
                        0,
                        1,
                    ],
                    "X",
                    "X",
                    1,
                    [1, 1, 1],
                    1,
                    1,
                    None,
                    0,
                    0,
                    None,
                    0,
                ],
                aid,
                ts,
                sig,
            ]
            body = "f.req=" + quote(json.dumps([[["Fbv4je", json.dumps(inner), None, "generic"]]]))
            resp = client.post(
                _GNEWS_BATCHEXECUTE,
                headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                content=body,
            )
            resp.raise_for_status()
            return _parse_batchexecute_url(resp.text)
    except Exception as exc:  # noqa: BLE001 - network/parse, fail soft
        logger.debug("google-news resolve failed for %s: %s", url, exc)
        return None


def _download(url: str, timeout: float) -> tuple[bytes, str | None]:
    if url.startswith("file://"):
        return Path(url[len("file://") :]).read_bytes(), None
    resp = httpx.get(
        url, headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=timeout
    )
    resp.raise_for_status()
    return resp.content, resp.headers.get("content-type")


def _ext_for(url: str, content_type: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in _IMAGE_EXTS:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        if guessed:
            return guessed
    return ".img"


def cache_image(
    image_url: str, output_dir: str | Path, date: str, *, timeout: float = DEFAULT_TIMEOUT
) -> str | None:
    """Download an image to ``<output_dir>/assets/<date>/`` and return its path
    relative to ``output_dir`` (usable as an ``<img src>``). Fail-soft → None.

    Expected unavailability (404/403/etc.) is logged at debug, not as a warning."""
    try:
        data, content_type = _download(image_url, timeout)
    except httpx.HTTPStatusError as exc:
        code = exc.response.status_code
        level = logging.DEBUG if code in _BLOCKED_STATUS else logging.WARNING
        logger.log(level, "image unavailable for %s (HTTP %s)", image_url, code)
        return None
    except Exception as exc:  # noqa: BLE001 - network/timeout, fail soft
        logger.warning("image cache failed for %s: %s", image_url, exc)
        return None
    name = hashlib.sha1(image_url.encode("utf-8")).hexdigest()[:16] + _ext_for(
        image_url, content_type
    )
    rel = f"assets/{date}/{name}"
    dest = Path(output_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return rel
