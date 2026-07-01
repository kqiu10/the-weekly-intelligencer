"""YouTube Data API v3 source — first-party, deterministic (SPEC §3, §10.1).

``search.list`` finds the most-viewed short videos matching a query within a window;
``videos.list`` adds real view counts. Results map to :class:`Item`s with durable
``i.ytimg.com`` thumbnails. Reads ``YOUTUBE_API_KEY`` at the call site (passed in by the
gatherer); when it is unset, :func:`fetch_youtube` is a no-op that returns ``[]`` so the
keyless pipeline still builds. ``map_results`` is pure (no network) — that is what the
tests exercise.
"""

from __future__ import annotations

import logging

import httpx

from .manifest import Item
from .net import DEFAULT_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


def _thumbnail(video_id: str) -> str:
    """A durable, public, auth-free thumbnail for a video id (survives URL expiry)."""
    return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"


def _view_counts(videos_json: dict) -> dict[str, int]:
    counts: dict[str, int] = {}
    for v in (videos_json or {}).get("items", []):
        vid = v.get("id")
        raw = (v.get("statistics") or {}).get("viewCount")
        if vid and raw is not None:
            try:
                counts[vid] = int(raw)
            except (TypeError, ValueError):
                continue
    return counts


def map_results(
    search_json: dict, videos_json: dict, *, group: str = "YouTube Shorts"
) -> list[Item]:
    """Map raw ``search.list`` + ``videos.list`` responses into Items (pure).

    Entries without a ``videoId`` or a non-blank title are dropped. The real view count
    (when available) is folded into ``raw_text`` so Claude can weigh it for the 🔥 signal.
    """
    counts = _view_counts(videos_json)
    items: list[Item] = []
    for entry in (search_json or {}).get("items", []):
        video_id = (entry.get("id") or {}).get("videoId")
        if not video_id:
            continue
        snippet = entry.get("snippet") or {}
        title = (snippet.get("title") or "").strip()
        if not title:
            continue
        published = (snippet.get("publishedAt") or "")[:10] or None
        description = (snippet.get("description") or "").strip()
        count = counts.get(video_id)
        raw_text = f"{count:,} views. {description}".strip() if count is not None else description
        items.append(
            Item(
                title=title,
                url=f"https://www.youtube.com/watch?v={video_id}",
                source="youtube.com",
                published=published,
                image=_thumbnail(video_id),
                raw_text=raw_text,
                origin="youtube",
                group=group,
            )
        )
    return items


def fetch_youtube(
    query: str,
    *,
    published_after: str,
    max_results: int,
    api_key: str | None,
    group: str = "YouTube Shorts",
    timeout: float = DEFAULT_TIMEOUT,
) -> list[Item]:
    """Most-viewed short videos for ``query`` published since ``published_after`` (RFC 3339).

    Returns ``[]`` immediately — **no HTTP** — when ``api_key`` is falsy (graceful skip),
    and also on any API/network error (fail-soft, like every other source).
    """
    if not api_key:
        logger.info("YOUTUBE_API_KEY not set; skipping youtube source for %r", query)
        return []
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
            search_resp = client.get(
                _SEARCH_URL,
                params={
                    "part": "snippet",
                    "type": "video",
                    "videoDuration": "short",
                    "order": "viewCount",
                    "publishedAfter": published_after,
                    "q": query,
                    "maxResults": max_results,
                    "relevanceLanguage": "en",
                    "key": api_key,
                },
            )
            search_resp.raise_for_status()
            search_json = search_resp.json()
            ids = [
                vid
                for e in search_json.get("items", [])
                if (vid := (e.get("id") or {}).get("videoId"))
            ]
            videos_json: dict = {}
            if ids:
                videos_resp = client.get(
                    _VIDEOS_URL,
                    params={"part": "statistics", "id": ",".join(ids), "key": api_key},
                )
                videos_resp.raise_for_status()
                videos_json = videos_resp.json()
    except httpx.HTTPError as exc:  # fail-soft: a bad key/quota/network never aborts the issue
        logger.warning("youtube api error for %r: %s", query, exc)
        return []
    return map_results(search_json, videos_json, group=group)
