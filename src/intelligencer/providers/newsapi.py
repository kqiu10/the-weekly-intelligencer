"""NewsAPI (https://newsapi.org) source with a hard daily request cap and response cache.

The cap is enforced across runs via a persistent per-day counter, so repeated
invocations in one day cannot exceed the plan limit. A response cache serves repeat
queries within a TTL so re-runs don't spend quota. Every failure mode is fail-soft:
the call returns no items plus a human-readable note, and the issue still builds.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from ..manifest import Item
from ..net import DEFAULT_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

ENDPOINT = "https://newsapi.org/v2/everything"


@dataclass
class NewsApiResult:
    items: list[Item] = field(default_factory=list)
    note: str | None = None


class NewsApiClient:
    def __init__(
        self,
        *,
        api_key: str,
        daily_limit: int = 100,
        cache_ttl_hours: float = 12,
        work_dir: str | Path = "out",
        fetch_json=None,
    ):
        self.api_key = api_key
        self.daily_limit = daily_limit
        self.cache_ttl_hours = cache_ttl_hours
        self.work_dir = Path(work_dir)
        self._fetch_json = fetch_json or self._default_fetch_json

    # -- public API -----------------------------------------------------------

    def fetch(self, query: str, *, page_size: int = 10) -> NewsApiResult:
        cached = self._cache_get(query)
        if cached is not None:
            return NewsApiResult(items=self._to_items(cached))

        if not self.api_key:
            return NewsApiResult(note="NewsAPI key not set; api source skipped")

        count = self._load_count()
        if count >= self.daily_limit:
            return NewsApiResult(
                note=f"NewsAPI daily limit ({self.daily_limit}) reached; api source skipped"
            )

        try:
            data = self._fetch_json(query, page_size)
        except Exception as exc:  # noqa: BLE001 - fail soft
            logger.warning("NewsAPI request failed for %r: %s", query, exc)
            return NewsApiResult(note=f"NewsAPI request failed: {exc}")

        self._save_count(count + 1)
        self._cache_put(query, data)
        return NewsApiResult(items=self._to_items(data))

    # -- mapping --------------------------------------------------------------

    @staticmethod
    def _to_items(data: dict) -> list[Item]:
        items: list[Item] = []
        for art in data.get("articles", []) or []:
            source = (art.get("source") or {}).get("name", "")
            items.append(
                Item(
                    title=(art.get("title") or "").strip(),
                    url=art.get("url", ""),
                    source=source,
                    published=art.get("publishedAt"),
                    image=art.get("urlToImage"),
                    raw_text=art.get("description") or "",
                    origin="api",
                )
            )
        return items

    # -- daily counter --------------------------------------------------------

    def _usage_path(self) -> Path:
        return self.work_dir / "newsapi_usage.json"

    def _load_count(self) -> int:
        path = self._usage_path()
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return 0
            if data.get("date") == _dt.date.today().isoformat():
                return int(data.get("count", 0))
        return 0

    def _save_count(self, count: int) -> None:
        path = self._usage_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"date": _dt.date.today().isoformat(), "count": count}),
            encoding="utf-8",
        )

    # -- response cache -------------------------------------------------------

    def _cache_path(self, query: str) -> Path:
        digest = hashlib.sha1(query.encode("utf-8")).hexdigest()[:16]
        return self.work_dir / "cache" / "newsapi" / f"{digest}.json"

    def _cache_get(self, query: str) -> dict | None:
        path = self._cache_path(query)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if time.time() - payload.get("_cached_at", 0) > self.cache_ttl_hours * 3600:
            return None
        return payload.get("data")

    def _cache_put(self, query: str, data: dict) -> None:
        path = self._cache_path(query)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"_cached_at": time.time(), "data": data}), encoding="utf-8")

    # -- real network call ----------------------------------------------------

    def _default_fetch_json(self, query: str, page_size: int) -> dict:
        resp = httpx.get(
            ENDPOINT,
            params={
                "q": query,
                "pageSize": page_size,
                "language": "en",
                "sortBy": "publishedAt",
            },
            headers={"X-Api-Key": self.api_key, "User-Agent": USER_AGENT},
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
