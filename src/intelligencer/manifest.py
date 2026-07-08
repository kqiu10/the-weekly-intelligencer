"""Manifest data model — the source of truth passed between pipeline stages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


@dataclass
class Item:
    title: str
    url: str
    source: str = ""
    published: str | None = None
    image: str | None = None
    raw_text: str = ""
    summary: str = ""
    origin: str = "feed"  # feed | site | search | civitai
    group: str = ""  # by-source layout: which source/lab this item belongs to
    creator: str = ""  # social-video: the post's @handle / channel name, overlaid on the tile
    # per-platform engagement counts for the social-video dimension, e.g.
    # {"views": .., "likes": .., "comments": .., "saves": .., "shares": ..} — rendered as a
    # metrics row instead of a preview image; only the keys a platform exposes are set.
    stats: dict = field(default_factory=dict)
    # SPEC §10.9 bilingual issue: {"zh": {title, summary, raw_text}, "en": {...}} — the
    # source-language entry is the original, the other its translation; empty = monolingual.
    i18n: dict = field(default_factory=dict)


@dataclass
class DimensionContent:
    name: str
    blurb: str = ""
    summary_mode: str = "rewrite"
    layout: str = "grid"  # grid | by-source
    items: list[Item] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    # by-source layout: group label -> dist-relative logo path (assets/logos/<slug>.svg)
    logos: dict[str, str] = field(default_factory=dict)
    # SPEC §10.9: {"zh": str, "en": str} pairs for the section heading and blurb
    name_i18n: dict = field(default_factory=dict)
    blurb_i18n: dict = field(default_factory=dict)


@dataclass
class Issue:
    date: str
    title: str
    subtitle: str = ""
    week: int = 1
    tldr: str = ""  # issue-level TL;DR (~100 words), written at the write stage
    tldr_i18n: dict = field(default_factory=dict)  # SPEC §10.9: {"zh": str, "en": str}
    # SPEC §10.9: masthead brand strings translate too (from config publication.*_i18n)
    title_i18n: dict = field(default_factory=dict)
    subtitle_i18n: dict = field(default_factory=dict)


@dataclass
class Manifest:
    issue: Issue
    dimensions: list[DimensionContent] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "issue": asdict(self.issue),
            "dimensions": [
                {
                    "name": d.name,
                    "blurb": d.blurb,
                    "summary_mode": d.summary_mode,
                    "layout": d.layout,
                    "items": [asdict(it) for it in d.items],
                    "notes": d.notes,
                    "logos": d.logos,
                    "name_i18n": d.name_i18n,
                    "blurb_i18n": d.blurb_i18n,
                }
                for d in self.dimensions
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        # Tolerate keys from older schema versions (e.g. the removed heat_tier/trends of
        # the 2026-07 trend feature) so previously written manifests keep loading.
        item_fields = {f.name for f in fields(Item)}
        issue = Issue(**data["issue"])
        dims: list[DimensionContent] = []
        for d in data.get("dimensions", []):
            items = [
                Item(**{k: v for k, v in it.items() if k in item_fields})
                for it in d.get("items", [])
            ]
            dims.append(
                DimensionContent(
                    name=d["name"],
                    blurb=d.get("blurb", ""),
                    summary_mode=d.get("summary_mode", "rewrite"),
                    layout=d.get("layout", "grid"),
                    items=items,
                    notes=d.get("notes", []),
                    logos=d.get("logos", {}) or {},
                    name_i18n=d.get("name_i18n", {}) or {},
                    blurb_i18n=d.get("blurb_i18n", {}) or {},
                )
            )
        return cls(issue=issue, dimensions=dims)

    def write(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    @classmethod
    def read(cls, path: str | Path) -> "Manifest":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
