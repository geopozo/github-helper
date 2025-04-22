# ruff: noqa: T201
import argparse
import asyncio
import gc
import sys

import logistro

from github_helper._adapters import GHAdapter

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

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output data in JSON format.",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print the output (with or without json).",
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Output as HTML.",
    )
    parser.add_argument(
        "--url",
        action="store_true",
        help="Output HTML as data-url for use like `firefox $(uv run gh-helper...)`.",
    )

    subparsers = parser.add_subparsers(dest="command")

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

    configs_parser = subparsers.add_parser(
        "project-configs",
        description="Show all releases from a repo.",
        help="Return all releases of a repo.",
    )
    configs_parser.add_argument(
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

    pypi_parser = subparsers.add_parser(
        "pypi",
        description="Show all pypi packages from a repo.",
        help="Return all pypi releases of a repo.",
    )
    pypi_parser.add_argument(
        "-r",
        "--repo",
        help="Name of repository required.",
        required=True,
    )

    releases_audit_parser = subparsers.add_parser(
        "audit-releases",
        description="Show all releases from a repo with comments.",
        help="Return all releases of a repo with comments.",
    )
    releases_audit_parser.add_argument(
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
    audit_versions = subparsers.add_parser(
        "audit-versions",
        description="",
        help="Compare versions of a repository between different sources",
    )
    audit_versions.add_argument(
        "-r",
        "--repo",
        help="Name of repository required.",
        required=True,
    )

    basic_args = parser.parse_args()
    return parser, vars(basic_args)


def _gc_run(fn, *args, **kwargs):
    """Run asyncio corrutines with garbage collection."""

    async def new_fn():
        gc.collect()
        ret = await fn
        gc.collect()
        return ret

    return asyncio.run(new_fn(), *args, **kwargs)


def run_cli():
    """Run cli command based on arguments."""
    _gc_run(_run_cli_async())


async def _run_cli_async():  # noqa: C901, PLR0912, PLR0915 complex
    parser, cli_args = _get_cli_args()
    repo = cli_args.pop("repo", None)
    paginate = cli_args.pop("paginate", False)
    command = cli_args.pop("command", None)
    cli_args.pop("log")
    cli_args.pop("human")

    gh = api.GHApi()
    adpt = GHAdapter(**cli_args, command=command)

    match command:
        case "auth-status":
            data, sadness = await gh.check_auth()
        case "orgs":
            data, sadness = await gh.get_orgs()
            data = await adpt.transform_orgs_data(data)
        case "user":
            data, sadness = await gh.get_user()
            data = await adpt.transform_user_data(data)
        case "scopes":
            data, sadness = await gh.get_scopes()
            data = await adpt.transform_scopes_data(data)
        case "repos":
            data, sadness = await gh.get_repos(paginate=paginate)
            data = await adpt.transform_repos_data(data)
        case "tags":
            data, sadness = await gh.get_remote_tags(repo)
            data = await adpt.transform_tags_data(data)
        case "project-configs":
            data, sadness = await gh.get_project_configs(repo)
            data = await adpt.transform_project_configs_data(data)
        case "releases":
            data, sadness = await gh.get_releases(repo)
            data = await adpt.transform_releases_data(data)
        case "pypi":
            data, sadness = await gh.get_pypi(repo)
            data = await adpt.transform_pypi_data(data)
        case "audit-releases":
            data, sadness = await gh.audit_releases(repo)
            data = await adpt.transform_audit_releases_data(data)
        case "audit-repo":
            data, sadness = await gh.audit_rulesets(repo)
            data = await adpt.transform_audit_rulesets_data(data)
        case "audit-versions":
            data, sadness = await gh.audit_versions(repo)
            data = await adpt.transform_audit_versions_data(data)
        case _:
            print("No command supplied.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

    if not data:
        print("No data to display.", file=sys.stderr)

    print(data)
    sys.exit(sadness)
