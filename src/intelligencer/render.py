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
    """Human label for the span an issue covers: the Monday of its calendar week through the issue's
    own date — week-to-date, computed from the manifest alone. No wall-clock is read, so the same
    issue always renders the same range (an issue generated Thu Jul 2 reads 'Jun 29 – Jul 2, 2026').
    The end is the issue date, not the calendar Sunday: it's how far content actually runs, and it
    never advertises a day that hadn't happened when the issue was made."""
    try:
        start_iso, _ = issue_week_range(issue.date)
        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(issue.date)
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


def render_html(
    manifest: Manifest, *, render_tldr: bool = True, image_dims: dict | None = None
) -> str:
    css = (TEMPLATE_DIR / "intelligencer.css").read_text(encoding="utf-8")
    template = _env().get_template("issue.html.j2")
    return template.render(
        issue=manifest.issue,
        dimensions=manifest.dimensions,
        css=css,
        render_tldr=render_tldr,
        image_dims=image_dims or {},
    )


def _collect_image_dims(manifest: Manifest, output_dir: Path) -> dict[str, tuple[int, int]]:
    """Measure intrinsic width/height of locally cached item images (perf audit
    2026-07-06: emitting the attributes lets the browser reserve layout space — no CLS
    when a lead/grid image loads). Hotlinked URLs and missing files are skipped."""
    from PIL import Image

    dims: dict[str, tuple[int, int]] = {}
    for dim in manifest.dimensions:
        for item in dim.items:
            rel = item.image
            if not rel or not rel.startswith("assets/") or rel in dims:
                continue
            path = Path(output_dir) / rel
            if not path.exists():
                continue
            try:
                with Image.open(path) as img:
                    dims[rel] = img.size
            except Exception:  # noqa: BLE001 - an unreadable image just gets no attributes
                continue
    return dims


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


def _copy_flame(manifest: Manifest, output_dir: Path) -> None:
    """Copy the 🔥 flame glyph into dist/ when at least one card is hot — it's referenced only by
    a heating item's flame badge, so skip it when nothing is hot."""
    from .images import copy_logo

    if any(item.heat_tier for dim in manifest.dimensions for item in dim.items):
        copy_logo("assets/flame.png", output_dir)


def _prune_issue_assets(manifest: Manifest, output_dir: Path) -> None:
    """Delete files in ``assets/<date>/`` that the manifest doesn't reference (perf audit
    2026-07-06: sha1-named leftovers from re-gathered runs accumulate in the deploy
    artifact — one real issue carried 5.6 MB of orphans). Only the issue's own asset
    directory is touched."""
    issue_dir = Path(output_dir) / "assets" / manifest.issue.date
    if not issue_dir.is_dir():
        return
    referenced = {it.image for dim in manifest.dimensions for it in dim.items if it.image}
    for f in issue_dir.iterdir():
        if f.is_file() and f"assets/{manifest.issue.date}/{f.name}" not in referenced:
            f.unlink()


def render_issue(
    manifest: Manifest,
    output_dir: str | Path,
    *,
    images: str = "cache",  # cache by default — hotlink-by-omission would break self-containment
    render_tldr: bool = True,
) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if images == "cache":
        _cache_images(manifest, output_dir)
    _prune_issue_assets(manifest, output_dir)
    _copy_logos(manifest, output_dir)
    _copy_flame(manifest, output_dir)
    image_dims = _collect_image_dims(manifest, output_dir)
    out = output_dir / f"{manifest.issue.date}.html"
    out.write_text(
        render_html(manifest, render_tldr=render_tldr, image_dims=image_dims),
        encoding="utf-8",
    )
    return out
