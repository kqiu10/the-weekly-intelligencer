"""B2: the rendered HTML matches the committed golden sample (deterministic)."""

from pathlib import Path

from intelligencer.manifest import Manifest
from intelligencer.render import render_html

FIXTURES = Path(__file__).parent / "fixtures"
# Paired with manifest.sample.json (its render input) — kept in fixtures/, not samples/,
# so a docs/README change to the human-facing samples/ folder can't silently delete a file
# this test depends on.
GOLDEN = FIXTURES / "golden_render.html"


def test_golden_render():
    manifest = Manifest.read(FIXTURES / "manifest.sample.json")
    html = render_html(manifest)
    assert html == GOLDEN.read_text(encoding="utf-8"), (
        "Rendered HTML drifted from tests/fixtures/golden_render.html. "
        "If the change is intended, regenerate the golden file."
    )


def test_tldr_renders_above_sections_when_present_and_omitted_when_empty():
    from intelligencer.manifest import Issue, Manifest

    text = "The week in AI: frontier labs shipped, and AI video went viral."
    shown = render_html(Manifest(issue=Issue(date="2026-07-01", title="T", tldr=text)))
    assert 'class="tldr"' in shown and text in shown
    hidden = render_html(Manifest(issue=Issue(date="2026-07-01", title="T")))
    assert 'class="tldr"' not in hidden
    # render_tldr=False suppresses it even when the manifest has one (review-it-first mode)
    off = render_html(
        Manifest(issue=Issue(date="2026-07-01", title="T", tldr=text)), render_tldr=False
    )
    assert 'class="tldr"' not in off


def test_empty_dimension_renders_no_section():
    from intelligencer.manifest import DimensionContent, Issue, Manifest

    empty = DimensionContent(name="The Intelligent Factory", blurb="A quiet week", layout="grid")
    manifest = Manifest(issue=Issue(date="2026-07-03", title="T"), dimensions=[empty])
    html = render_html(manifest)
    # a dimension with zero items (every source came back empty, e.g. an unfilled search
    # source) must not leave a title+blurb section with nothing under it
    assert "The Intelligent Factory" not in html
    assert "A quiet week" not in html
    assert 'class="dimension"' not in html


def test_week_range_label_is_week_to_date_from_the_issue_date():
    from intelligencer.manifest import Issue
    from intelligencer.render import _week_range_label

    # deterministic from the manifest alone (no wall-clock): the issue's week Monday → its own date
    assert _week_range_label(Issue(date="2026-07-02", title="T")) == "Jun 29 – Jul 2, 2026"
    assert _week_range_label(Issue(date="2026-06-26", title="T")) == "Jun 22 – Jun 26, 2026"


def test_hot_item_shows_a_flame_after_its_title_and_cold_item_does_not():
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest

    dim = DimensionContent(
        name="Social",
        layout="by-source",
        items=[
            Item(title="hot post", url="u1", group="TikTok", summary="s", heat_tier=2),
            Item(title="cold post", url="u2", group="TikTok", summary="s"),
        ],
    )
    html = render_html(Manifest(issue=Issue(date="2026-07-06", title="T"), dimensions=[dim]))
    # one flame, on the hot card right after its title — and no separate "Heating up" strip
    assert html.count('class="flame"') == 1
    assert "Heating up" not in html and 'class="trend-strip"' not in html
    assert 'hot post</a><img class="flame" src="assets/flame.png"' in html
    assert "cold post</a><img" not in html


def test_compact_filter_formats_counts_like_social_apps():
    from intelligencer.render import _compact

    assert _compact(840) == "840"
    assert _compact(6083) == "6083"
    assert _compact(12000) == "12K"
    assert _compact(98200) == "98.2K"
    assert _compact(104200) == "104.2K"
    assert _compact(1300000) == "1.3M"
    assert _compact(1028127) == "1M"


def test_social_item_renders_media_tile_with_overlaid_creator_and_metrics():
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest

    social = DimensionContent(
        name="Social",
        layout="by-source",
        items=[
            Item(
                title="AI cat pilots a jet",
                url="https://www.youtube.com/shorts/x",
                source="youtube.com",
                group="YouTube Shorts",
                image="https://i.ytimg.com/vi/x/oardefault.jpg",
                creator="AI Cinema",
                stats={"views": 1028127, "likes": 12000, "comments": 840},
            )
        ],
    )
    html = render_html(Manifest(issue=Issue(date="2026-07-02", title="T"), dimensions=[social]))
    assert "labs--media" in html
    assert 'class="media-tile"' in html and "oardefault.jpg" in html  # portrait tile
    assert 'class="media-creator">AI Cinema' in html  # creator overlaid on the frame
    # title is a linked heading in the text section (not overlaid on the tile)
    assert (
        'class="item-title"><a href="https://www.youtube.com/shorts/x">AI cat pilots a jet' in html
    )
    assert "media-cap-title" not in html
    # likes + comments overlaid on the tile; the old text metrics row is gone; views not shown
    assert 'class="media-metrics"' in html and "12K" in html and "840" in html
    assert 'href="#ic-like"' in html and 'href="#ic-comment"' in html
    assert 'class="stats"' not in html  # no separate text metrics row
    assert "1M" not in html  # views are not displayed on the tile


def test_media_dimension_imageless_item_falls_back_to_normal_card():
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest

    dim = DimensionContent(
        name="Social",
        layout="by-source",
        items=[
            Item(
                title="has image",
                url="u1",
                group="YouTube Shorts",
                image="https://i.ytimg.com/vi/x/oardefault.jpg",
                stats={"likes": 12000},
            ),
            Item(
                title="no image",
                url="u2",
                group="Instagram",
                summary="popular AI reel",
                stats={"likes": 5000},
            ),
        ],
    )
    html = render_html(Manifest(issue=Issue(date="2026-07-02", title="T"), dimensions=[dim]))
    # the imaged item is a portrait media tile; the imageless one renders as a plain by-source card
    assert html.count('class="media-tile"') == 1
    assert 'class="item-title"><a href="u2">no image' in html
    assert "popular AI reel" in html


def test_social_platform_logos_are_packaged():
    from intelligencer.images import LOGO_DIR, logo_asset_path

    for slug in ("youtube", "tiktok", "instagram", "facebook", "reddit"):
        assert logo_asset_path(slug) == f"assets/logos/{slug}.svg"
        assert (LOGO_DIR / f"{slug}.svg").read_text().lstrip().startswith("<svg")


def test_intelligent_factory_company_logos_are_packaged():
    # SPEC §10.4: unlike the labs/platforms above, these aren't pre-declared config
    # sources — Claude adds one here (and a matching assets/logos/<slug>.svg) each time a
    # new company is confirmed. Grows over time; extend this list alongside the SVGs.
    from intelligencer.images import LOGO_DIR, logo_asset_path

    # deeplearningai.svg wraps the brand's official 300px raster as a data URI —
    # SVG-only resolver, no invented vector paths
    for slug in ("hp", "unilever", "manufacturingdive", "deeplearningai"):
        assert logo_asset_path(slug) == f"assets/logos/{slug}.svg"
        assert (LOGO_DIR / f"{slug}.svg").read_text().lstrip().startswith("<svg")


def test_item_images_lazy_load_and_lead_stays_eager():
    """Perf audit 2026-07-06: thumbnails get loading=lazy decoding=async (+ intrinsic
    width/height when known); the lead image — the LCP candidate — stays eager with
    fetchpriority=high instead."""
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest
    from intelligencer.render import render_html

    m = Manifest(
        issue=Issue(date="2026-07-05", title="T", week=2),
        dimensions=[
            DimensionContent(
                name="Grid",
                layout="grid",
                items=[
                    Item(title="Lead", url="u0", image="assets/d/lead.png", summary="s"),
                    Item(title="Second", url="u1", image="assets/d/a.png", summary="s"),
                ],
            ),
            DimensionContent(
                name="Labs",
                layout="by-source",
                items=[Item(title="Row", url="u2", group="G", image="assets/d/b.png", summary="s")],
            ),
        ],
    )
    dims = {
        "assets/d/lead.png": (600, 338),
        "assets/d/a.png": (600, 400),
        "assets/d/b.png": (132, 88),
    }
    html = render_html(m, image_dims=dims)
    # lead: eager + high priority + dimensions, never lazy
    assert (
        'src="assets/d/lead.png" fetchpriority="high" decoding="async"'
        ' width="600" height="338"' in html
    )
    lead_tag = html.split('class="lead-image"')[1].split(">")[0]
    assert "lazy" not in lead_tag
    # grid + by-source thumbnails: lazy + async + dimensions
    assert 'src="assets/d/a.png" loading="lazy" decoding="async" width="600" height="400"' in html
    assert 'src="assets/d/b.png" loading="lazy" decoding="async" width="132" height="88"' in html


def test_collect_image_dims_reads_local_cached_files(tmp_path):
    from PIL import Image

    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest
    from intelligencer.render import _collect_image_dims

    (tmp_path / "assets" / "d").mkdir(parents=True)
    Image.new("RGB", (300, 200)).save(tmp_path / "assets" / "d" / "x.png")
    m = Manifest(
        issue=Issue(date="d", title="T"),
        dimensions=[
            DimensionContent(
                name="D",
                items=[
                    Item(title="a", url="u", image="assets/d/x.png"),
                    Item(title="b", url="u", image="https://hotlinked.example/y.jpg"),
                    Item(title="c", url="u", image="assets/d/missing.png"),
                ],
            )
        ],
    )
    dims = _collect_image_dims(m, tmp_path)
    assert dims == {"assets/d/x.png": (300, 200)}  # local file measured; hotlink/missing skipped


def _bilingual_manifest():
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest

    return Manifest(
        issue=Issue(
            date="2026-07-05",
            title="T",
            week=2,
            tldr="The week.",
            tldr_i18n={"zh": "本周要闻。", "en": "The week."},
        ),
        dimensions=[
            DimensionContent(
                name="Rewriting Cross-Border Branding",
                name_i18n={"zh": "重塑跨境品牌", "en": "Rewriting Cross-Border Branding"},
                blurb="How AI reshapes brands abroad",
                blurb_i18n={"zh": "AI 如何重塑品牌出海", "en": "How AI reshapes brands abroad"},
                layout="by-source",
                items=[
                    Item(
                        title="Anker lists in HK",
                        url="http://x",
                        group="Anker",
                        summary="Listed.",
                        i18n={
                            "zh": {
                                "title": "安克登陆港交所",
                                "summary": "安克完成上市。",
                                "raw_text": "",
                            },
                            "en": {
                                "title": "Anker lists in HK",
                                "summary": "Anker listed.",
                                "raw_text": "",
                            },
                        },
                    )
                ],
            )
        ],
    )


def test_bilingual_manifest_renders_paired_spans_and_toggle():
    """SPEC §10.9: every translated string ships as a zh/en span pair; a hidden checkbox +
    masthead label flips languages via pure CSS; Chinese is the default view."""
    from intelligencer.render import render_html

    html = render_html(_bilingual_manifest(), render_tldr=True)
    assert '<html lang="zh-Hans">' in html  # Chinese default
    assert '<input type="checkbox" id="lang-en"' in html
    assert 'class="lang-toggle"' in html  # the translate-icon label
    assert '<span lang="zh">安克登陆港交所</span><span lang="en">Anker lists in HK</span>' in html
    assert '<span lang="zh">重塑跨境品牌</span>' in html  # dimension name pair
    assert '<span lang="zh">本周要闻。</span>' in html  # TL;DR pair
    assert '<span lang="zh">安克完成上市。</span>' in html  # summary pair
    assert '[lang="en"] { display: none; }' in html  # zh-default css rule (inlined)


def test_monolingual_manifest_renders_plain_content():
    """A manifest without i18n renders its content as plain strings — no span pairs on
    titles/summaries/names. (Static template chrome like the masthead issue label is
    always bilingual by design.)"""
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest
    from intelligencer.render import render_html

    m = Manifest(
        issue=Issue(date="2026-07-05", title="T", week=2),
        dimensions=[
            DimensionContent(name="D", items=[Item(title="Plain", url="http://x", summary="Text.")])
        ],
    )
    html = render_html(m)
    assert '<a href="http://x">Plain</a>' in html  # no spans inside the title anchor
    assert ">Text.</p>" in html  # summary paragraph plain
    assert '<h3 class="dimension-name">D</h3>' in html  # dimension name plain


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
    assert (
        '<img class="lab-logo" src="assets/logos/openai.svg" '
        'loading="lazy" decoding="async" alt="OpenAI logo">' in html
    )
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


def test_render_issue_copies_flame_asset_only_when_an_item_is_hot(tmp_path):
    """The flame glyph is copied into dist/ exactly when a card needs its badge."""
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest
    from intelligencer.render import render_issue

    def render_into(subdir, tier):
        out = tmp_path / subdir
        dim = DimensionContent(
            name="Social",
            layout="by-source",
            items=[Item(title="p", url="u", group="TikTok", summary="s", heat_tier=tier)],
        )
        render_issue(
            Manifest(issue=Issue(date="2026-07-06", title="T"), dimensions=[dim]),
            out,
            images="hotlink",
        )
        return (out / "assets" / "flame.png").exists()

    assert render_into("hot", 2) is True
    assert render_into("cold", 0) is False
