# ruff: noqa: T201
import argparse
import asyncio
import sys

import logistro
import orjson
from tabulate import tabulate

from . import _api as api


def _get_cli_args():
    # Set the arguments
    description = """gh-status helps you audit your github repos.


    See gh-status COMMAND --help for information about commands.
    """

    parser = argparse.ArgumentParser(
        add_help=True,
        parents=[logistro.parser],
        conflict_handler="resolve",
        description=description,
    )

    subparsers = parser.add_subparsers(dest="command")
    parser.add_argument(
        "-j",
        "--json",
        action="store_true",
        help="Output data in JSON format.",
    )
    parser.add_argument(
        "-p",
        "--pretty",
        action="store_true",
        help="Pretty print the output (with or without json)",
    )

    check_auth_parser = subparsers.add_parser(
        "auth-status",
        description="Check that you are logged in.",
        help="Check that you are logged in. No arguments.",
    )
    _ = check_auth_parser  # add_argument, set_defaults, etc

    _ = subparsers.add_parser(
        "user",
        description="Get current logged-in user.",
        help="Return username of current logged in user.",
    )

    _ = subparsers.add_parser(
        "orgs",
        description="List orgs you're part of.",
        help="Return orgs of current logged in user.",
    )

    _ = subparsers.add_parser(
        "scopes",
        description="Get list of current scopes.",
        help="Return scopes of current logged in user.",
    )

    _ = subparsers.add_parser(
        "repos",
        description="Show all repos.",
        help="Return all repos of current logged in user.",
    )

    tags_parser = subparsers.add_parser(
        "tags",
        description="Show all tags from a repo",
        help="Return all repos of a repo",
    )
    tags_parser.add_argument("-r", "--repo", help="Name of the repository")

    # We need complete this command in the future
    # We need an argument called --repo or maybe --name
    _ = subparsers.add_parser(
        "releases",
        description="Show all releases from a repo",
        help="Return all releases of a repo",
    )

    basic_args = parser.parse_args()
    return parser, vars(basic_args)


def run_cli():
    """Run cli command based on arguments."""
    asyncio.run(_run_cli_async())


async def _run_cli_async():
    parser, cli_args = _get_cli_args()
    gh = api.GHApi()
    match cli_args["command"]:
        case "auth-status":
            # único (por ahora)
            sys.exit(await gh.check_auth(cli_args=cli_args))
        case "orgs":
            data = await gh.get_orgs()
        case "user":
            data = await gh.get_user()
        case "scopes":
            data = await gh.get_scopes()
        case "repos":
            data = await gh.get_repos()
        case "tags":
            repo = cli_args["repo"]
            data = await gh.get_tags(repo=repo)
        case "releases":
            data = await gh.get_releases()
        case _:
            print("No command supplied.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

    if not data:
        print("No data to display.", file=sys.stderr)
        sys.exit(1)

    _print_data(
        data,
        fmt_json=cli_args["json"],
        fmt_pretty=cli_args["pretty"],
    )


def _print_data(data, *, fmt_json, fmt_pretty):
    """Format data based on the option provided."""
    if fmt_json:
        output = orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 if fmt_pretty else None,
        ).decode()
    else:
        if not isinstance(data, list):
            data = [data]
        output = tabulate(
            data,
            headers="keys" if fmt_pretty else "",
            tablefmt="pretty" if fmt_pretty else "plain",
        )
    print(output)
