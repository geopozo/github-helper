"""A CLI dashboard for github status."""

import re
import warnings
from pathlib import Path

import jq  # type: ignore [import-not-found]
import logistro
import orjson

from github_helper import _gh_service as srv
from github_helper._gh_service import GHError, ScopesError, ScopesWarning
from github_helper._utils import load_json
from github_helper.api import _audit

_logger = logistro.getLogger(__name__)
_SCRIPT_DIR = Path(__file__).resolve().parent
_TEMPLATE_PATH = _SCRIPT_DIR / "templates"


class GHApi:
    """Provides access to status functions ontop of gh program."""

    def _split_full_name(self, full_name):
        if "/" in full_name:
            return full_name.split("/")
        else:
            return self._current_user, full_name

    def __init__(self):
        """Initializize a new GHApi, takes no arguments."""
        self._current_user = ""

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
        orgs_jq = jq.compile("map({ name: (.login) })")
        endpoint = "/user/orgs"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        orgs = orgs_jq.input_value(orjson.loads(out)).first()

        _ = await self.get_user()

        role_jq = jq.compile(".role")
        for org in orgs:
            endpoint = f"orgs/{org['name']}/memberships/{self._current_user}"
            _logger.debug(f"Calling API: {endpoint}")
            retval, out, err = await srv.gh_api(endpoint)
            self._check_retval(retval, err, **org, endpoint=endpoint)
            org["role"] = role_jq.input_value(orjson.loads(out)).first()
        sadness = int(not orgs)
        return orgs, sadness

    async def get_user(self):
        """Return username."""
        if self._current_user:
            return {"user": self._current_user}

        user_jq = jq.compile("{ (.login): .id }")
        endpoint = "/user"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        user_data = user_jq.input_text(out.decode()).first()
        user_name = next(iter(user_data))
        self._current_user = user_name
        sadness = int(not user_data)
        return user_name, sadness

    async def get_scopes(self):
        """Return array of scopes."""
        scopes_re = re.compile(rb"\n< X-Oauth-Scopes: (.*)\n")
        cli_command = ["gh", "api", "/user", "--verbose"]
        _logger.debug(f"Calling CLI command: {' '.join(cli_command)}")
        retval, out, err = await srv.gh_call(*cli_command)
        self._check_retval(retval, err)
        match = scopes_re.search(out)
        if not match:
            raise GHError(
                (
                    "get_scopes couldn't find scopes for some reason. "
                    "Output:\n"
                    f"{out.decode()}"
                ),
            )
        scopes = [scope.strip() for scope in match[1].decode().split(",")]
        sadness = int(not scopes)
        return scopes, sadness

    async def get_repos(self, *, paginate):
        """Return repos for a user."""
        repos_jq = jq.compile(
            r"map({"
            r"name: .name,"
            r"visibility: .visibility,"
            r"archived: .archived,"
            r"owner: .owner.login"
            r"})"
            r" | sort_by(.name)"
            r" | sort_by(.archived)"
            r" | reverse"
            r" | sort_by(.visibility)"
            r" | reverse"
            r" | sort_by(.owner)",
        )
        endpoint = "/user/repos"
        _logger.debug(f"Calling API: {endpoint}")
        args = ["gh", "api", endpoint]
        if paginate:
            args.append("--paginate")
        retval, out, err = await srv.gh_call(*args)
        self._check_retval(retval, err, endpoint=endpoint)
        repos = repos_jq.input_value(orjson.loads(out)).first()
        sadness = int(not repos)
        return repos, sadness

    async def get_tagged_versions(self, repo):
        """Return tags for a repo."""
        _ = await self.get_user()
        tags_jq = jq.compile("map({version: .name})")
        owner, repo = self._split_full_name(full_name=repo)
        endpoint = f"repos/{owner}/{repo}/tags"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        tags = tags_jq.input_value(orjson.loads(out)).first()
        sadness = int(not tags)
        return tags, sadness

    async def get_releases(self, repo):
        """Return releases for a repo."""
        _ = await self.get_user()
        releases_jq = jq.compile(
            r"map({" r"tag: .tag_name, " r"published: (.draft | not)" r"})",
        )
        owner, repo = self._split_full_name(full_name=repo)
        endpoint = f"repos/{owner}/{repo}/releases"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        releases = releases_jq.input_value(orjson.loads(out)).first()
        sadness = int(not releases)
        return releases, sadness

    async def _get_ruleset(self, owner, repo, ruleset_id):
        """Return releset for a user by Id."""
        endpoint = f"repos/{owner}/{repo}/rulesets/{ruleset_id}"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        return orjson.loads(out)

    async def audit_rulesets(self, repo):
        """
        Verify that repos have the proper branch/tag protections or find differences.

        Args:
            repo: the name of the repo to verify. Can be "owner/repo" or just
            "repo" and owner is assumed to be the current user.

        """
        rulesets_jq = jq.compile("map({(.name): .id}) | add")
        config_path = _TEMPLATE_PATH / "audit-config.json"
        config = await load_json(config_path)
        _ = await self.get_user()
        owner, repo = self._split_full_name(repo)
        repo_full_name = f"{owner}/{repo}"
        required_ruleset_templates = _audit.get_required_rulesets(
            config,
            repo_full_name,
        )

        endpoint = f"repos/{owner}/{repo}/rulesets"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        active_rulesets = rulesets_jq.input_value(orjson.loads(out)).first()

        if not active_rulesets:
            return []

        excluded_keys = [
            "id",
            "source_type",
            "source",
            "node_id",
            "created_at",
            "updated_at",
            "_links",
            "target",
        ]
        result = [
            {"template": t, "status": "missing ruleset"}
            for t in required_ruleset_templates
            if t not in active_rulesets
        ]

        for template, ruleset_id in active_rulesets.items():
            json_file = f"{template}.json"
            if template not in required_ruleset_templates:
                result.append({"template": template, "status": "additional ruleset"})
                continue
            current_rulset = await self._get_ruleset(owner, repo, ruleset_id)
            expected_ruleset = await _audit.load_template_ruleset(json_file)
            _audit.remove_excluded_keys(current_rulset, excluded_keys)
            _audit.remove_excluded_keys(expected_ruleset, excluded_keys)

            diffs = []
            diffs = await _audit.json_diff(
                current_rulset,
                expected_ruleset,
                diffs,
            )
            for diff in diffs:
                diff["template"] = template
            result = result + diffs
        sadness = len(result)
        return result, sadness
