"""Credential-free package entry point for development setup checks."""

import argparse
from importlib.metadata import version


def main() -> None:
    """Show package help or the installed distribution version."""
    parser = argparse.ArgumentParser(
        prog="synapse",
        description="Synapse foundation. Research runs are not implemented yet.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {version('synapse-research')}",
    )
    parser.parse_args()
    parser.print_help()
