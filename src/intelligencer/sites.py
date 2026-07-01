"""Crawl an official newsroom listing page for recent article links + dates.

For companies with no usable RSS feed, we scrape their news/blog index instead of
a third-party aggregator: collect the article links (those matching
``link_contains``) and the publish date shown beside each. The article's title,
image, and lede are filled later by the generic article extractor — this module
only answers "which recent URLs, and dated when".
"""

from __future__ import annotations

import datetime as _dt
import logging
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .net import BROWSER_HEADERS, DEFAULT_TIMEOUT

logger = logging.getLogger(__name__)

_MONTHS = "Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec"
_DATE_RE = re.compile(rf"(?:{_MONTHS})[a-z]* \d{{1,2}},? \d{{4}}|\d{{4}}-\d{{2}}-\d{{2}}")


def _parse_date(text: str) -> str | None:
    """Parse a listing date ('Jun 30, 2026', 'June 30, 2026', '2026-06-30') to ISO."""
    text = text.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    m = re.match(r"([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})", text)
    if m:
        try:
            parsed = _dt.datetime.strptime(
                f"{m.group(1)[:3]} {int(m.group(2))} {m.group(3)}", "%b %d %Y"
            )
        except ValueError:
            return None
        return parsed.date().isoformat()
    return None


def _nearest_date(anchor) -> str | None:
    """Walk up from a link to find the date shown in its listing row/card."""
    node = anchor
    for _ in range(5):
        node = node.parent
        if node is None:
            break
        match = _DATE_RE.search(node.get_text(" ", strip=True))
        if match:
            return _parse_date(match.group(0))
    return None


def parse_listing(
    html: str | bytes, base_url: str, link_contains: str
) -> list[tuple[str, str | None]]:
    """Return ``[(article_url, iso_date_or_None), ...]`` from a listing page, in
    page order (newest first), skipping the section root and duplicate links."""
    soup = BeautifulSoup(html, "html.parser")
    marker = link_contains.strip("/").rsplit("/", 1)[-1]
    out: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if link_contains not in href:
            continue
        url = urljoin(base_url, href).split("?")[0].split("#")[0].rstrip("/")
        if url in seen or url.rsplit("/", 1)[-1] == marker:  # skip the "/news" root itself
            continue
        seen.add(url)
        out.append((url, _nearest_date(anchor)))
    return out


def list_site_articles(
    listing_url: str, link_contains: str, *, timeout: float = DEFAULT_TIMEOUT
) -> list[tuple[str, str | None]]:
    """Fetch a newsroom listing and return its article links + dates. Fail-soft →
    [] on any network error (the source is simply skipped, like a dead feed)."""
    try:
        resp = httpx.get(
            listing_url, headers=BROWSER_HEADERS, follow_redirects=True, timeout=timeout
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - network, fail soft
        logger.warning("site listing unavailable %s: %s", listing_url, exc)
        return []
    return parse_listing(resp.text, str(resp.url), link_contains)


def default_link_pattern(listing_url: str) -> str:
    """Derive a link filter from the listing path (e.g. ``.../news`` → ``/news/``)."""
    path = urlparse(listing_url).path.strip("/")
    return f"/{path}/" if path else "/"
