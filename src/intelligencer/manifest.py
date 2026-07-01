"""Manifest data model — the source of truth passed between pipeline stages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
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
    origin: str = "feed"  # feed | api | search
    group: str = ""  # by-source layout: which source/lab this item belongs to


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
    # trend rows for the 🔥 "Heating up" strip: {descriptor, tags, magnitude, heat_tier,
    # direction, recurring, samples} — populated by the trends step (SPEC §10.2)
    trends: list[dict] = field(default_factory=list)


@dataclass
class Issue:
    date: str
    title: str
    subtitle: str = ""
    week: int = 1
    tldr: str = ""  # issue-level TL;DR (~100 words), written at the write stage


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
                    "trends": d.trends,
                }
                for d in self.dimensions
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Manifest":
        issue = Issue(**data["issue"])
        dims: list[DimensionContent] = []
        for d in data.get("dimensions", []):
            items = [Item(**it) for it in d.get("items", [])]
            dims.append(
                DimensionContent(
                    name=d["name"],
                    blurb=d.get("blurb", ""),
                    summary_mode=d.get("summary_mode", "rewrite"),
                    layout=d.get("layout", "grid"),
                    items=items,
                    notes=d.get("notes", []),
                    logos=d.get("logos", {}) or {},
                    trends=d.get("trends", []) or [],
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
