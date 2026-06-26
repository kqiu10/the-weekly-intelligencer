"""Render a manifest into a self-contained, NYT-style HTML issue."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .manifest import Manifest

TEMPLATE_DIR = Path(__file__).parent / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml", "j2"]),
    )


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


def render_issue(manifest: Manifest, output_dir: str | Path, *, images: str = "hotlink") -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    if images == "cache":
        _cache_images(manifest, output_dir)
    out = output_dir / f"{manifest.issue.date}.html"
    out.write_text(render_html(manifest), encoding="utf-8")
    return out
