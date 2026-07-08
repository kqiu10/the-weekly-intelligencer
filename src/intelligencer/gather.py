"""Assemble a manifest from config by gathering each dimension's sources.

Deterministic ``feed`` and ``site`` sources are gathered here, with zero Claude
tokens. ``search`` sources are filled by the SKILL.md orchestrator. A dead
source is skipped with a visible note; ``raw`` dimensions use the feed/snippet text
verbatim as the summary. When ``discover_og`` is set, items lacking a feed-embedded
image fall back to the article page's og:image.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
from urllib.parse import urlparse

from .civitai import fetch_civitai
from .config import Config, Dimension
from .feeds import fetch_feed
from .images import fetch_article_preview, logo_asset_path, resolve_google_news_url
from .sites import default_link_pattern, list_site_articles
from .text import item_blurb
from .manifest import DimensionContent, Issue, Item, Manifest

logger = logging.getLogger(__name__)

# An unlabeled by-source feed/site source is a *candidate pool* (like a civitai source):
# gather brings in a bounded batch of recent items that Claude prunes to the qualifying few
# at the write stage. Bounded (not fully uncapped) so enrichment/og-discovery stays cheap.
CANDIDATE_POOL_CAP = 12


def _today() -> str:
    return _dt.date.today().isoformat()


def _week_monday(d: _dt.date) -> _dt.date:
    """The Monday that starts the calendar week containing ``d`` (weekday(): Mon=0 … Sun=6).
    Snapping dates to their Monday is what buckets issues by calendar week."""
    return d - _dt.timedelta(days=d.weekday())


def issue_week_number(first_issue_date: str | None, issue_date: str) -> int:
    """Issue number = calendar weeks (Mon–Sun) since the first issue's week, 1-based.
    Week 1 is the Mon–Sun week that contains the first issue, so it ends on the first
    Sunday on/after ``first_issue_date``; every following Monday begins the next week."""
    if not first_issue_date:
        return 1
    first = _week_monday(_dt.date.fromisoformat(first_issue_date))
    current = _week_monday(_dt.date.fromisoformat(issue_date))
    return max((current - first).days // 7, 0) + 1


def issue_week_range(issue_date: str) -> tuple[str, str]:
    """The Mon–Sun calendar week (start, end as ISO dates) that ``issue_date`` falls
    in — the same week the issue is numbered by, so 'Issue N' and this range agree."""
    monday = _week_monday(_dt.date.fromisoformat(issue_date))
    sunday = monday + _dt.timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()


def _parse_iso_date(value: str | None) -> _dt.date | None:
    if not value:
        return None
    try:
        return _dt.date.fromisoformat(value[:10])
    except (ValueError, TypeError):
        return None


def _domain(url: str) -> str:
    """Bare publisher host for an article URL (``www.anthropic.com`` → ``anthropic.com``)."""
    host = urlparse(url).netloc
    return host[4:] if host.startswith("www.") else host


def _drop_contentless(items: list[Item]) -> list[Item]:
    """Drop items we couldn't give real content: no title, or neither a preview
    image nor a blurb (a bare headline + link). Happens when a site hard-blocks
    our fetch (403), so nothing is reachable. A source may end up with fewer items
    — 0, 1, or up to its cap — which is fine."""
    return [it for it in items if it.title.strip() and (it.image or item_blurb(it) or it.stats)]


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


def _window_start(today: _dt.date, within_days: int) -> _dt.date:
    """Start of the content window: ``within_days`` back, but **never earlier than the issue's own
    calendar-week Monday** — so content matches the 'Issue N · Mon–Sun' masthead range and a mid-week
    run doesn't pull in the previous week's posts (the window is week-to-date)."""
    return max(today - _dt.timedelta(days=within_days), _week_monday(today))


def _select_in_window(items: list[Item], today: _dt.date, within_days: int) -> list[Item]:
    """Keep items published within ``[window_start, today]`` — the issue's week-to-date (see
    ``_window_start``) — dropping undated ones, and preserve the feed's own order (relevance for a
    Google News search, recency for a chronological RSS feed)."""
    cutoff = _window_start(today, within_days)
    return [
        it
        for it in items
        if (d := _parse_iso_date(it.published)) is not None and cutoff <= d <= today
    ]


def _gather_dimension(
    dim: Dimension,
    *,
    discover_og: bool,
    today: _dt.date,
    blurb_words: int = 50,
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
        elif source.type == "site" and source.url:
            # Scrape an official newsroom index for (url, date); title/image/lede
            # are filled from each article by the enrichment pass below.
            pattern = source.link_contains or default_link_pattern(source.url)
            for url, published in list_site_articles(source.url, pattern):
                src_items.append(
                    Item(
                        title="",
                        url=url,
                        source=_domain(url),
                        published=published,
                        origin="site",
                        group=label,
                    )
                )
        elif source.type == "civitai":
            # First-party Civitai images API (deterministic): the week's most-reacted,
            # safe-rated AI images as a candidate pool Claude prunes at the write stage.
            # No CIVITAI_API_KEY → fetch_civitai returns [] (graceful skip).
            cap = dim.max_per_source or dim.max_items or 5
            src_items = fetch_civitai(
                max_results=min(max(cap * 2, 10), 30),
                api_key=os.environ.get("CIVITAI_API_KEY"),
                group=label or "Civitai",
            )
        # search sources are filled by the SKILL.md orchestrator

        # Keep only items inside the recency window (e.g. past 7 days), preserving
        # the feed's own order (relevance for Google News, recency for RSS).
        if dim.within_days is not None:
            src_items = _select_in_window(src_items, today, dim.within_days)
        # An *unlabeled* by-source feed/site (like a civitai source) is a candidate pool: bring
        # in a bounded batch for Claude to prune at the write stage, left ungrouped (group="")
        # for Claude to reassign to the company each kept item is about. A *labeled* by-source
        # source is a display row capped per source; a civitai source is capped by its own fetch.
        is_candidate_pool = (
            dim.layout == "by-source" and source.type in ("feed", "site") and not source.label
        )
        if is_candidate_pool:
            src_items = src_items[:CANDIDATE_POOL_CAP]
        elif dim.max_per_source is not None and source.type != "civitai":
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
        # One fetch per article yields its title, preview image, and lede — the
        # article's own opening words (NYT-style). For `site` items this supplies
        # the title too; for feeds it replaces thin text like "Headline — Publisher".
        for item in items:
            if item.origin in ("feed", "site") and item.url:
                title, og_image, lede = fetch_article_preview(item.url, max_words=blurb_words)
                if title and not item.title:
                    item.title = title
                if og_image and not item.image:
                    item.image = og_image
                if lede:
                    item.raw_text = lede
        # An og:image can itself be a publisher-wide default reused across items.
        _drop_boilerplate_images(items)
        # Now that enrichment is done, drop any item left with neither image nor
        # blurb — a bare headline adds nothing and usually means a hard 403 block.
        items = _drop_contentless(items)

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
        title_i18n=config.publication.title_i18n,
        subtitle_i18n=config.publication.subtitle_i18n,
    )
    blurb_words = int(config.defaults.get("blurb_words", 50))
    dimensions = [
        _gather_dimension(d, discover_og=discover_og, today=today, blurb_words=blurb_words)
        for d in config.dimensions
    ]
    return Manifest(issue=issue, dimensions=dimensions)
