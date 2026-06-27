"""Configuration model + loader for The Weekly Intelligencer."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

VALID_SOURCE_TYPES = {"feed", "api", "search"}
VALID_SUMMARY_MODES = {"raw", "rewrite", "synthesize"}
VALID_LAYOUTS = {"grid", "by-source"}


@dataclass
class Source:
    type: str  # feed | api | search
    url: str | None = None
    query: str | None = None
    provider: str | None = None
    label: str | None = None  # by-source layout: the row heading (e.g. a lab name)


@dataclass
class Dimension:
    name: str
    blurb: str = ""
    summary: str = "rewrite"  # raw | rewrite | synthesize
    max_items: int = 5
    layout: str = "grid"  # grid | by-source
    max_per_source: int | None = None  # by-source: cap items shown per source
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
                    label=s.get("label"),
                )
            )
        layout = d.get("layout", "grid")
        raw_mps = d.get("max_per_source")
        # by-source defaults to 2 items per source unless told otherwise.
        max_per_source = (
            int(raw_mps) if raw_mps is not None else (2 if layout == "by-source" else None)
        )
        dimensions.append(
            Dimension(
                name=d.get("name", "Untitled"),
                blurb=d.get("blurb", ""),
                summary=d.get("summary", default_summary),
                max_items=int(d.get("max_items", default_max)),
                layout=layout,
                max_per_source=max_per_source,
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


def validate_config(config: Config) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Errors block the build; warnings do not."""
    errors: list[str] = []
    warnings: list[str] = []

    if not config.dimensions:
        errors.append("no dimensions defined")

    seen: set[str] = set()
    for dim in config.dimensions:
        if dim.name in seen:
            errors.append(f"duplicate dimension name: {dim.name!r}")
        seen.add(dim.name)
        if not dim.sources:
            errors.append(f"dimension {dim.name!r} has no sources")
        if dim.summary not in VALID_SUMMARY_MODES:
            errors.append(f"dimension {dim.name!r}: unknown summary {dim.summary!r}")
        if dim.layout not in VALID_LAYOUTS:
            errors.append(f"dimension {dim.name!r}: unknown layout {dim.layout!r}")
        for src in dim.sources:
            if src.type not in VALID_SOURCE_TYPES:
                errors.append(f"dimension {dim.name!r}: unknown source type {src.type!r}")
            if dim.layout == "by-source" and src.type in ("feed", "api") and not src.label:
                warnings.append(
                    f"dimension {dim.name!r}: a {src.type} source has no label; "
                    "its row will be unlabeled"
                )
            if src.type == "api":
                provider = config.providers.get(src.provider or "")
                if not provider:
                    errors.append(
                        f"dimension {dim.name!r}: api provider {src.provider!r} "
                        "not defined under providers"
                    )
                else:
                    key_env = provider.get("key_env")
                    if key_env and not os.environ.get(key_env):
                        warnings.append(
                            f"api provider {src.provider!r}: env {key_env} not set — "
                            "these sources will be skipped"
                        )
    return errors, warnings
