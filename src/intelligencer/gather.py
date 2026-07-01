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
from .images import fetch_article_preview, logo_asset_path, resolve_google_news_url
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


def _drop_boilerplate_images(items: list[Item]) -> None:
    """Null out any preview image shared by more than one item. A real article
    image is unique to that article, so a repeated URL is boilerplate — e.g. the
    generic thumbnail Google News returns for every entry in a feed — and showing
    the same picture on story after story just looks broken."""
    from collections import Counter

    counts = Counter(it.image for it in items if it.image)
    for it in items:
        if it.image and counts[it.image] > 1:
            it.image = None


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
    dim: Dimension,
    *,
    discover_og: bool,
    newsapi: NewsApiClient | None,
    today: _dt.date,
    blurb_words: int = 160,
) -> DimensionContent:
    items: list[Item] = []
    notes: list[str] = []
    logos: dict[str, str] = {}
    for source in dim.sources:
        label = source.label or ""
        # Map each labeled source to its packaged logo (by-source layout).
        if label and source.logo:
            rel = logo_asset_path(source.logo)
            if rel:
                logos[label] = rel
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

    # Only touch the network for the items we keep — never probe a whole feed archive.
    if discover_og:
        # Google News links are opaque redirects; resolve them to the real article
        # so the link works and its og:image is reachable. Native feeds no-op fast.
        for item in items:
            if item.origin == "feed" and item.url:
                real = resolve_google_news_url(item.url)
                if real:
                    item.url = real
    # Drop feed boilerplate (e.g. Google News' generic thumbnail) first, so those
    # items fall through to og:image discovery instead of showing a shared picture.
    _drop_boilerplate_images(items)
    if discover_og:
        # One fetch per article yields both its preview image and its lede — the
        # article's own opening words (NYT-style), which replace thin feed text
        # like Google News' "Headline — Publisher".
        for item in items:
            if item.origin == "feed" and item.url:
                og_image, lede = fetch_article_preview(item.url, max_words=blurb_words)
                if og_image and not item.image:
                    item.image = og_image
                if lede:
                    item.raw_text = lede
        # An og:image can itself be a publisher-wide default reused across items.
        _drop_boilerplate_images(items)

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
        logos=logos,
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
    blurb_words = int(config.defaults.get("blurb_words", 160))
    dimensions = [
        _gather_dimension(
            d, discover_og=discover_og, newsapi=newsapi, today=today, blurb_words=blurb_words
        )
        for d in config.dimensions
    ]
    return Manifest(issue=issue, dimensions=dimensions)
