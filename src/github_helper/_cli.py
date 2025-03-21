import argparse
import asyncio
import sys

# ruff: noqa: T201
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

    # i think this doesn't do order?
    check_auth_parser = subparsers.add_parser(
        "auth-status",
        description="Check that you are logged in.",
        help="Check that you are logged in. No arguments.",
    )
    _ = check_auth_parser  # add_argument, set_defaults, etc

    user_parser = subparsers.add_parser(
        "user",
        description="Get current logged-in user.",
        help="Return username of current logged in user.",
    )
    user_parser.add_argument("-j", "--json", action="store_true")
    user_parser.add_argument("-p", "--pretty", action="store_true")

    orgs_parser = subparsers.add_parser(
        "orgs",
        description="List orgs you're part of.",
        help="Return orgs of current logged in user.",
    )
    orgs_parser.add_argument("-j", "--json", action="store_true")
    orgs_parser.add_argument("-p", "--pretty", action="store_true")

    scopes_parser = subparsers.add_parser(
        "scopes",
        description="Get list of current scopes.",
        help="Return scopes of current logged in user.",
    )
    scopes_parser.add_argument("-j", "--json", action="store_true")
    scopes_parser.add_argument("-p", "--pretty", action="store_true")

    repos_parser = subparsers.add_parser(
        "repos",
        description="Show all repos.",
        help="Return all repos of current logged in user.",
    )
    repos_parser.add_argument("-j", "--json", action="store_true")
    repos_parser.add_argument("-p", "--pretty", action="store_true")

    # could accept user

    basic_args = parser.parse_args()
    return vars(basic_args)


def run_cli():
    """Run cli command based on arguments."""
    asyncio.run(_run_cli_async())


def _get_table(table, headers, tablefmt):
    print(tabulate(table, headers=headers, tablefmt=tablefmt))


def check_flags(cli_args, info=None):
    """Check if any flags are set."""
    if cli_args["json"] and cli_args["pretty"]:
        raise ValueError("Cannot use both --json and --pretty.")

    if cli_args["json"]:
        print(orjson.dumps(info, option=orjson.OPT_INDENT_2).decode())
        return

    if cli_args["pretty"]:
        _get_table(info, headers="keys", tablefmt="pretty")
        return

    _get_table(info, headers="", tablefmt="plain")


async def _run_cli_async():
    cli_args = _get_cli_args()
    gh = api.GHApi()
    match cli_args["command"]:
        case "auth-status":
            # prints directly, not sure if I like it
            sys.exit(await gh.check_auth(cli_args=cli_args))
        case "orgs":
            check_flags(
                cli_args,
                info=await gh.get_orgs(),
            )
        case "user":
            check_flags(
                cli_args,
                info=[{"user": next(iter(await gh.get_user()))}],
            )
        case "scopes":
            check_flags(
                cli_args,
                info=[{"scope_name": scope} for scope in await gh.get_scopes()],
            )
        case "repos":
            check_flags(
                cli_args,
                info=await gh.get_repos(),
            )
        case _:
            print("No command supplied. See --help.")
