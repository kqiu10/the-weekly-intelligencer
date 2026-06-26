"""Assemble a manifest from config by gathering each dimension's sources.

Deterministic ``feed`` sources only here. ``api`` (C1) and ``search`` (the SKILL.md
orchestrator) are wired in later tasks. A dead source is skipped with a visible note;
``raw`` dimensions use the feed text verbatim as the summary (no Claude needed). When
``discover_og`` is set, items lacking a feed-embedded image fall back to the article
page's og:image.
"""

from __future__ import annotations

import datetime as _dt
import logging

from .config import Config, Dimension
from .feeds import fetch_feed
from .images import fetch_og_image_url
from .manifest import DimensionContent, Issue, Item, Manifest

logger = logging.getLogger(__name__)


def _today() -> str:
    return _dt.date.today().isoformat()


def issue_volume_number(first_issue_date: str | None, issue_date: str) -> tuple[int, int]:
    """Compute (volume, number) where a volume spans 52 weekly issues."""
    if not first_issue_date:
        return 1, 1
    first = _dt.date.fromisoformat(first_issue_date)
    current = _dt.date.fromisoformat(issue_date)
    weeks = max((current - first).days // 7, 0)
    return weeks // 52 + 1, weeks % 52 + 1


def _gather_dimension(dim: Dimension, *, discover_og: bool) -> DimensionContent:
    items: list[Item] = []
    notes: list[str] = []
    for source in dim.sources:
        if source.type == "feed" and source.url:
            try:
                feed_items = fetch_feed(source.url)
            except Exception as exc:  # noqa: BLE001 - fail soft, surface a note
                logger.warning("feed unavailable %s: %s", source.url, exc)
                notes.append(f"A source was unavailable and was skipped: {source.url}")
                continue
            for fi in feed_items:
                image = fi.image
                if not image and discover_og and fi.url:
                    image = fetch_og_image_url(fi.url)
                items.append(
                    Item(
                        title=fi.title,
                        url=fi.url,
                        source=fi.source,
                        published=fi.published,
                        image=image,
                        raw_text=fi.raw_text,
                        origin="feed",
                    )
                )
        # api / search sources are handled in later tasks

    items = items[: dim.max_items]
    if dim.summary == "raw":
        for item in items:
            if not item.summary:
                item.summary = item.raw_text

    return DimensionContent(
        name=dim.name,
        blurb=dim.blurb,
        summary_mode=dim.summary,
        items=items,
        notes=notes,
    )


def build_manifest(
    config: Config, *, date: str | None = None, discover_og: bool = False
) -> Manifest:
    date_str = date or _today()
    volume, number = issue_volume_number(config.publication.first_issue_date, date_str)
    issue = Issue(
        date=date_str,
        title=config.publication.title,
        subtitle=config.publication.subtitle,
        volume=volume,
        number=number,
    )
    dimensions = [_gather_dimension(d, discover_og=discover_og) for d in config.dimensions]
    return Manifest(issue=issue, dimensions=dimensions)
