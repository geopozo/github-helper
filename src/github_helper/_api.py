"""A CLI dashboard for github status."""

# ruff: noqa: T201
import asyncio
import re
import subprocess
import warnings
from calendar import c

import jq
import orjson

## maybe add options for output (full or reduced, python, json, or console)
## yeah so all functions return python object, so either iterate it or json it
## maybe add unfiltered option as well

current_user = ""  # global


class GHError(RuntimeError):
    """Error type for `gh` CLI tool errors."""


class ScopesError(RuntimeError):
    """Error for when missing necessary scope."""


class ScopesWarning(UserWarning):
    """Warning for when missing optional enhancing scope."""


# untested
def _check_scopes(scopes_had, scopes_needed, scopes_wanted):
    missing_scopes_needed = [
        scope for scope in scopes_needed if scope not in scopes_had
    ]
    missing_scopes_wanted = [
        scope for scope in scopes_wanted if scope not in scopes_had
    ]
    if missing_scopes_wanted:
        warnings.warn(
            "Missing scope may lead to missing information, etc. "
            f"Other scopes wanted: {missing_scopes_wanted}. Had: {scopes_had}. "
            "Try gh `auth refresh --scopes SCOPE,...`",
            category=ScopesWarning,
            stacklevel=1,
        )
    if scopes_needed:
        raise ScopesError(
            "Missing essential scopes: "
            f"Other scopes needed: {missing_scopes_needed}. Had: {scopes_had}. "
            "Try gh `auth refresh --scopes SCOPE,...`",
        )


def _check_retval(retval, err):
    if retval != 0:
        try:
            raise GHError(str(err))  # noqa: TRY301
        except GHError as e:
            # Skip one level of the traceback
            raise e.with_traceback(e.__traceback__.tb_next) from None


async def _gh_call(*commands, direct=False) -> asyncio.subprocess.Process:
    p = await asyncio.create_subprocess_exec(
        *commands,
        stdout=None if direct else subprocess.PIPE,
        stderr=None if direct else subprocess.PIPE,
        limit=102400,
    )
    retval = await p.wait()
    print(p.pid)
    stdout, stderr = await p.communicate()
    return retval, stdout, stderr


async def _gh_api(endpoint: str, *, direct=False):
    return await _gh_call("gh", "api", endpoint, direct=direct)


user_jq = jq.compile(" { (.login) : .id } ")


async def get_user(*, cli_args=None):
    """Return username."""
    _ = cli_args
    retval, out, err = await _gh_api("/user")
    _check_retval(retval, err)
    # NOTE: I think using orjson would be faster, so that's what I do
    return user_jq.input_text(out.decode()).first()


orgs_jq = jq.compile('map({ (.login): "UNKNOWN" }) | add')
role_jq = jq.compile(".role")  # the "" silences quote linter
repos_jq = jq.compile(
    "map({name: .name, visibility: .visibility, owner: .owner.login})"
)


async def get_orgs(*, cli_args=None):
    """Return orgs for a user."""
    _ = cli_args
    retval, out, err = await _gh_api("/user/orgs")
    _check_retval(retval, err)
    orgs = orgs_jq.input_value(orjson.loads(out)).first()
    for k in orgs:
        retval, out, err = await _gh_api(f"/orgs/{k}/memberships/{current_user}")
        _check_retval(retval, err)
        orgs[k] = role_jq.input_value(orjson.loads(out)).first()
    return orgs


async def get_scopes(*, cli_args=None):
    """Return array of scopes."""
    _ = cli_args
    scopes_re = re.compile(rb"\n< X-Oauth-Scopes: (.*)\n")
    retval, out, err = await _gh_call("gh", "api", "/user", "--verbose")
    _check_retval(retval, err)
    match = scopes_re.search(out)
    if not match:
        raise RuntimeError(
            "get_scopes couldn't find scopes for some reason. Output:\n{out}",
        )
    return [scope.strip() for scope in match[1].decode().split(",")]


async def get_repos(*, cli_args=None):
    """Return repos for a user."""
    _ = cli_args
    retval, out, err = await _gh_api("/user/repos")
    _check_retval(retval, err)
    repos = repos_jq.input_value(orjson.loads(out)).first()
    return repos


# this one prints directly to maintain color
async def check_auth(*, cli_args=None):
    """Return true if user is logged in."""
    retval, _, _ = await _gh_call(
        "gh",
        "auth",
        "status",
        direct=bool(cli_args),
    )
    return retval


# print out repos and status of repos
# repo (visibility) public (archived) private (archived)
# your role on the repo?

# get /user/repos # get third party by looking for own name plus orgs
# get /users/{username}/repos #
# get /orgs/{org}/repos #

# lets just start by properly organizing the objects by name/etc
# orgs # just what
# private # just what
# other { "who":
#          "what":
#          "permissions"
#       }


# do basic branch analysis
# do basic rules
