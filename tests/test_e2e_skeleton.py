"""A2 walking skeleton: config → fetch (feed) → manifest → render → HTML, fully offline."""

from pathlib import Path

from intelligencer.config import load_config
from intelligencer.gather import build_manifest
from intelligencer.render import render_issue

FIXTURES = Path(__file__).parent / "fixtures"


def test_skeleton_feed_to_html(tmp_path):
    cfg = load_config(FIXTURES / "config.skeleton.yaml")

    manifest = build_manifest(cfg)
    items = manifest.dimensions[0].items
    assert items, "no items gathered from the fixture feed"
    assert items[0].title == "First Headline"
    assert items[0].url == "http://example.com/first"

    out = render_issue(manifest, tmp_path)
    assert out.exists()
    html = out.read_text(encoding="utf-8")

    # masthead + each item's headline and working link are present
    assert manifest.issue.title in html
    assert "First Headline" in html
    assert "http://example.com/first" in html
