"""B3: configuration validation."""

from intelligencer.config import load_config, validate_config


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
"""


def test_valid_config_has_no_errors(tmp_path):
    errors, _warnings = validate_config(load_config(_write(tmp_path, GOOD)))
    assert errors == []


def test_duplicate_names_fail(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: Dup, sources: [{type: feed, url: "http://x"}]}
  - {name: Dup, sources: [{type: feed, url: "http://y"}]}
"""
    errors, _ = validate_config(load_config(_write(tmp_path, text)))
    assert any("duplicate" in e for e in errors)


def test_unknown_source_type_fails(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: A, sources: [{type: bogus, url: "http://x"}]}
"""
    errors, _ = validate_config(load_config(_write(tmp_path, text)))
    assert any("unknown source type" in e for e in errors)


def test_unknown_summary_fails(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: A, summary: bogus, sources: [{type: feed, url: "http://x"}]}
"""
    errors, _ = validate_config(load_config(_write(tmp_path, text)))
    assert any("unknown summary" in e for e in errors)


def test_dimension_without_sources_fails(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: A, sources: []}
"""
    errors, _ = validate_config(load_config(_write(tmp_path, text)))
    assert any("no sources" in e for e in errors)


def test_by_source_layout_parses(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - name: Labs
    layout: by-source
    max_per_source: 2
    sources:
      - {type: feed, label: OpenAI, url: "http://x"}
"""
    cfg = load_config(_write(tmp_path, text))
    dim = cfg.dimensions[0]
    assert dim.layout == "by-source"
    assert dim.max_per_source == 2
    assert dim.sources[0].label == "OpenAI"
    errors, _ = validate_config(cfg)
    assert errors == []


def test_by_source_defaults_max_per_source_to_two(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: Labs, layout: by-source, sources: [{type: feed, label: X, url: "http://x"}]}
"""
    cfg = load_config(_write(tmp_path, text))
    assert cfg.dimensions[0].max_per_source == 2


def test_unknown_layout_fails(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: A, layout: bogus, sources: [{type: feed, url: "http://x"}]}
"""
    errors, _ = validate_config(load_config(_write(tmp_path, text)))
    assert any("unknown layout" in e for e in errors)


def test_by_source_unlabeled_source_warns(tmp_path):
    text = """
publication: {title: T}
dimensions:
  - {name: A, layout: by-source, sources: [{type: feed, url: "http://x"}]}
"""
    _errors, warnings = validate_config(load_config(_write(tmp_path, text)))
    assert any("unlabeled" in w for w in warnings)
