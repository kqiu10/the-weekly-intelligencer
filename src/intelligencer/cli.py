"""Command-line interface for The Weekly Intelligencer.

Subcommands:
  * ``fetch``    — gather deterministic sources into ``out/manifest.json``
  * ``render``   — render the manifest into a self-contained HTML issue
  * ``validate`` — validate the configuration file
"""

from __future__ import annotations

import argparse
import sys

MANIFEST_PATH = "out/manifest.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelligencer",
        description="Generate a weekly NYT-style AI-industry issue.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{fetch,render,validate}")

    p_fetch = sub.add_parser("fetch", help="Gather deterministic sources into a manifest")
    p_fetch.add_argument("--config", default="config/dimensions.yaml", help="config file path")
    p_fetch.add_argument("--dry-run", action="store_true", help="fetch without writing caches")
    p_fetch.add_argument(
        "--only",
        help="only gather these dimensions: comma-separated 1-based indices and/or name "
        "substrings (e.g. '1,3' or 'Cross-Border'); merges into any existing manifest",
    )
    p_fetch.add_argument(
        "--date", help="issue date YYYY-MM-DD to pin the week window (default: today)"
    )

    p_render = sub.add_parser("render", help="Render a manifest into a self-contained HTML issue")
    p_render.add_argument("--config", default="config/dimensions.yaml", help="config file path")
    p_render.add_argument(
        "--open", action="store_true", dest="open_after", help="open the issue when done"
    )
    p_render.add_argument(
        "--only",
        help="only render these dimensions: comma-separated 1-based indices and/or "
        "name substrings (e.g. '1,3' or 'Cross-Border')",
    )

    p_validate = sub.add_parser("validate", help="Validate the configuration file")
    p_validate.add_argument("--config", default="config/dimensions.yaml", help="config file path")

    return parser


def _select_dimensions(dimensions: list, only: str | None) -> list:
    """Select a subset of dimensions for a partial fetch/render run.

    ``only`` is a comma-separated list of tokens; each token is either a **1-based index**
    into the config's declared dimension order, or a **case-insensitive name substring**.
    Matches are unioned and returned in **declared config order** (not the order typed).
    Empty/None selects everything. An out-of-range numeric index raises ``ValueError`` —
    it signals a typo, distinct from a substring that simply matches nothing (→ empty list,
    which the caller reports as "no dimensions match")."""
    if not only:
        return dimensions
    selected: set[int] = set()
    for token in (t.strip() for t in only.split(",")):
        if not token:
            continue
        if token.isdigit():
            idx = int(token)
            if not 1 <= idx <= len(dimensions):
                raise ValueError(f"dimension index {idx} out of range (1..{len(dimensions)})")
            selected.add(idx - 1)
        else:
            needle = token.lower()
            selected.update(i for i, d in enumerate(dimensions) if needle in d.name.lower())
    return [d for i, d in enumerate(dimensions) if i in selected]


def _merge_dimensions(base_dims: list, fresh_dims: list, order_names: list[str]) -> list:
    """Splice freshly-fetched dimensions into the ones already in the manifest.

    Walks ``order_names`` (the config's full declared order) and, for each, prefers the
    freshly-fetched version, falling back to the existing manifest's version — so a partial
    ``fetch --only`` refreshes just the selected dimensions and leaves every untouched one's
    data (including Claude-authored search items/summaries) exactly as it was. A base
    dimension no longer present in the config order is dropped (config is the authority)."""
    fresh_by_name = {d.name: d for d in fresh_dims}
    base_by_name = {d.name: d for d in base_dims}
    merged = []
    for name in order_names:
        if name in fresh_by_name:
            merged.append(fresh_by_name[name])
        elif name in base_by_name:
            merged.append(base_by_name[name])
    return merged


def _cmd_fetch(args: argparse.Namespace) -> int:
    import datetime as dt
    from pathlib import Path

    from .config import load_config
    from .gather import build_manifest
    from .manifest import Manifest

    if args.date:
        try:
            dt.date.fromisoformat(args.date)
        except ValueError:
            print(f"invalid --date {args.date!r}; expected YYYY-MM-DD", file=sys.stderr)
            return 1
    cfg = load_config(args.config)
    full_order = [d.name for d in cfg.dimensions]  # declared order, captured before filtering
    try:
        cfg.dimensions = _select_dimensions(cfg.dimensions, args.only)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not cfg.dimensions:
        print(f"no dimensions match --only {args.only!r}", file=sys.stderr)
        return 1
    manifest = build_manifest(cfg, date=args.date, discover_og=True)
    # A partial fetch (--only) merges into any existing manifest rather than replacing it
    # wholesale — otherwise refreshing one dimension would wipe the others' authored content.
    if args.only and Path(MANIFEST_PATH).exists():
        base = Manifest.read(MANIFEST_PATH)
        manifest.dimensions = _merge_dimensions(base.dimensions, manifest.dimensions, full_order)
        manifest.issue = base.issue  # keep the established issue (incl. hand-written TL;DR)
    path = manifest.write(MANIFEST_PATH)
    n = sum(len(d.items) for d in manifest.dimensions)
    missing = sum(1 for d in manifest.dimensions for it in d.items if not it.image)
    summary = f"{n} items across {len(manifest.dimensions)} dimensions"
    if missing:
        summary += f", {missing} without a preview image"
    print(f"wrote {path} ({summary})")
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    from .config import load_config
    from .manifest import Manifest
    from .render import render_issue

    cfg = load_config(args.config)
    manifest = Manifest.read(MANIFEST_PATH)
    try:
        manifest.dimensions = _select_dimensions(manifest.dimensions, args.only)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if not manifest.dimensions:
        print(f"no dimensions match --only {args.only!r}", file=sys.stderr)
        return 1
    out = render_issue(
        manifest, cfg.output.dir, images=cfg.output.images, render_tldr=cfg.output.render_tldr
    )
    print(f"wrote {out}")
    if getattr(args, "open_after", False):
        import webbrowser

        webbrowser.open(out.resolve().as_uri())
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    from .config import load_config, validate_config

    cfg = load_config(args.config)
    errors, warnings = validate_config(cfg)
    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if errors:
        return 1
    print(f"config OK: {len(cfg.dimensions)} dimensions ({len(warnings)} warnings)")
    return 0


def main(argv: list[str] | None = None) -> int:
    from dotenv import load_dotenv

    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    if args.command == "fetch":
        return _cmd_fetch(args)
    if args.command == "render":
        return _cmd_render(args)
    if args.command == "validate":
        return _cmd_validate(args)
    print(f"'{args.command}' is not implemented yet.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
