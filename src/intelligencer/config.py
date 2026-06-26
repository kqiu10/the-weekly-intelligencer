"""Configuration model + loader for The Week Intelligencer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Source:
    type: str  # feed | api | search
    url: str | None = None
    query: str | None = None
    provider: str | None = None


@dataclass
class Dimension:
    name: str
    blurb: str = ""
    summary: str = "rewrite"  # raw | rewrite | synthesize
    max_items: int = 5
    sources: list[Source] = field(default_factory=list)


@dataclass
class Output:
    dir: str = "./dist"
    images: str = "cache"  # cache | hotlink
    open_after_render: bool = False


@dataclass
class Publication:
    title: str
    subtitle: str = ""
    first_issue_date: str | None = None
    timezone: str = "UTC"


@dataclass
class Config:
    publication: Publication
    output: Output
    dimensions: list[Dimension]
    defaults: dict = field(default_factory=dict)
    providers: dict = field(default_factory=dict)
    path: Path | None = None


def _resolve_file_url(url: str, base_dir: Path) -> str:
    """Make a relative ``file://`` URL absolute, relative to the config's directory."""
    if not url.startswith("file://"):
        return url
    raw = url[len("file://") :]
    p = Path(raw)
    if not p.is_absolute():
        p = (base_dir / raw).resolve()
    return f"file://{p}"


def load_config(path: str | Path) -> Config:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base_dir = path.parent

    pub = data.get("publication", {}) or {}
    publication = Publication(
        title=pub.get("title", "Untitled"),
        subtitle=pub.get("subtitle", ""),
        first_issue_date=pub.get("first_issue_date"),
        timezone=pub.get("timezone", "UTC"),
    )

    out = data.get("output", {}) or {}
    output = Output(
        dir=out.get("dir", "./dist"),
        images=out.get("images", "cache"),
        open_after_render=bool(out.get("open_after_render", False)),
    )

    defaults = data.get("defaults", {}) or {}
    default_summary = defaults.get("summary", "rewrite")
    default_max = int(defaults.get("max_items", 5))

    dimensions: list[Dimension] = []
    for d in data.get("dimensions", []) or []:
        sources = []
        for s in d.get("sources", []) or []:
            url = s.get("url")
            if url:
                url = _resolve_file_url(url, base_dir)
            sources.append(
                Source(
                    type=s.get("type", "feed"),
                    url=url,
                    query=s.get("query"),
                    provider=s.get("provider"),
                )
            )
        dimensions.append(
            Dimension(
                name=d.get("name", "Untitled"),
                blurb=d.get("blurb", ""),
                summary=d.get("summary", default_summary),
                max_items=int(d.get("max_items", default_max)),
                sources=sources,
            )
        )

    return Config(
        publication=publication,
        output=output,
        dimensions=dimensions,
        defaults=defaults,
        providers=data.get("providers", {}) or {},
        path=path,
    )
