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
