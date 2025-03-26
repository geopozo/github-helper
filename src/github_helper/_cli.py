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

    # i think this doesn't do order?
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

    basic_args = parser.parse_args()
    return parser, vars(basic_args)


def run_cli():
    """Run cli command based on arguments."""
    asyncio.run(_run_cli_async())


def _print_table(table, headers, tablefmt):
    """Print data in table format."""
    if not table:
        print("No data to display.", file=sys.stderr)
        sys.exit(1)
        return
    print(tabulate(table, headers=headers, tablefmt=tablefmt))


def _print_json(data, option=None):
    """Print data in JSON format."""
    if not data:
        print("No data to display.", file=sys.stderr)
        sys.exit(1)
    print(orjson.dumps(data, option=option).decode())


def _format_data(data, cli_args=""):
    """Format data based on the option provided."""
    if cli_args["json"] and cli_args["pretty"]:
        _print_json(data, option=orjson.OPT_INDENT_2)
    elif cli_args["json"]:
        _print_json(data)
    elif cli_args["pretty"]:
        _print_table(data, headers="keys", tablefmt="pretty")
    else:
        _print_table(data, headers="", tablefmt="plain")


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
            data = [
                {
                    "user": await gh.get_user(),
                },
            ]
        case "scopes":
            data = await gh.get_scopes()
        case "repos":
            data = await gh.get_repos()
        case _:
            print("No command supplied.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

    _format_data(data, cli_args)
