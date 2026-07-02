"""Render a manifest into a self-contained, NYT-style HTML issue."""

from __future__ import annotations

from datetime import date
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


def _week_range_label(issue) -> str:
    """Human label for the span an issue covers: Monday of its calendar week through the issue's
    own date — week-to-date, e.g. 'Jun 29 – Jul 2, 2026'. The end is capped at the issue date, not
    the calendar Sunday, so a mid-week issue doesn't advertise a future end date; it matches the
    week-to-date content window (``_window_start``)."""
    try:
        start_iso, end_iso = issue_week_range(issue.date)
        start = date.fromisoformat(start_iso)
        end = min(date.fromisoformat(issue.date), date.fromisoformat(end_iso))
    except (ValueError, TypeError, AttributeError):
        return ""
    return f"{start:%b} {start.day} – {end:%b} {end.day}, {end:%Y}"


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )
    env.filters["groupby_order"] = _groupby_order
    env.filters["blurb"] = item_blurb
    env.filters["week_range"] = _week_range_label
    env.filters["compact"] = _compact
    return env


def render_html(manifest: Manifest, *, render_tldr: bool = True) -> str:
    css = (TEMPLATE_DIR / "intelligencer.css").read_text(encoding="utf-8")
    template = _env().get_template("issue.html.j2")
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
