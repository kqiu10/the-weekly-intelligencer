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


def test_tldr_renders_above_sections_when_present_and_omitted_when_empty():
    from intelligencer.manifest import Issue, Manifest

    text = "The week in AI: frontier labs shipped, and AI video went viral."
    shown = render_html(Manifest(issue=Issue(date="2026-07-01", title="T", tldr=text)))
    assert 'class="tldr"' in shown and text in shown
    hidden = render_html(Manifest(issue=Issue(date="2026-07-01", title="T")))
    assert 'class="tldr"' not in hidden


def test_trend_strip_shows_only_heating_rows_and_hides_when_none():
    from intelligencer.manifest import DimensionContent, Issue, Manifest

    def render(trends):
        dim = DimensionContent(name="Social", layout="by-source", trends=trends)
        return render_html(Manifest(issue=Issue(date="2026-07-06", title="T"), dimensions=[dim]))

    # heating rows render one flame glyph per tier; a zero-heat row is suppressed
    html = render(
        [
            {"descriptor": "AI cats flying jets", "heat_tier": 3},
            {"descriptor": "singing dogs", "heat_tier": 1},
            {"descriptor": "cold context", "heat_tier": 0},
        ]
    )
    assert 'class="trend-strip"' in html
    assert "AI cats flying jets" in html and "singing dogs" in html
    assert "cold context" not in html  # zero-heat rows are hidden
    assert html.count('class="flame"') == 4  # 3 + 1; none for the suppressed row

    # cold-start week — every context is heat_tier 0 → no strip and no flame symbol
    cold = render([{"descriptor": "brand new", "heat_tier": 0}])
    assert 'class="trend-strip"' not in cold and 'id="flame"' not in cold
    # a dimension with no trends also renders no strip
    assert 'class="trend-strip"' not in render([])


def test_social_platform_logos_are_packaged():
    from intelligencer.images import LOGO_DIR, logo_asset_path

    for slug in ("youtube", "tiktok", "instagram", "facebook"):
        assert logo_asset_path(slug) == f"assets/logos/{slug}.svg"
        assert (LOGO_DIR / f"{slug}.svg").read_text().lstrip().startswith("<svg")


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


def test_by_source_renders_company_logo_when_present():
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest

    manifest = Manifest(
        issue=Issue(date="2026-06-26", title="T", subtitle="", week=1),
        dimensions=[
            DimensionContent(
                name="Labs",
                layout="by-source",
                logos={"OpenAI": "assets/logos/openai.svg"},
                items=[
                    Item(
                        title="A1",
                        url="https://openai.com/a",
                        source="openai.com",
                        published="2026-06-26",
                        summary="s",
                        group="OpenAI",
                    ),
                    # A group without a logo simply renders name-only (no <img>).
                    Item(
                        title="B1",
                        url="https://x.ai/b",
                        source="x.ai",
                        published="2026-06-25",
                        summary="s",
                        group="xAI",
                    ),
                ],
            )
        ],
    )
    html = render_html(manifest)
    assert '<div class="lab-rail">' in html
    assert '<img class="lab-logo" src="assets/logos/openai.svg" alt="OpenAI logo">' in html
    # exactly one logo image — the logo-less group stays name-only
    assert html.count('class="lab-logo"') == 1
    assert ">xAI<" in html


def test_blurb_hides_title_echoes_shows_real_lede():
    from intelligencer.manifest import Item
    from intelligencer.text import item_blurb

    # raw_text is just the headline (punctuation aside) -> nothing to show
    assert (
        item_blurb(
            Item(
                title="Grok 4.5 Enters Beta - BASENOR",
                url="u",
                source="basenor.com",
                raw_text="Grok 4.5 Enters Beta BASENOR",
            )
        )
        == ""
    )
    # "Headline Publisher-name" echo -> hidden via title+source check
    assert (
        item_blurb(
            Item(title="Big News", url="u", source="Example News", raw_text="Big News Example News")
        )
        == ""
    )
    # empty when there's no text at all
    assert item_blurb(Item(title="X", url="u", raw_text="", summary="")) == ""
    # a real lede is shown, and a written summary wins over raw_text
    assert item_blurb(
        Item(
            title="Grok 4.5 Enters Beta",
            url="u",
            source="basenor.com",
            raw_text="Elon Musk posted a single word late Monday night.",
        )
    ).startswith("Elon Musk")
    assert item_blurb(Item(title="X", url="u", raw_text="raw lede", summary="written summary")) == (
        "written summary"
    )


def test_render_issue_copies_company_logos_into_dist(tmp_path):
    """render_issue makes the issue self-contained: referenced logos land in dist/."""
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest
    from intelligencer.render import render_issue

    manifest = Manifest(
        issue=Issue(date="2026-06-26", title="T", subtitle="", week=1),
        dimensions=[
            DimensionContent(
                name="Labs",
                layout="by-source",
                logos={"OpenAI": "assets/logos/openai.svg"},
                items=[
                    Item(
                        title="A1",
                        url="https://openai.com/a",
                        source="openai.com",
                        published="2026-06-26",
                        summary="s",
                        group="OpenAI",
                    ),
                ],
            )
        ],
    )
    render_issue(manifest, tmp_path, images="hotlink")
    copied = tmp_path / "assets" / "logos" / "openai.svg"
    assert copied.exists()
    assert copied.read_bytes().startswith(b"<svg")
