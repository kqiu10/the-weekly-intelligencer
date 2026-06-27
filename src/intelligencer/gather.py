"""Assemble a manifest from config by gathering each dimension's sources.

Deterministic ``feed`` and ``api`` (NewsAPI) sources are gathered here, with zero
Claude tokens. ``search`` sources are filled by the SKILL.md orchestrator. A dead
source is skipped with a visible note; ``raw`` dimensions use the feed/snippet text
verbatim as the summary. When ``discover_og`` is set, items lacking a feed-embedded
image fall back to the article page's og:image.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os

from .config import Config, Dimension
from .feeds import fetch_feed
from .images import fetch_og_image_url
from .manifest import DimensionContent, Issue, Item, Manifest
from .providers.newsapi import NewsApiClient

logger = logging.getLogger(__name__)


def _today() -> str:
    return _dt.date.today().isoformat()


def issue_week_number(first_issue_date: str | None, issue_date: str) -> int:
    """Issue number = weeks since the first issue, 1-based (Week 1, Week 2, …)."""
    if not first_issue_date:
        return 1
    first = _dt.date.fromisoformat(first_issue_date)
    current = _dt.date.fromisoformat(issue_date)
    return max((current - first).days // 7, 0) + 1


def _parse_iso_date(value: str | None) -> _dt.date | None:
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _recent_first(items: list[Item], today: _dt.date, within_days: int) -> list[Item]:
    """Keep items published within ``[today - within_days, today]``, most-recent
    first. Undated items are dropped — we can't confirm they're in the window —
    and the date sort also corrects relevance-ordered feeds (e.g. Google News)."""
    cutoff = today - _dt.timedelta(days=within_days)
    dated: list[tuple[_dt.date, Item]] = []
    for it in items:
        d = _parse_iso_date(it.published)
        if d is not None and cutoff <= d <= today:
            dated.append((d, it))
    dated.sort(key=lambda pair: pair[0], reverse=True)
    return [it for _, it in dated]


def _make_newsapi_client(config: Config) -> NewsApiClient | None:
    cfg = config.providers.get("newsapi")
    if not cfg:
        return None
    return NewsApiClient(
        api_key=os.environ.get(cfg.get("key_env", "NEWSAPI_KEY"), ""),
        daily_limit=int(cfg.get("daily_request_limit", 100)),
        cache_ttl_hours=float(cfg.get("cache_ttl_hours", 12)),
    )


def _gather_dimension(
    dim: Dimension, *, discover_og: bool, newsapi: NewsApiClient | None, today: _dt.date
) -> DimensionContent:
    items: list[Item] = []
    notes: list[str] = []
    for source in dim.sources:
        label = source.label or ""
        src_items: list[Item] = []
        if source.type == "feed" and source.url:
            try:
                feed_items = fetch_feed(source.url)
            except Exception as exc:  # noqa: BLE001 - fail soft, surface a note
                logger.warning("feed unavailable %s: %s", source.url, exc)
                notes.append(f"A source was unavailable and was skipped: {source.url}")
                continue
            for fi in feed_items:
                src_items.append(
                    Item(
                        title=fi.title,
                        url=fi.url,
                        source=fi.source,
                        published=fi.published,
                        image=fi.image,
                        raw_text=fi.raw_text,
                        origin="feed",
                        group=label,
                    )
                )
        elif source.type == "api" and source.provider == "newsapi" and source.query:
            if newsapi is None:
                notes.append("NewsAPI provider not configured; api source skipped")
                continue
            result = newsapi.fetch(source.query)
            for it in result.items:
                it.group = label
            src_items.extend(result.items)
            if result.note:
                notes.append(result.note)
        # search sources are filled by the SKILL.md orchestrator

        # Strict recency window (e.g. past 7 days), most-recent first. Also fixes
        # relevance-ordered feeds (Google News) and drops undated items.
        if dim.within_days is not None:
            src_items = _recent_first(src_items, today, dim.within_days)
        # Cap each source independently (by-source layout); a source with no items
        # contributes nothing and its row is simply never rendered.
        if dim.max_per_source is not None:
            src_items = src_items[: dim.max_per_source]
        items.extend(src_items)

    # Overall cap only applies when there is no per-source cap.
    if dim.max_per_source is None:
        items = items[: dim.max_items]

    # Discover og:images only for the items we keep — never probe a whole feed archive.
    if discover_og:
        for item in items:
            if not item.image and item.origin == "feed" and item.url:
                item.image = fetch_og_image_url(item.url)

    if dim.summary == "raw":
        for item in items:
            if not item.summary:
                item.summary = item.raw_text

    return DimensionContent(
        name=dim.name,
        blurb=dim.blurb,
        summary_mode=dim.summary,
        layout=dim.layout,
        items=items,
        notes=notes,
    )


def build_manifest(
    config: Config, *, date: str | None = None, discover_og: bool = False
) -> Manifest:
    date_str = date or _today()
    today = _dt.date.fromisoformat(date_str)
    week = issue_week_number(config.publication.first_issue_date, date_str)
    issue = Issue(
        date=date_str,
        title=config.publication.title,
        subtitle=config.publication.subtitle,
        week=week,
    )
    newsapi = _make_newsapi_client(config)
    dimensions = [
        _gather_dimension(d, discover_og=discover_og, newsapi=newsapi, today=today)
        for d in config.dimensions
    ]
    return Manifest(issue=issue, dimensions=dimensions)
