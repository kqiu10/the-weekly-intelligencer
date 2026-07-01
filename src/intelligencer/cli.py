"""Command-line interface for The Weekly Intelligencer.

Subcommands:
  * ``fetch``    — gather deterministic sources into ``out/manifest.json``
  * ``render``   — render the manifest into a self-contained HTML issue
  * ``validate`` — validate the configuration file (implemented in B3)
"""

from __future__ import annotations

import argparse
import sys

MANIFEST_PATH = "out/manifest.json"
TRENDS_PATH = "data/trends.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelligencer",
        description="Generate a weekly NYT-style AI-industry issue.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{fetch,render,validate,trends}")

    p_fetch = sub.add_parser("fetch", help="Gather deterministic sources into a manifest")
    p_fetch.add_argument("--config", default="config/dimensions.yaml", help="config file path")
    p_fetch.add_argument("--dry-run", action="store_true", help="fetch without writing caches")

    p_render = sub.add_parser("render", help="Render a manifest into a self-contained HTML issue")
    p_render.add_argument("--config", default="config/dimensions.yaml", help="config file path")
    p_render.add_argument(
        "--open", action="store_true", dest="open_after", help="open the issue when done"
    )

    p_validate = sub.add_parser("validate", help="Validate the configuration file")
    p_validate.add_argument("--config", default="config/dimensions.yaml", help="config file path")

    sub.add_parser("trends", help="Fold curated trend topics into the store and annotate 🔥 heat")

    return parser


def _cmd_fetch(args: argparse.Namespace) -> int:
    from .config import load_config
    from .gather import build_manifest

    cfg = load_config(args.config)
    manifest = build_manifest(cfg, discover_og=True)
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
    out = render_issue(manifest, cfg.output.dir, images=cfg.output.images)
    print(f"wrote {out}")
    if getattr(args, "open_after", False):
        import webbrowser

        webbrowser.open(out.resolve().as_uri())
    return 0


def _cmd_trends(args: argparse.Namespace) -> int:
    from .manifest import Manifest
    from .trends import apply_trends, load_store, save_store

    manifest = Manifest.read(MANIFEST_PATH)
    store = load_store(TRENDS_PATH)
    apply_trends(manifest, store, week=manifest.issue.week, issue_date=manifest.issue.date)
    save_store(store, TRENDS_PATH)
    manifest.write(MANIFEST_PATH)
    n = sum(len(d.trends) for d in manifest.dimensions)
    print(f"updated {n} trend topics -> {TRENDS_PATH}")
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
    if args.command == "trends":
        return _cmd_trends(args)
    print(f"'{args.command}' is not implemented yet.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
