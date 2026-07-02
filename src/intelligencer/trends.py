"""Trend store: a small committed time-series of context "hotness" across issues.

``data/trends.json`` holds one entry per canonical topic, each with a history of weekly
magnitudes. Claude assigns a topic's canonical ``id`` (its semantic identity) at the write
stage; this module just persists magnitudes over time and is the substrate the 🔥 heat
signal (``heat_tier``) is computed from. Pure stdlib, human-readable, diff-able JSON.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Point:
    week: int
    issue_date: str
    magnitude: int
    samples: list[str] = field(default_factory=list)


@dataclass
class Topic:
    id: str
    descriptor: str
    tags: list[str] = field(default_factory=list)
    history: list[Point] = field(default_factory=list)


@dataclass
class TrendStore:
    topics: list[Topic] = field(default_factory=list)

    def get(self, topic_id: str) -> Topic | None:
        return next((t for t in self.topics if t.id == topic_id), None)

    def magnitudes(self, topic_id: str) -> list[int]:
        """This topic's weekly magnitudes, oldest → newest."""
        topic = self.get(topic_id)
        return [p.magnitude for p in topic.history] if topic else []

    def record(
        self,
        topic_id: str,
        descriptor: str,
        tags: list[str],
        *,
        week: int,
        issue_date: str,
        magnitude: int,
        samples: list[str] | None = None,
    ) -> Topic:
        """Record this issue's magnitude for a topic, creating the topic if new. Re-recording
        the same ``week`` (a pipeline rerun for one issue) updates that point in place rather
        than appending a duplicate."""
        topic = self.get(topic_id)
        if topic is None:
            topic = Topic(id=topic_id, descriptor=descriptor, tags=list(tags))
            self.topics.append(topic)
        else:
            # keep the latest descriptor/tags Claude assigned
            topic.descriptor = descriptor
            topic.tags = list(tags)
        point = Point(
            week=week, issue_date=issue_date, magnitude=magnitude, samples=list(samples or [])
        )
        existing = next((p for p in topic.history if p.week == week), None)
        if existing is not None:
            topic.history[topic.history.index(existing)] = point
        else:
            topic.history.append(point)
        topic.history.sort(key=lambda p: p.week)
        return topic

    def to_dict(self) -> dict:
        return {
            "topics": [
                {
                    "id": t.id,
                    "descriptor": t.descriptor,
                    "tags": t.tags,
                    "history": [
                        {
                            "week": p.week,
                            "issue_date": p.issue_date,
                            "magnitude": p.magnitude,
                            "samples": p.samples,
                        }
                        for p in t.history
                    ],
                }
                for t in self.topics
            ]
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TrendStore":
        topics = [
            Topic(
                id=t["id"],
                descriptor=t.get("descriptor", ""),
                tags=list(t.get("tags", [])),
                history=[
                    Point(
                        week=int(p["week"]),
                        issue_date=p.get("issue_date", ""),
                        magnitude=int(p.get("magnitude", 0)),
                        samples=list(p.get("samples", [])),
                    )
                    for p in t.get("history", [])
                ],
            )
            for t in data.get("topics", [])
        ]
        return cls(topics=topics)


def load_store(path: str | Path) -> TrendStore:
    """Load the store; a missing file yields an empty store (cold start)."""
    path = Path(path)
    if not path.exists():
        return TrendStore()
    return TrendStore.from_dict(json.loads(path.read_text(encoding="utf-8")))


def save_store(store: TrendStore, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def heat_tier(history: list[int]) -> int:
    """Flame tier 0–3 from a topic's weekly magnitudes (oldest→newest, incl. this week).
    "Getting hotter" = recurring AND rising: a first appearance or a flat/cooling topic is 0;
    a small rise is 1; a big jump (≥2× or +3) is 2; a sustained climb (≥3 consecutive rising
    weeks reaching magnitude ≥5) is 3."""
    if len(history) < 2:
        return 0
    cur, prev = history[-1], history[-2]
    if cur <= prev:
        return 0
    streak = 0
    for earlier, later in zip(history, history[1:]):
        streak = streak + 1 if later > earlier else 0
    if streak >= 3 and cur >= 5:
        return 3
    if cur >= 2 * prev or cur - prev >= 3:
        return 2
    return 1


def direction(history: list[int]) -> str:
    """'up' / 'down' / 'flat' for the latest week vs. the one before."""
    if len(history) < 2:
        return "flat"
    cur, prev = history[-1], history[-2]
    return "up" if cur > prev else "down" if cur < prev else "flat"


def recurring(history: list[int]) -> bool:
    """True once a topic has appeared in more than one issue."""
    return len(history) >= 2


def apply_trends(manifest, store: TrendStore, *, week: int, issue_date: str):
    """Fold this issue's Claude-curated trend topics into the store and annotate them for
    render. Each dimension carrying ``trends`` holds rows of {id, descriptor, tags, magnitude,
    samples}; for each, record the magnitude into the store then attach the computed
    ``heat_tier``/``direction``/``recurring``. Mutates ``manifest`` and ``store`` in place."""
    for dim in manifest.dimensions:
        for topic in dim.trends:
            tid = topic["id"]
            store.record(
                tid,
                topic.get("descriptor", ""),
                topic.get("tags", []),
                week=week,
                issue_date=issue_date,
                magnitude=int(topic.get("magnitude", 0)),
                samples=topic.get("samples", []),
            )
            mags = store.magnitudes(tid)
            tier = heat_tier(mags)
            topic["heat_tier"] = tier
            topic["direction"] = direction(mags)
            topic["recurring"] = recurring(mags)
            # Stamp the heat onto the posts that depict this context (its ``samples``), so each
            # card can show a flame after its title — there is no separate "Heating up" strip.
            if tier:
                samples = set(topic.get("samples", []))
                for item in dim.items:
                    if item.url in samples:
                        item.heat_tier = max(item.heat_tier, tier)
    return manifest
