"""Deterministic feed fetching + parsing (RSS/Atom)."""

from __future__ import annotations

import datetime
import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from .images import image_from_feed_entry
from .net import DEFAULT_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)


@dataclass
class FeedItem:
    title: str
    url: str
    source: str
    published: str | None
    raw_text: str
    image: str | None = None


def _read_bytes(url: str, timeout: float) -> bytes:
    if url.startswith("file://"):
        return Path(url[len("file://") :]).read_bytes()
    resp = httpx.get(
        url, timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )
    resp.raise_for_status()
    return resp.content


def _clean(text: str) -> str:
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def _entry_date(entry) -> str | None:
    """Normalize an entry's date to an ISO ``YYYY-MM-DD`` string, or None."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    try:
        return datetime.date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday).isoformat()
    except (ValueError, TypeError):
        return None


def _entry_source(entry, link: str, feed_title: str) -> str:
    """The real publisher of an item. Google News items carry a ``<source>``
    element naming the actual outlet, so prefer that over ``news.google.com``."""
    src = entry.get("source")
    if src:
        host = urlparse(src.get("href") or "").netloc
        if host:
            return host.replace("www.", "")
        if src.get("title"):
            return src["title"]
    host = urlparse(link).netloc.replace("www.", "") if link else ""
    return host or feed_title


def fetch_feed(url: str, *, timeout: float = DEFAULT_TIMEOUT) -> list[FeedItem]:
    """Fetch + parse one RSS/Atom feed. Raises on a read/network error so the caller
    can record a fail-soft note; returns ``[]`` for an empty/unparseable feed."""
    content = _read_bytes(url, timeout)
    parsed = feedparser.parse(content)
    feed_title = parsed.feed.get("title", "") if parsed.feed else ""
    items: list[FeedItem] = []
    for entry in parsed.entries:
        link = entry.get("link", "")
        items.append(
            FeedItem(
                title=entry.get("title", "").strip(),
                url=link,
                source=_entry_source(entry, link, feed_title),
                published=_entry_date(entry),
                raw_text=_clean(entry.get("summary", "")),
                image=image_from_feed_entry(entry),
            )
        )
    return items
