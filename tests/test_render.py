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


def test_by_source_renders_labeled_rows_with_source_and_date():
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest

    manifest = Manifest(
        issue=Issue(date="2026-06-26", title="T", subtitle="", week=1),
        dimensions=[
            DimensionContent(
                name="Labs",
                layout="by-source",
                items=[
                    Item(
                        title="A1",
                        url="https://openai.com/a",
                        source="openai.com",
                        published="2026-06-26",
                        summary="s",
                        group="OpenAI",
                    ),
                    Item(
                        title="A2",
                        url="https://openai.com/b",
                        source="openai.com",
                        published="2026-06-25",
                        summary="s",
                        group="OpenAI",
                    ),
                    Item(
                        title="B1",
                        url="https://deepmind.google/c",
                        source="deepmind.google",
                        published="2026-06-24",
                        summary="s",
                        group="Google DeepMind",
                    ),
                ],
            )
        ],
    )
    html = render_html(manifest)
    # one labeled row per lab (no empty rows), in source order
    assert html.count('class="lab"') == 2
    assert ">OpenAI<" in html
    assert ">Google DeepMind<" in html
    # clean publisher + date, not a long pasted URL
    assert ">openai.com<" in html
    assert "2026-06-26" in html
    assert html.index(">OpenAI<") < html.index(">Google DeepMind<")
    # a by-source first dimension suppresses the hero, so the masthead sits
    # directly above the first section (what the top-rule CSS rule keys off)
    assert '<article class="lead">' not in html
