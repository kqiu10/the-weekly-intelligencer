"""CLI crucial paths: `--only` dimension selection and the fetch merge that
guards against the destructive wholesale-replace footgun. Trivial argparse plumbing is
deliberately untested (crucial, fiddly, non-obvious logic only)."""

from types import SimpleNamespace

import pytest

from intelligencer.cli import _merge_dimensions, _select_dimensions, main


def _named(*names):
    """Lightweight stand-ins — _select_dimensions only reads `.name`."""
    return [SimpleNamespace(name=n) for n in names]


# Config declared order used by the selection tests.
FOUR = _named(
    "Frontier AI Research Labs",  # index 1
    "The Intelligent Factory",  # index 2
    "Rewriting Cross-Border Branding",  # index 3
    "Trending Social Video & Images",  # index 4
)


@pytest.mark.parametrize(
    "only, expected",
    [
        (None, [d.name for d in FOUR]),  # no filter → all
        ("2", ["The Intelligent Factory"]),  # 1-based index
        ("1,3", ["Frontier AI Research Labs", "Rewriting Cross-Border Branding"]),
        (
            "3,1",
            ["Frontier AI Research Labs", "Rewriting Cross-Border Branding"],
        ),  # config order wins
        ("1,Trending", ["Frontier AI Research Labs", "Trending Social Video & Images"]),  # mixed
        ("1,Frontier", ["Frontier AI Research Labs"]),  # overlapping tokens dedup
        (" 1 , 4 ", ["Frontier AI Research Labs", "Trending Social Video & Images"]),  # whitespace
        ("cross-border", ["Rewriting Cross-Border Branding"]),  # case-insensitive substring
        ("nonexistent", []),  # no match → empty (caller reports it)
    ],
)
def test_select_dimensions(only, expected):
    assert [d.name for d in _select_dimensions(FOUR, only)] == expected


@pytest.mark.parametrize("bad", ["0", "9"])  # indices are 1-based; out-of-range is a typo
def test_select_dimensions_bad_index_raises_naming_the_range(bad):
    with pytest.raises(ValueError) as exc:
        _select_dimensions(FOUR, bad)
    assert bad in str(exc.value) and "1" in str(exc.value) and "4" in str(exc.value)


def test_fetch_out_of_range_index_exits_1_without_fetching(capsys):
    # index 99 against the shipped config raises inside selection → clean exit 1, no network
    assert main(["fetch", "--only", "99"]) == 1
    assert "out of range" in capsys.readouterr().err


# --- fetch --only merge: partial fetch splices into the existing manifest ---


def _dc(name, marker):
    from intelligencer.manifest import DimensionContent, Item

    return DimensionContent(name=name, items=[Item(title=marker, url="http://x")])


def test_merge_rules_fresh_wins_base_survives_removed_drops_new_joins():
    """One scenario, all four rules: freshly-fetched dims replace their base version,
    untouched base dims survive, a dim removed from the config order drops, and a dim
    new to the config (absent from base) joins — all in declared config order."""
    base = [_dc("Alpha", "base-a"), _dc("Beta", "base-b"), _dc("Removed", "r")]
    fresh = [_dc("Beta", "fresh-b"), _dc("New", "fresh-n")]
    merged = _merge_dimensions(base, fresh, ["Alpha", "Beta", "New"])
    assert [(d.name, d.items[0].title) for d in merged] == [
        ("Alpha", "base-a"),
        ("Beta", "fresh-b"),
        ("New", "fresh-n"),
    ]


def test_fetch_only_merges_and_preserves_untouched_dimension_and_tldr(tmp_path, monkeypatch):
    """A partial `fetch --only` must not wipe the rest of the manifest (the footgun this
    fixes). Two search-only dimensions → fetch touches no network; refreshing one leaves
    the other's hand-authored items and the issue TL;DR intact."""
    from intelligencer import cli
    from intelligencer.manifest import DimensionContent, Issue, Item, Manifest

    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "publication: {title: T, first_issue_date: '2026-06-26'}\n"
        "output: {dir: ./dist}\n"
        "dimensions:\n"
        "  - {name: Alpha, layout: by-source, sources: [{type: search, query: a}]}\n"
        "  - {name: Beta, layout: by-source, sources: [{type: search, query: b}]}\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "manifest.json"
    monkeypatch.setattr(cli, "MANIFEST_PATH", str(manifest_path))

    # Base manifest: both dimensions carry hand-authored search items; issue has a TL;DR.
    Manifest(
        issue=Issue(date="2026-06-28", title="T", week=1, tldr="hand-written summary"),
        dimensions=[
            DimensionContent(
                name="Alpha",
                layout="by-source",
                items=[Item(title="A-old", url="http://a", origin="search", group="X")],
            ),
            DimensionContent(
                name="Beta",
                layout="by-source",
                items=[Item(title="B-keep", url="http://b", origin="search", group="Y")],
            ),
        ],
    ).write(manifest_path)

    args = SimpleNamespace(config=str(cfg), only="Alpha", date=None, dry_run=False)
    assert cli._cmd_fetch(args) == 0

    result = Manifest.read(manifest_path)
    assert [d.name for d in result.dimensions] == ["Alpha", "Beta"]  # full config order
    beta = next(d for d in result.dimensions if d.name == "Beta")
    assert [it.title for it in beta.items] == ["B-keep"]  # untouched dimension survived
    alpha = next(d for d in result.dimensions if d.name == "Alpha")
    assert alpha.items == []  # targeted dim refreshed (search-only → empty until re-filled)
    assert result.issue.tldr == "hand-written summary"  # base issue (incl. TL;DR) preserved
