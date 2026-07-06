"""Civitai images API source — first-party, deterministic (SPEC §10.1).

``GET /api/v1/images`` returns the week's most-reacted AI images (sort="Most Reactions",
period="Week") with real reaction counts and the hosted image URL — the portrait-tile
content the social dimension renders. Reads ``CIVITAI_API_KEY`` at the call site (passed
in by the gatherer); anonymous requests are Cloudflare-blocked, so when the key is unset
:func:`fetch_civitai` is a no-op that returns ``[]`` and the keyless pipeline still
builds. ``map_images`` is pure (no network) — that is what the tests exercise.

NSFW is filtered twice, non-negotiably: ``nsfw=None`` is requested at the API level, and
:func:`map_images` drops anything not explicitly safe-rated even if the API leaks it.
"""

from __future__ import annotations

import logging

import httpx

from .manifest import Item
from .net import DEFAULT_TIMEOUT, USER_AGENT

logger = logging.getLogger(__name__)

_IMAGES_URL = "https://civitai.com/api/v1/images"
_TITLE_MAX = 80


def _is_safe(img: dict) -> bool:
    """Only images explicitly safe on *both* flags pass — belt and suspenders."""
    if img.get("nsfw") not in (False, "None", None):
        return False
    level = img.get("nsfwLevel")
    return level in (None, "None", 1)


def _prompt_title(prompt: str) -> str:
    """The creator's own prompt doubles as the display title (never an invented headline),
    truncated to a card-friendly length on a word boundary."""
    prompt = " ".join(prompt.split())
    if len(prompt) <= _TITLE_MAX:
        return prompt
    return prompt[: _TITLE_MAX - 1].rsplit(" ", 1)[0] + "…"


def map_images(payload: dict, *, group: str = "Civitai") -> list[Item]:
    """Map a ``/api/v1/images`` response into Items (pure). Drops anything NSFW-flagged
    or without a hosted image URL (nothing to render on a portrait tile)."""
    items: list[Item] = []
    for img in (payload or {}).get("items", []):
        if not _is_safe(img):
            continue
        image_url = img.get("url")
        image_id = img.get("id")
        if not image_url or not image_id:
            continue
        stats_in = img.get("stats") or {}
        stats: dict[str, int] = {}
        for api_field, key in (("likeCount", "likes"), ("commentCount", "comments")):
            raw = stats_in.get(api_field)
            if raw is not None:
                try:
                    stats[key] = int(raw)
                except (TypeError, ValueError):
                    continue
        prompt = ((img.get("meta") or {}).get("prompt") or "").strip()
        items.append(
            Item(
                title=_prompt_title(prompt) if prompt else "Most-reacted AI image this week",
                url=f"https://civitai.com/images/{image_id}",
                source="civitai.com",
                published=(img.get("createdAt") or "")[:10] or None,
                image=image_url,
                raw_text=prompt,
                origin="civitai",
                group=group,
                creator=(img.get("username") or "").strip(),
                stats=stats,
            )
        )
    return items


def fetch_civitai(
    *,
    max_results: int,
    api_key: str | None,
    period: str = "Week",
    sort: str = "Most Reactions",
    group: str = "Civitai",
    timeout: float = DEFAULT_TIMEOUT,
) -> list[Item]:
    """The week's most-reacted safe-rated AI images.

    Returns ``[]`` immediately — **no HTTP** — when ``api_key`` is falsy (anonymous
    requests are Cloudflare-blocked anyway), and also on any API/network error
    (fail-soft, like every other source).
    """
    if not api_key:
        logger.info("CIVITAI_API_KEY not set; skipping civitai source")
        return []
    try:
        with httpx.Client(
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {api_key}"},
        ) as client:
            resp = client.get(
                _IMAGES_URL,
                params={
                    "limit": max(min(max_results, 100), 10),  # API floor is 10
                    "sort": sort,
                    "period": period,
                    "nsfw": "None",  # safe-rated only; map_images re-checks defensively
                },
            )
            resp.raise_for_status()
            payload = resp.json()
    except httpx.HTTPError as exc:  # fail-soft: a bad key/quota/network never aborts the issue
        logger.warning("civitai api error: %s", exc)
        return []
    return map_images(payload, group=group)
