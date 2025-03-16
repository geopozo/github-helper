import argparse

import logistro


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
        "check_auth",
        description="Check that you are logged in.",
        help="Check that you are logged in. No arguments.",
    )
    _ = check_auth_parser  # add_argument, set_defaults, etc

    _ = subparsers.add_parser(
        "whoami",
        description="Get current logged-in user.",
        help="Return username of current logged in user.",
    )

    _ = subparsers.add_parser(
        "list_orgs",
        description="List orgs you're part of.",
        help="Return orgs of current logged in user.",
    )

    _ = subparsers.add_parser(
        "scopes",
        description="Get list of current scopes.",
        help="Return scopes of current logged in user.",
    )
    # could accept user

    basic_args = parser.parse_args()
    return vars(basic_args)
