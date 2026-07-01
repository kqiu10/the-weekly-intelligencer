"""A1 scaffold smoke test: the CLI exposes the three subcommands."""

import pytest

from intelligencer.cli import build_parser, main


@pytest.mark.parametrize("command", ["fetch", "render", "validate", "trends"])
def test_subcommand_parses(command):
    args = build_parser().parse_args([command])
    assert args.command == command


def test_no_command_is_allowed_by_parser():
    # No subcommand parses cleanly; main() decides what to do with it.
    args = build_parser().parse_args([])
    assert args.command is None


def test_only_flag_parses_for_fetch_and_render():
    assert build_parser().parse_args(["fetch", "--only", "Trending"]).only == "Trending"
    assert build_parser().parse_args(["render", "--only", "Social"]).only == "Social"
    assert build_parser().parse_args(["fetch"]).only is None  # optional


def test_select_dimensions_filters_by_name_substring():
    from intelligencer.cli import _select_dimensions
    from intelligencer.manifest import DimensionContent

    dims = [
        DimensionContent(name="Frontier AI Research Labs"),
        DimensionContent(name="Trending AI Generative Context & Social Video"),
    ]
    assert _select_dimensions(dims, None) == dims  # no filter → all
    picked = _select_dimensions(dims, "trending")  # case-insensitive substring
    assert [d.name for d in picked] == ["Trending AI Generative Context & Social Video"]
    assert _select_dimensions(dims, "nope") == []  # no match → empty


def test_main_validate_ok(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "publication: {title: T}\n"
        "dimensions:\n"
        "  - {name: A, summary: raw, sources: [{type: search, query: x}]}\n",
        encoding="utf-8",
    )
    assert main(["validate", "--config", str(cfg)]) == 0


def test_main_no_command_returns_1():
    assert main([]) == 1
