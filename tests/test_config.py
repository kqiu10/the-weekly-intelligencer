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
        (d for d in cfg.dimensions if d.name == "Trending AI Generative Context & Social Video"),
        None,
    )
    assert social is not None, "the social-video dimension is missing from the shipped config"
    assert social.layout == "by-source"
    assert social.trends is True  # trend tracking is enabled for this dimension
    assert [(s.type, s.label, s.logo) for s in social.sources] == [
        ("youtube", "YouTube Shorts", "youtube"),  # first-party Data API metrics (SPEC §10.1)
        ("search", "TikTok", "tiktok"),  # metrics only when a post's counts are readable
    ]


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


def test_by_source_unlabeled_source_warns(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: A, layout: by-source, sources: [{type: feed, url: "http://x"}]}
"""
    _errors, warnings = validate_config(load_config(_write(tmp_path, text)))
    assert any("unlabeled" in w for w in warnings)
