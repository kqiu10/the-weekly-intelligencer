"""og:image extraction, feed-embedded image discovery, and local caching."""

from __future__ import annotations

import hashlib
import logging
import mimetypes
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .net import DEFAULT_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".gif")


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


def fetch_og_image_url(article_url: str, *, timeout: float = DEFAULT_TIMEOUT) -> str | None:
    """Fetch an article page and return its og:image URL. Fail-soft → None."""
    try:
        resp = httpx.get(
            article_url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=timeout,
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - fail soft
        logger.warning("og:image fetch failed for %s: %s", article_url, exc)
        return None
    return extract_og_image(resp.text, base_url=str(resp.url))


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
    relative to ``output_dir`` (usable as an ``<img src>``). Fail-soft → None."""
    try:
        data, content_type = _download(image_url, timeout)
    except Exception as exc:  # noqa: BLE001 - fail soft
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
