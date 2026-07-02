"""Render a manifest into a self-contained, NYT-style HTML issue."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .gather import issue_week_range
from .manifest import Manifest
from .text import item_blurb

TEMPLATE_DIR = Path(__file__).parent / "templates"


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


def _compact(n) -> str:
    """Format an engagement count the way social apps do: 6083 → '6083', 98200 → '98.2K',
    1_300_000 → '1.3M', 1_028_127 → '1M'. Non-numeric input renders as empty."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return ""
    if n < 10_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1000:.1f}".rstrip("0").rstrip(".") + "K"
    return f"{n / 1_000_000:.1f}".rstrip("0").rstrip(".") + "M"


def _week_range_label(issue, today: date | None = None) -> str:
    """Human label for the span an issue covers: the Monday of its calendar week through
    ``min(today, that Monday + 7 days)`` — week-to-date as of *now*. A week still in progress stops
    at today (never advertises a future date); a fully-elapsed week shows its whole 7-day span. So a
    mid-week Issue 2 reads 'Jun 29 – Jul 2' today, and a past Issue 1 reads 'Jun 22 – Jun 29'."""
    try:
        start_iso, _ = issue_week_range(issue.date)
        start = date.fromisoformat(start_iso)
    except (ValueError, TypeError, AttributeError):
        return ""
    if today is None:
        today = date.today()
    end = min(today, start + timedelta(days=7))
    return f"{start:%b} {start.day} – {end:%b} {end.day}, {end:%Y}"


def _env(today: date | None = None) -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    env.filters["groupby_order"] = _groupby_order
    env.filters["blurb"] = item_blurb
    env.filters["week_range"] = lambda issue: _week_range_label(issue, today)
    env.filters["compact"] = _compact
    return env


def render_html(manifest: Manifest, *, render_tldr: bool = True, today: date | None = None) -> str:
    css = (TEMPLATE_DIR / "intelligencer.css").read_text(encoding="utf-8")
    template = _env(today).get_template("issue.html.j2")
    return template.render(
        issue=manifest.issue,
        dimensions=manifest.dimensions,
        css=css,
        render_tldr=render_tldr,
    )


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


def render_issue(
    manifest: Manifest,
    output_dir: str | Path,
    *,
    images: str = "hotlink",
    render_tldr: bool = True,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if images == "cache":
        _cache_images(manifest, output_dir)
    _copy_logos(manifest, output_dir)
    out = output_dir / f"{manifest.issue.date}.html"
    out.write_text(render_html(manifest, render_tldr=render_tldr), encoding="utf-8")
    return out
