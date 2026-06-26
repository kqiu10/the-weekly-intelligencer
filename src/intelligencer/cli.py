"""Command-line interface for The Week Intelligencer.

Subcommands are wired up across build tasks:
  * ``fetch``    — gather deterministic sources into a manifest (A2+)
  * ``render``   — render a manifest into a self-contained HTML issue (A2+)
  * ``validate`` — validate the configuration file (B3)
"""

from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="intelligencer",
        description="Generate a weekly NYT-style AI-industry issue.",
    )
    sub = parser.add_subparsers(dest="command", metavar="{fetch,render,validate}")

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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    # Subcommand dispatch is implemented in later tasks.
    print(f"'{args.command}' is not implemented yet.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
