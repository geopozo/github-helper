"""A CLI dashboard for github status."""

import re
import warnings

import jq
import logistro
import orjson

from . import _gh_service as srv

_logger = logistro.getLogger(__name__)
## maybe add options for output (full or reduced, python, json, or console)
## yeah so all functions return python object, so either iterate it or json it
## maybe add unfiltered option as well


class GHError(RuntimeError):
    """Error type for `gh` CLI tool errors."""


class ScopesError(RuntimeError):
    """Error for when missing necessary scope."""


class ScopesWarning(UserWarning):
    """Warning for when missing optional enhancing scope."""


# lets just start by properly organizing the objects by name/etc
# orgs # just what
# private # just what
# other { "who":
#          "what":
#          "permissions"
#       }


class GHApi:
    def __init__(self):
        self.current_user = ""

    # untested
    def _check_scopes(self, scopes_had, scopes_needed, scopes_wanted):
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

    async def check_auth(self, *, cli_args=None):
        """Return true if user is logged in."""
        retval, _, _ = await srv.gh_call(
            "gh",
            "auth",
            "status",
            direct=bool(cli_args),
        )
        return retval

    def _check_retval(self, retval, err, **kwargs):
        if retval != 0:
            try:
                raise GHError(f"{err!s}, add'l: {kwargs.items()!s}")  # noqa: TRY301
            except GHError as e:
                raise e.with_traceback(e.__traceback__.tb_next) from None

    async def get_orgs(self):
        """Return orgs for a user."""
        retval, out, err = await srv.gh_api("/user/orgs")
        self._check_retval(retval, err)
        orgs_jq = jq.compile("map({ name: (.login) })")
        orgs = orgs_jq.input_value(orjson.loads(out)).first()
        role_jq = jq.compile(".role")
        await self._initialize()
        for k in orgs:
            endpoint = f"/orgs/{k["name"]}/memberships/{self.current_user}"
            retval, out, err = await srv.gh_api(endpoint)
            self._check_retval(retval, err)
            k["role"] = role_jq.input_value(orjson.loads(out)).first()
        return orgs

    async def get_user(self):
        """Return username."""
        retval, out, err = await srv.gh_api("/user")
        self._check_retval(retval, err)
        user_jq = jq.compile(" { (.login) : .id } ")
        return user_jq.input_text(out.decode()).first()

    async def get_scopes(self):
        """Return array of scopes."""
        scopes_re = re.compile(rb"\n< X-Oauth-Scopes: (.*)\n")
        retval, out, err = await srv.gh_call("gh", "api", "/user", "--verbose")
        self._check_retval(retval, err)
        match = scopes_re.search(out)
        if not match:
            raise RuntimeError(
                "get_scopes couldn't find scopes for some reason. Output:\n{out}",
            )
        return [scope.strip() for scope in match[1].decode().split(",")]

    async def get_repos(self):
        """Return repos for a user."""
        retval, out, err = await srv.gh_api("/user/repos")
        self._check_retval(retval, err)
        repos_jq = jq.compile(
            "map({name: .name, visibility: .visibility, owner: .owner.login})"
        )
        repos = repos_jq.input_value(orjson.loads(out)).first()
        return repos

    async def _initialize(self):
        if self.current_user:
            return
        user_name = next(iter(await self.get_user()))
        self.current_user = user_name
