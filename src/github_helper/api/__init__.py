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

_logger = logistro.getLogger(__name__)
_SCRIPT_DIR = Path(__file__).resolve().parent
_TEMPLATE_PATH = _SCRIPT_DIR / "templates"


class GHApi:
    """Provides access to status functions ontop of gh program."""

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

    async def _load_target_ruleset(self, *, path):
        if Path(path).is_file():
            return await load_json(path=path)

        if Path(path).is_dir():
            raise GHError("File name required")

        template_path = _TEMPLATE_PATH / path
        return await load_json(path=template_path)

    async def _json_comparer(self, *, origin, target, excluded_keys):
        differences = []
        all_keys = set(origin.keys()).union(target.keys())

        for key in all_keys:
            if key in excluded_keys:
                continue

            origin_value = origin.get(key)
            target_value = target.get(key)

            if origin_value != target_value:
                differences.append(
                    {"name": key, "origin": origin_value, "target": target_value},
                )
        return differences if differences else {"is_equal": True}

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
        return orgs

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
        return {"user": user_name}

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
        return [{"scope_name": scope} for scope in scopes]

    async def get_repos(self):
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
            r" | reverse",
        )
        endpoint = "/user/repos"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        repos = repos_jq.input_value(orjson.loads(out)).first()
        return repos

    async def get_tags(self, *, repo):
        """Return tags for a repo."""
        _ = await self.get_user()
        tags_jq = jq.compile("map({name: .name})")
        endpoint = f"repos/{self._current_user}/{repo}/tags"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        tags = tags_jq.input_value(orjson.loads(out)).first()
        return tags

    async def get_releases(self, *, repo):
        """Return releases for a repo."""
        _ = await self.get_user()
        releases_jq = jq.compile(
            r"map({"
            r"name: .name, "
            r"tag: .tag_name, "
            r"published: (.draft | not)"
            r"})",
        )
        endpoint = f"repos/{self._current_user}/{repo}/releases"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        releases = releases_jq.input_value(orjson.loads(out)).first()
        return releases

    def _get_repo_full_name(self, *, repo):
        parts = repo.split("/")
        if len(parts) > 1:
            owner = parts[0]
            repo = parts[1]
        else:
            owner = self._current_user
        return owner, repo

    def _validate_config_keys(self, *, keys):
        allowed_keys = {"repo", "include", "exclude"}
        if keys - allowed_keys:
            raise TypeError("Only 'repo', 'include' and 'exclude' keys are allowed.")

    def _get_rulesets_files(self, *, config, repo_name):
        rulesets_files = set()
        for r in config:
            self._validate_config_keys(keys=r.keys())

            if "repo" not in r:
                continue
            if "include" in r:
                if not isinstance(r["include"], list):
                    raise TypeError("'include' must be a list")
                if r["repo"] == "*" or r["repo"] == repo_name:
                    rulesets_files = rulesets_files | set(r["include"])
            if "exclude" in r:
                if not isinstance(r["exclude"], list):
                    raise TypeError("'exclude' must be a list")
                if r["repo"] == repo_name:
                    rulesets_files = rulesets_files - set(r["exclude"])
        return rulesets_files

    async def _get_ruleset(self, *, ruleset_id, owner, repo):
        """Return releset for a user by Id."""
        endpoint = f"repos/{owner}/{repo}/rulesets/{ruleset_id}"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        return orjson.loads(out)

    async def audit_rulesets_repo(self, *, repo):
        """
        Verify that repos have the proper branch/tag protections or find differences.

        Args:
            repo: the name of the repo to verify. Can be "owner/repo" or just
            "repo" and owner is assumed to be the current user.

        """
        default_file = "audit-config.json"
        rulesets_jq = jq.compile("map({(.name): .id}) | add")
        config_file = _TEMPLATE_PATH / default_file
        config_json = await load_json(path=config_file)
        _ = await self.get_user()
        owner, repo = self._get_repo_full_name(repo=repo)
        repo_name = f"{owner}/{repo}"
        files_names = self._get_rulesets_files(config=config_json, repo_name=repo_name)

        endpoint = f"repos/{owner}/{repo}/rulesets"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        self._check_retval(retval, err, endpoint=endpoint)
        rulesets = rulesets_jq.input_value(orjson.loads(out)).first()

        if not rulesets:
            return []

        excluded_keys = [
            "id",
            "source_type",
            "source",
            "node_id",
            "created_at",
            "updated_at",
            "_links",
        ]
        result = [
            {"parent": m, "status": "missing", "differences": []}
            for m in files_names
            if m not in rulesets
        ]

        for k, v in rulesets.items():
            json_file = f"{k}.json"
            if k not in files_names:
                result.append({"parent": k, "status": "additional", "differences": []})
                continue
            json_origin = await self._get_ruleset(owner=owner, repo=repo, ruleset_id=v)
            json_target = await self._load_target_ruleset(path=json_file)
            differences = await self._json_comparer(
                origin=json_origin,
                target=json_target,
                excluded_keys=excluded_keys,
            )
            result.append({"parent": k, "status": "found", "differences": differences})
        return result
