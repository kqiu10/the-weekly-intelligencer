"""A1 scaffold smoke test: the CLI exposes the three subcommands."""

import pytest

from intelligencer.cli import build_parser


@pytest.mark.parametrize("command", ["fetch", "render", "validate"])
def test_subcommand_parses(command):
    args = build_parser().parse_args([command])
    assert args.command == command


def test_no_command_is_allowed_by_parser():
    # No subcommand parses cleanly; main() decides what to do with it.
    args = build_parser().parse_args([])
    assert args.command is None
