# ruff: noqa: T201
import argparse
import asyncio
import sys

import logistro

from github_helper._gh_adapter import GHAdapter

from . import api


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
        help="Pretty print the output (with or without json).",
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

    repos_parser = subparsers.add_parser(
        "repos",
        description="Show all repos.",
        help="Return all repos of current logged in user.",
    )
    repos_parser.add_argument(
        "-p",
        "--paginate",
        help="Get all repos",
        action="store_true",
    )

    tags_parser = subparsers.add_parser(
        "tags",
        description="Show all tags from a repo.",
        help="Return all repos of a repo.",
    )
    tags_parser.add_argument(
        "-r",
        "--repo",
        help="Name of repository required.",
        required=True,
    )

    releases_parser = subparsers.add_parser(
        "releases",
        description="Show all releases from a repo.",
        help="Return all releases of a repo.",
    )
    releases_parser.add_argument(
        "-r",
        "--repo",
        help="Name of repository required.",
        required=True,
    )

    audit_repo = subparsers.add_parser(
        "audit-repo",
        description="",
        help="Audit repo rulesets against template.",
    )
    audit_repo.add_argument(
        "-r",
        "--repo",
        help="Name of repository required.",
        required=True,
    )

    basic_args = parser.parse_args()
    return parser, vars(basic_args)


def run_cli():
    """Run cli command based on arguments."""
    asyncio.run(_run_cli_async())


async def _run_cli_async():
    parser, cli_args = _get_cli_args()
    repo = cli_args.get("repo", None)
    paginate = cli_args.get("paginate", None)
    json = cli_args.get("json", None)
    pretty = cli_args.get("pretty", None)
    gh = api.GHApi()
    adpt = GHAdapter(json, pretty)
    match cli_args["command"]:
        case "auth-status":
            # único (por ahora)
            sys.exit(await gh.check_auth(cli_args=cli_args))
        case "orgs":
            data, sadness = await gh.get_orgs()
            data = adpt.transform_orgs_data(data)
        case "user":
            data, sadness = await gh.get_user()
            data = adpt.transform_user_data(data)
        case "scopes":
            data, sadness = await gh.get_scopes()
            data = adpt.transform_scopes_data(data)
        case "repos":
            data, sadness = await gh.get_repos(paginate=paginate)
            data = adpt.transform_repos_data(data)
        case "tags":
            data, sadness = await gh.get_tagged_versions(repo)
            data = adpt.transform_tags_data(data)
        case "releases":
            data, sadness = await gh.get_releases(repo)
            data = adpt.transform_releases_data(data)
        case "audit-repo":
            data, sadness = await gh.audit_rulesets(repo)
            data = adpt.transform_audit_rulesets_data(data)
        case _:
            print("No command supplied.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

    if not data:
        print("No data to display.", file=sys.stderr)

    print(data)
    sys.exit(sadness)
