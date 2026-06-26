"""Assemble a manifest from config by gathering each dimension's sources.

Deterministic ``feed`` sources only here. ``api`` (C1) and ``search`` (the SKILL.md
orchestrator) are wired in later tasks. When ``discover_og`` is set, items lacking a
feed-embedded image fall back to fetching the article page's og:image.
"""

from __future__ import annotations

import datetime as _dt

from .config import Config, Dimension
from .feeds import fetch_feed
from .images import fetch_og_image_url
from .manifest import DimensionContent, Issue, Item, Manifest


def _today() -> str:
    return _dt.date.today().isoformat()


def _gather_dimension(dim: Dimension, *, discover_og: bool) -> DimensionContent:
    items: list[Item] = []
    for source in dim.sources:
        if source.type == "feed" and source.url:
            for fi in fetch_feed(source.url):
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
    return DimensionContent(name=dim.name, blurb=dim.blurb, summary_mode=dim.summary, items=items)


def build_manifest(
    config: Config, *, date: str | None = None, discover_og: bool = False
) -> Manifest:
    issue = Issue(date=date or _today(), title=config.publication.title)
    dimensions = [_gather_dimension(d, discover_og=discover_og) for d in config.dimensions]
    return Manifest(issue=issue, dimensions=dimensions)
