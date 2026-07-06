"""Configuration model + loader for The Weekly Intelligencer."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

VALID_SOURCE_TYPES = {"feed", "search", "site", "youtube", "civitai"}
VALID_SUMMARY_MODES = {"raw", "rewrite", "synthesize"}
VALID_LAYOUTS = {"grid", "by-source"}


@dataclass
class Source:
    type: str  # feed | search | site | youtube
    url: str | None = None
    query: str | None = None
    label: str | None = None  # by-source layout: the row heading (e.g. a lab name)
    logo: str | None = None  # by-source layout: packaged logo slug (e.g. "openai")
    link_contains: str | None = None  # site: only follow links whose href holds this


@dataclass
class Dimension:
    name: str
    blurb: str = ""
    summary: str = "rewrite"  # raw | rewrite | synthesize
    max_items: int = 5
    layout: str = "grid"  # grid | by-source
    max_per_source: int | None = None  # by-source: cap items shown per source
    within_days: int | None = None  # keep only items published within N days
    trends: bool = False  # enable 🔥 trend tracking for this dimension (SPEC §10.2)
    sources: list[Source] = field(default_factory=list)


@dataclass
class Output:
    dir: str = "./dist"
    images: str = "cache"  # cache | hotlink
    open_after_render: bool = False
    render_tldr: bool = True  # show the issue TL;DR in the HTML (still written to the manifest)


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
    path: Path | None = None


# ${VAR} placeholders in source URLs, e.g. "${RSSHUB_BASE}/36kr/newsflashes" — lets a
# private instance host live in gitignored .env instead of the committed config (the repo
# is public). An unset var stays literal: validate warns, and the fetch fails soft.
_ENV_VAR_RE = re.compile(r"\$\{([A-Z][A-Z0-9_]*)\}")


def _expand_env_vars(url: str) -> str:
    return _ENV_VAR_RE.sub(lambda m: os.environ.get(m.group(1), m.group(0)), url)


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
        render_tldr=bool(out.get("render_tldr", True)),
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
                url = _resolve_file_url(_expand_env_vars(url), base_dir)
            sources.append(
                Source(
                    type=s.get("type", "feed"),
                    url=url,
                    query=s.get("query"),
                    label=s.get("label"),
                    logo=s.get("logo"),
                    link_contains=s.get("link_contains"),
                )
            )
        layout = d.get("layout", "grid")
        raw_mps = d.get("max_per_source")
        # by-source defaults to 2 items per source unless told otherwise.
        max_per_source = (
            int(raw_mps) if raw_mps is not None else (2 if layout == "by-source" else None)
        )
        raw_wd = d.get("within_days")
        within_days = int(raw_wd) if raw_wd is not None else None
        dimensions.append(
            Dimension(
                name=d.get("name", "Untitled"),
                blurb=d.get("blurb", ""),
                summary=d.get("summary", default_summary),
                max_items=int(d.get("max_items", default_max)),
                layout=layout,
                max_per_source=max_per_source,
                within_days=within_days,
                trends=bool(d.get("trends", False)),
                sources=sources,
            )
        )

    return Config(
        publication=publication,
        output=output,
        dimensions=dimensions,
        defaults=defaults,
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
            if src.type in ("feed", "site") and not src.url:
                errors.append(f"dimension {dim.name!r}: a {src.type} source has no url")
            for var in _ENV_VAR_RE.findall(src.url or ""):
                warnings.append(
                    f"dimension {dim.name!r}: source url references unset env var {var}; "
                    "the source will be skipped at fetch"
                )
            if src.type == "youtube" and not src.query:
                errors.append(f"dimension {dim.name!r}: a youtube source has no query")
            # An unlabeled by-source feed is intentional — a candidate pool Claude prunes and
            # regroups to the company each kept item is about (see gather.CANDIDATE_POOL_CAP),
            # so it is not warned about here.
    return errors, warnings
