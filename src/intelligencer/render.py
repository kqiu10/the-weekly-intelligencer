"""Render a manifest into a self-contained, NYT-style HTML issue."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .manifest import Manifest

TEMPLATE_DIR = Path(__file__).parent / "templates"

_NORM = re.compile(r"[^a-z0-9]+")


def _normkey(text: str) -> str:
    """Collapse text to lowercase alphanumerics for loose equality checks."""
    return _NORM.sub("", (text or "").lower())


def _blurb(item) -> str:
    """The blurb to show under a headline: the item's summary or raw lede — but
    empty when that text just echoes the headline (or 'Headline — Publisher',
    as Google News feeds give), so we never print the title twice."""
    text = (getattr(item, "summary", "") or getattr(item, "raw_text", "") or "").strip()
    if not text:
        return ""
    key = _normkey(text)
    title = getattr(item, "title", "") or ""
    source = getattr(item, "source", "") or ""
    if key in (_normkey(title), _normkey(f"{title} {source}")):
        return ""
    return text


def _groupby_order(items, attr):
    """Group items by ``attr`` preserving first-seen order (unlike Jinja's
    sorting ``groupby``). Returns ``[(key, [items]), ...]``; empty groups never
    appear, so a source that produced nothing is skipped for free."""
    groups: list[tuple[str, list]] = []
    index: dict[str, int] = {}
    for it in items:
        key = getattr(it, attr, "") or ""
        if key not in index:
            index[key] = len(groups)
            groups.append((key, []))
        groups[index[key]][1].append(it)
    return groups


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    env.filters["groupby_order"] = _groupby_order
    env.filters["blurb"] = _blurb
    return env


def render_html(manifest: Manifest) -> str:
    css = (TEMPLATE_DIR / "intelligencer.css").read_text(encoding="utf-8")
    template = _env().get_template("issue.html.j2")
    return template.render(issue=manifest.issue, dimensions=manifest.dimensions, css=css)


def _cache_images(manifest: Manifest, output_dir: Path) -> None:
    from .images import cache_image

    date = manifest.issue.date
    for dim in manifest.dimensions:
        for item in dim.items:
            if item.image and not item.image.startswith("assets/"):
                # drop a broken image rather than emit a broken <img>
                item.image = cache_image(item.image, output_dir, date)


def _copy_logos(manifest: Manifest, output_dir: Path) -> None:
    """Copy each referenced company logo into the issue's dist/ so the HTML is
    self-contained. Logos are packaged assets, needed regardless of image mode."""
    from .images import copy_logo

    for dim in manifest.dimensions:
        for rel in set(dim.logos.values()):
            copy_logo(rel, output_dir)


def render_issue(manifest: Manifest, output_dir: str | Path, *, images: str = "hotlink") -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if images == "cache":
        _cache_images(manifest, output_dir)
    _copy_logos(manifest, output_dir)
    out = output_dir / f"{manifest.issue.date}.html"
    out.write_text(render_html(manifest), encoding="utf-8")
    return out
