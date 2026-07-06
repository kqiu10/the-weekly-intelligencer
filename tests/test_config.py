"""B3: configuration validation."""

from pathlib import Path

import pytest

from intelligencer.config import load_config, validate_config

CONFIG = Path(__file__).parent.parent / "config" / "dimensions.yaml"


def test_shipped_config_has_valid_social_video_dimension():
    cfg = load_config(CONFIG)
    errors, _ = validate_config(cfg)
    assert errors == []
    social = next(
        (d for d in cfg.dimensions if d.name == "Trending Social Video & Images"),
        None,
    )
    assert social is not None, "the social-video dimension is missing from the shipped config"
    assert social.layout == "by-source"
    assert social.trends is True  # trend tracking is enabled for this dimension
    # YouTube stays first-party API; TikTok/IG/FB web search replaced by X curator feeds via
    # the private RSSHub instance (2026-07-06) — unlabeled candidate pools Claude prunes
    assert [(s.type, s.label, s.logo) for s in social.sources] == [
        ("youtube", "YouTube Shorts", "youtube"),  # free official Data API
        ("feed", None, None),
        ("feed", None, None),
    ]
    assert any("/twitter/user/RowanCheung" in (s.url or "") for s in social.sources)
    assert any("/twitter/user/icreatelife" in (s.url or "") for s in social.sources)
    assert not any(s.type == "search" for s in social.sources)


def test_shipped_config_has_valid_intelligent_factory_dimension():
    cfg = load_config(CONFIG)
    errors, _ = validate_config(cfg)
    assert errors == []
    factory = next(
        (d for d in cfg.dimensions if d.name == "The Intelligent Factory"),
        None,
    )
    assert (
        factory is not None
    ), "The Intelligent Factory dimension is missing from the shipped config"
    assert (
        factory.layout == "by-source"
    )  # one card per company found this week (groupby_order is dynamic)
    assert factory.max_per_source == 2
    assert factory.max_items == 7  # a ceiling, not a target
    assert factory.within_days == 7
    assert factory.trends is False  # SPEC §10.4: not a visual-context beat, no 🔥 signal

    # all-feed candidate pools — no search, and no Google proxies (dropped per ck's review
    # 2026-07-06, direct sources only): Manufacturing Dive's technology topic feed + The
    # Batch via the private RSSHub instance (${RSSHUB_BASE} expands from .env)
    assert [s.type for s in factory.sources] == ["feed", "feed"]
    assert any("manufacturingdive.com/feeds/topic" in (s.url or "") for s in factory.sources)
    assert any("/deeplearning/the-batch" in (s.url or "") for s in factory.sources)
    assert not any("news.google.com" in (s.url or "") for s in factory.sources)
    # candidate-pool feeds are unlabeled — Claude regroups each kept item to its company
    assert all(s.label is None for s in factory.sources)

    # SPEC §10.4: positioned after Frontier AI Research Labs; Rewriting Cross-Border Branding
    # (SPEC §10.5) now sits immediately after it, before Trending Social Video & Images.
    names = [d.name for d in cfg.dimensions]
    assert names.index("The Intelligent Factory") == names.index("Frontier AI Research Labs") + 1
    assert (
        names.index("Rewriting Cross-Border Branding") == names.index("The Intelligent Factory") + 1
    )


def test_shipped_config_has_valid_cross_border_branding_dimension():
    cfg = load_config(CONFIG)
    errors, _ = validate_config(cfg)
    assert errors == []
    brand = next(
        (d for d in cfg.dimensions if d.name == "Rewriting Cross-Border Branding"),
        None,
    )
    assert brand is not None, "Rewriting Cross-Border Branding is missing from the shipped config"
    assert (
        brand.layout == "by-source"
    )  # one card per brand found this week (groupby_order is dynamic)
    assert brand.max_per_source == 2
    assert brand.max_items == 7  # a ceiling, not a target (SPEC §10.5)
    assert brand.within_days == 7
    assert brand.trends is False  # SPEC §10.5: announcement-driven text, no 🔥 signal

    # feed/site candidate pools — no search, and no Google proxies (dropped per ck's
    # review 2026-07-06, direct sources only): 白鲸/36氪快讯/钛媒体最新 via the private
    # RSSHub instance (${RSSHUB_BASE} from .env) + 雨果跨境 scraped first-party
    assert [s.type for s in brand.sources] == ["feed", "feed", "feed", "site"]
    assert any("/baijing/article" in (s.url or "") for s in brand.sources)
    assert any("/36kr/newsflashes" in (s.url or "") for s in brand.sources)
    assert any("/tmtpost/new" in (s.url or "") for s in brand.sources)
    assert not any("news.google.com" in (s.url or "") for s in brand.sources)
    yuguo = brand.sources[-1]
    assert yuguo.type == "site" and "cifnews.com" in (yuguo.url or "")
    assert yuguo.link_contains == "/article/"  # article links share this path on the index
    assert all(s.label is None for s in brand.sources)

    # SPEC §10.5: positioned after The Intelligent Factory, before Trending Social Video & Images
    names = [d.name for d in cfg.dimensions]
    assert (
        names.index("Rewriting Cross-Border Branding") == names.index("The Intelligent Factory") + 1
    )
    assert (
        names.index("Trending Social Video & Images")
        == names.index("Rewriting Cross-Border Branding") + 1
    )


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


GOOD = """
publication: {title: T}
output: {dir: ./dist}
dimensions:
  - name: Alpha
    summary: raw
    sources: [{type: feed, url: "http://x/f.xml"}]
  - name: Beta
    summary: rewrite
    sources: [{type: search, query: "x"}]
  - name: Gamma
    layout: by-source
    sources: [{type: youtube, label: "YouTube Shorts", logo: youtube, query: "AI video"}]
"""


def test_valid_config_has_no_errors(tmp_path):
    errors, _warnings = validate_config(load_config(_write(tmp_path, GOOD)))
    assert errors == []


ENV_URL = """
publication: {title: T}
dimensions:
  - {name: A, sources: [{type: feed, url: "${RSSHUB_BASE}/36kr/newsflashes"}]}
"""


def test_env_var_in_source_url_is_expanded(tmp_path, monkeypatch):
    """${VAR} in a source URL expands from the environment at load time — so a private
    instance host (e.g. RSSHUB_BASE) lives in gitignored .env, never in the committed
    config of a public repo."""
    monkeypatch.setenv("RSSHUB_BASE", "http://rss.example:1200")
    cfg = load_config(_write(tmp_path, ENV_URL))
    assert cfg.dimensions[0].sources[0].url == "http://rss.example:1200/36kr/newsflashes"
    assert validate_config(cfg)[1] == []  # no warnings when the var resolves


def test_unset_env_var_in_source_url_warns_and_fails_soft(tmp_path, monkeypatch):
    """An unset ${VAR} stays literal (the fetch later fails soft → skipped source) and
    validate points at the missing variable by name."""
    monkeypatch.delenv("RSSHUB_BASE", raising=False)
    cfg = load_config(_write(tmp_path, ENV_URL))
    assert cfg.dimensions[0].sources[0].url == "${RSSHUB_BASE}/36kr/newsflashes"
    _errors, warnings = validate_config(cfg)
    assert any("RSSHUB_BASE" in w for w in warnings)


@pytest.mark.parametrize(
    "expected, yaml_text",
    [
        (
            "duplicate",
            """
publication: {title: T}
dimensions:
  - {name: Dup, sources: [{type: feed, url: "http://x"}]}
  - {name: Dup, sources: [{type: feed, url: "http://y"}]}
""",
        ),
        (
            "unknown source type",
            """
publication: {title: T}
dimensions:
  - {name: A, sources: [{type: bogus, url: "http://x"}]}
""",
        ),
        (
            "no query",
            """
publication: {title: T}
dimensions:
  - {name: A, sources: [{type: youtube, label: X, logo: youtube}]}
""",
        ),
        (
            "unknown summary",
            """
publication: {title: T}
dimensions:
  - {name: A, summary: bogus, sources: [{type: feed, url: "http://x"}]}
""",
        ),
        (
            "no sources",
            """
publication: {title: T}
dimensions:
  - {name: A, sources: []}
""",
        ),
        (
            "unknown layout",
            """
publication: {title: T}
dimensions:
  - {name: A, layout: bogus, sources: [{type: feed, url: "http://x"}]}
""",
        ),
    ],
)
def test_invalid_config_reports_error(tmp_path, expected, yaml_text):
    """Each malformed config surfaces its specific validation error."""
    errors, _ = validate_config(load_config(_write(tmp_path, yaml_text)))
    assert any(expected in e for e in errors)


def test_by_source_layout_parses(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - name: Labs
    layout: by-source
    max_per_source: 3
    sources:
      - {type: feed, label: OpenAI, url: "http://x"}
"""
    cfg = load_config(_write(tmp_path, text))
    dim = cfg.dimensions[0]
    assert dim.layout == "by-source"
    assert dim.max_per_source == 3  # explicit value parses
    assert dim.sources[0].label == "OpenAI"
    assert validate_config(cfg)[0] == []


def test_by_source_defaults_max_per_source_to_two(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: Labs, layout: by-source, sources: [{type: feed, label: X, url: "http://x"}]}
"""
    assert load_config(_write(tmp_path, text)).dimensions[0].max_per_source == 2


def test_by_source_unlabeled_feed_is_a_valid_candidate_pool(tmp_path):
    """An unlabeled by-source feed is an intentional candidate pool (gather brings a bounded
    batch; Claude prunes + regroups to the company each kept item is about) — it validates
    cleanly, with no 'unlabeled' warning."""
    text = """
publication: {title: T}
dimensions:
  - {name: A, layout: by-source, sources: [{type: feed, url: "http://x"}]}
"""
    errors, warnings = validate_config(load_config(_write(tmp_path, text)))
    assert errors == []
    assert not any("unlabeled" in w for w in warnings)
