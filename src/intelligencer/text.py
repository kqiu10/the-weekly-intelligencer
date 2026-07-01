"""Shared text helpers for selecting and normalizing item blurbs."""

from __future__ import annotations

import re

_NORM = re.compile(r"[^a-z0-9]+")


def normkey(text: str) -> str:
    """Collapse text to lowercase alphanumerics for loose equality checks."""
    return _NORM.sub("", (text or "").lower())


def item_blurb(item) -> str:
    """The blurb to show under a headline: the item's summary or raw lede — but
    "" when that text merely echoes the headline (or "Headline — Publisher", as
    Google News feeds give), so we never print the title twice."""
    text = (getattr(item, "summary", "") or getattr(item, "raw_text", "") or "").strip()
    if not text:
        return ""
    key = normkey(text)
    title = getattr(item, "title", "") or ""
    source = getattr(item, "source", "") or ""
    if key in (normkey(title), normkey(f"{title} {source}")):
        return ""
    return text
