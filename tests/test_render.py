"""B2: the rendered HTML matches the committed golden sample (deterministic)."""

from pathlib import Path

from intelligencer.manifest import Manifest
from intelligencer.render import render_html

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN = Path(__file__).parent.parent / "samples" / "2026-06-26.html"


def test_golden_render():
    manifest = Manifest.read(FIXTURES / "manifest.sample.json")
    html = render_html(manifest)
    assert html == GOLDEN.read_text(encoding="utf-8"), (
        "Rendered HTML drifted from samples/2026-06-26.html. "
        "If the change is intended, regenerate the golden file."
    )
