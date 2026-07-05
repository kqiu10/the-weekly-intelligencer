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


def _named(*names):
    """Lightweight stand-ins — _select_dimensions only reads `.name`."""
    from types import SimpleNamespace

    return [SimpleNamespace(name=n) for n in names]


# Config declared order used by the index-selection tests below (SPEC §10.6).
FOUR = _named(
    "Frontier AI Research Labs",  # index 1
    "The Intelligent Factory",  # index 2
    "Rewriting Cross-Border Branding",  # index 3
    "Trending Social Video & Images",  # index 4
)


def _picked(only):
    from intelligencer.cli import _select_dimensions

    return [d.name for d in _select_dimensions(FOUR, only)]


def test_single_index_is_one_based():
    assert _picked("2") == ["The Intelligent Factory"]


def test_comma_separated_indices():
    assert _picked("1,3") == ["Frontier AI Research Labs", "Rewriting Cross-Border Branding"]


def test_selection_preserves_config_order_not_typed_order():
    # typed "3,1" but returned in declared config order (1 before 3)
    assert _picked("3,1") == ["Frontier AI Research Labs", "Rewriting Cross-Border Branding"]


def test_mix_of_index_and_substring_is_unioned():
    assert _picked("1,Trending") == [
        "Frontier AI Research Labs",
        "Trending Social Video & Images",
    ]


def test_overlapping_tokens_dedup():
    # index 1 and substring "Frontier" select the same dimension → included once
    assert _picked("1,Frontier") == ["Frontier AI Research Labs"]


def test_whitespace_around_tokens_is_ignored():
    assert _picked(" 1 , 4 ") == [
        "Frontier AI Research Labs",
        "Trending Social Video & Images",
    ]


def test_out_of_range_index_raises_with_valid_range():
    from intelligencer.cli import _select_dimensions

    with pytest.raises(ValueError) as exc:
        _select_dimensions(FOUR, "9")
    msg = str(exc.value)
    assert "9" in msg and "1" in msg and "4" in msg  # names the bad index and valid range


def test_zero_index_raises():
    from intelligencer.cli import _select_dimensions

    with pytest.raises(ValueError):
        _select_dimensions(FOUR, "0")  # indices are 1-based


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


def test_fetch_out_of_range_index_exits_1_without_fetching(capsys):
    # index 99 against the shipped config raises inside selection → clean exit 1, no network
    assert main(["fetch", "--only", "99"]) == 1
    assert "out of range" in capsys.readouterr().err
