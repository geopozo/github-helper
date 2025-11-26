"""A CLI dashboard for github status."""

import asyncio
import itertools
import re
import sys
import tomllib
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypedDict, TypeVar

import aiohttp
import jq  # type: ignore [import-not-found]
import logistro
import orjson
from colored import Fore, Style

from github_helper._services import gh as srv
from github_helper._services import repos as repo_srv
from github_helper._services import ssh_srv
from github_helper._services.gh import GHError, ScopesError, ScopesWarning
from github_helper._utils import load_json
from github_helper.api import _audit, versions

from ._pkg_audit import ReleaseAudit

_logger = logistro.getLogger(__name__)
_SCRIPT_DIR = Path(__file__).resolve().parent
_TEMPLATE_PATH = _SCRIPT_DIR / "templates"

# could just put this in CLI and be done with it
# could also force
if not sys.stdout.isatty():

    class _NoColor:
        def __getattr__(self, name):
            return ""

    # Override colored's foreground, background, and style
    Fore = Style = _NoColor()  # type: ignore[misc, assignment]


async def _noop(tup=0, ret=None):
    ### Allows us to fake async noops
    if not tup:
        return ret
    else:
        return (ret,) * tup


_check_ran = False


def _check_ssh_once():
    _logger = logistro.getLogger(__name__)
    global _check_ran  # noqa: PLW0603 global
    if not _check_ran:
        _logger.debug("SSH has not been checked yet.")
        ssh_srv.check_ssh_ready()
        _check_ran = True
    else:
        _logger.debug("SSH is already ran.")


_check_ssh_once()


def _log_one_json(obj):
    obj = obj[0] if isinstance(obj, list) else obj
    if _logger.getEffectiveLevel() <= logistro.DEBUG2:
        raw = orjson.dumps(
            obj,
            option=orjson.OPT_INDENT_2,
        ).decode()
        _logger.debug2(f"gh result:\n {raw!s}")


_T = TypeVar("_T")
RetVal = tuple[_T, int]
"""Return type for api's that can exit the program."""


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

    async def check_auth(self):
        """Return true if user is logged in."""
        retval, out, err = await srv.gh_call(
            "gh",
            "auth",
            "status",
        )
        srv.check_retval(retval, err, command="gh auth status")
        return out.decode(), retval

    async def get_orgs(self):
        """Return orgs for a user."""
        orgs_jq = jq.compile("map({ name: (.login) })")
        endpoint = "/user/orgs"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        srv.check_retval(retval, err, endpoint=endpoint)
        orgs = orgs_jq.input_value(orjson.loads(out)).first()

        _ = await self.get_user()  # will refresh self._current_user

        role_jq = jq.compile(".role")
        for org in orgs:
            endpoint = f"orgs/{org['name']}/memberships/{self._current_user}"
            _logger.debug(f"Calling API: {endpoint}")
            retval, out, err = await srv.gh_api(endpoint)
            srv.check_retval(retval, err, **org, endpoint=endpoint)
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
        srv.check_retval(retval, err, endpoint=endpoint)
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
        srv.check_retval(retval, err)
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

    async def _get_collaborators(self, owner, repo):
        """Return collaborators for a repo."""
        permissions_enum = {
            "admin": 4,
            "maintain": 3,
            "push": 2,
            "triage": 1,
            "pull": 0,
        }
        jq_expr = (
            'map(select(.login != "{owner}") | '
            "{ user: .login, permission: (["
            + ", ".join(
                f"(if .permissions.{perm} == true then {val} else empty end)"
                for perm, val in permissions_enum.items()
            )
            + "] | max) })"
        )
        collabs_jq = jq.compile(jq_expr.replace("{owner}", owner))

        endpoint = f"repos/{owner}/{repo}/collaborators"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        srv.check_retval(retval, err, endpoint=endpoint)
        collabs = collabs_jq.input_value(orjson.loads(out)).first()
        return collabs

    async def get_repos(self, *, paginate):
        """Return repos for a user."""
        _ = await self.get_user()
        repos_jq = jq.compile(
            r"map({"
            r"name: .name,"
            r"visibility: .visibility,"
            r"archived: .archived,"
            r"owner: .owner.login,"
            r"owner_type: .owner.type,"
            r"topics: .topics,"
            r"fork: .fork,"
            r"description: .description,"
            r"stargazers: .stargazers_count,"
            r"watchers: .watchers_count,"
            r"forks: .forks_count,"
            r"open_issues: .open_issues_count,"
            r"license: .license,"
            r"default_branch: .default_branch"
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
        srv.check_retval(retval, err, endpoint=endpoint)
        repos_json = orjson.loads(out)
        _log_one_json(repos_json)
        repos = repos_jq.input_value(repos_json).first()

        pins_query = """
{
  %s(login: "%s") {
    pinnedItems(first: 6, types: [REPOSITORY]) {
      nodes {
        ... on Repository {
          nameWithOwner
          url
        }
      }
    }
  }
}"""
        pins_jq = jq.compile(
            ".data.organization.pinnedItems.nodes[]?.nameWithOwner "
            '| sub("^[^/]+/"; "") // empty',
        )
        pins = {}
        for t, o in {(repo["owner_type"].lower(), repo["owner"]) for repo in repos}:
            retval, out, err = await srv.gh_graphql(
                query=pins_query % (t, o),
            )

            srv.check_retval(retval, err)
            pins_raw = orjson.loads(out)
            pins[o] = pins_jq.input_value(pins_raw).all() if pins_raw else []

        for repo in repos:
            repo["pinned"] = (
                repo["owner"] in pins and repo["name"] in pins[repo["owner"]]
            )

        async def query_repo(repo):
            try:
                collabs = await self._get_collaborators(
                    repo["owner"],
                    repo["name"],
                )
                _logger.debug2(f"Adding collabs to {repo['name']}: {collabs}")
                repo["collaborators"] = collabs
            except GHError as e:
                match = re.search(r"HTTP (4\d{2})", e.args[0])
                if match:
                    repo["collaborators"] = [f"({match.group(1)})"]
                else:
                    repo["collaborators"] = [e]

        await asyncio.gather(*[query_repo(repo) for repo in repos])

        folder_repos = repo_srv.RepoFolder()

        async def query_version(repo):
            _logger.debug(f"Downloading repo {repo['owner']}/{repo['name']}")
            private = repo["visibility"] == "private"
            url = "ssh://git@github.com" if private else None
            r = await folder_repos.add_repo(
                repo["owner"],
                repo["name"],
                url=url,
            )
            repo["version"] = await r.describe(repo["default_branch"])

        await asyncio.gather(*[query_version(repo) for repo in repos])

        sadness = int(not repos)
        return repos, sadness

    # this should take a name TODO (or several)
    class ConfigDescription(TypedDict):
        """Description of a config."""

        object: Any
        _original: str

    ConfigSet = dict[str, ConfigDescription]

    async def get_project_configs(
        self,
        repo: str,
        *filenames: str,
        ref: str | None = None,
    ) -> RetVal[ConfigSet]:
        """Find all projects in a repo."""
        if not filenames:
            raise ValueError("A least one filename must be supplied.")
        owner, repo = self._split_full_name(full_name=repo)
        folder_repos = repo_srv.RepoFolder()
        projects: dict = {}

        _logger.debug(f"Downloading repo {owner}/{repo}")
        r = await folder_repos.add_repo(
            owner,
            repo,
            url="ssh://git@github.com",
        )
        if not ref:
            ref = "main" if "main" in await r.list_branches() else "master"
        files: list[dict] = []
        for name in filenames:
            files.extend(await r.get_files_by_name(name, ref=ref) or [])
        configs: GHApi.ConfigSet = {}
        for f in files:
            obj = None
            if f["path"].endswith(".json"):
                obj = orjson.loads(f["content"])
            elif f["path"].endswith(".toml"):
                obj = tomllib.loads(f["content"].decode())
            configs[f["path"]] = {
                "object": obj,
                "_original": f["content"].decode(),
            }

        sadness = int(not projects)
        return configs, sadness

    @dataclass(slots=True, kw_only=True)
    class Tag:
        """Return type for get_remote_tags."""

        tag: str
        """Tag"""

        version: versions.Version | None = None
        """Calculated version."""

        def __post_init__(self):
            """Initialize derivative values."""
            self.version = versions.Version(self.tag)

        def tag_diff(self) -> bool:
            """Check if our version tag correctly formatted."""
            # NOTE: this is biased towards python, semver is different!
            return self.tag.removeprefix("v") != str(self.version).removeprefix("v")

        def __json__(self):
            """Convert to json."""
            return {
                "tag": self.tag,
                "version": self.version.__json__() if self.version else None,
            }

    async def get_remote_tags(self, repo, count=None) -> RetVal[list[Tag]]:
        """Return tags ("tag":"name") for a repo."""
        _ = await self.get_user()
        tags_jq = jq.compile("map({tag: .name})")
        owner, repo = self._split_full_name(full_name=repo)
        endpoint = f"repos/{owner}/{repo}/tags"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        srv.check_retval(retval, err, endpoint=endpoint)
        tags_dict = tags_jq.input_value(orjson.loads(out)).first()
        tags = [GHApi.Tag(**tag) for tag in tags_dict]
        sadness = int(not tags)
        return tags[:count], sadness

    @dataclass(slots=True, kw_only=True)
    class Release(Tag):
        """Release object containing version and files."""

        prerelease: bool
        """Does the source mark it as prerelease?"""
        files: list[str]
        """Files that came with it."""
        audit: ReleaseAudit | None = None

        def __json__(self):
            """Convert to json."""
            old = GHApi.Tag.__json__(self)
            old.update(
                {
                    "prerelease": self.prerelease,
                    "files": self.files,
                    "audit": self.audit.__json__() if self.audit else None,
                },
            )
            return old

    async def get_pypi(
        self,
        project_name: str,
        *,
        testing: bool = False,
    ) -> RetVal[list[Release]]:
        """Get all pypi releases for ALL projects in a repo."""
        prefix = "test." if testing else ""

        url = f"https://{prefix}pypi.org/pypi/{project_name}/json"
        _logger.debug(url)
        try:
            jq_dir = (
                r".releases // {} | "
                r"to_entries | map("
                r"{tag: .key, files:"
                r"[ .value[] | select(.yanked != true) | .filename ]"
                r"})"
            )
            pypi_jq = jq.compile(jq_dir)
            session = aiohttp.ClientSession()
            response = await session.get(url)
            pypi_json = await response.json()
            if pypi_json.get("message", None) == "Not Found":
                return [], 1
            releases = pypi_jq.input_value(pypi_json).first()
        finally:
            await response.release()
            await session.close()

        sadness = int(not releases)
        coerced_releases: list[GHApi.Release] = [
            GHApi.Release(
                **r,
                prerelease=versions.Version(r["tag"]).is_prerelease,
            )
            for r in releases
        ]
        return coerced_releases, sadness

    async def get_releases(self, repo: str) -> RetVal[list[Release]]:
        """Return releases for a repo."""
        _ = await self.get_user()
        releases_jq = jq.compile(
            r"map("
            r"select(.draft | not) | "
            r"{"
            r"tag: .tag_name, "
            r"prerelease: .prerelease, "
            r"files: [.assets | .[]? | .name], "
            r"}"
            r")",
        )
        owner, repo = self._split_full_name(full_name=repo)
        endpoint = f"repos/{owner}/{repo}/releases"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        srv.check_retval(retval, err, endpoint=endpoint)
        obj = orjson.loads(out)
        releases = releases_jq.input_value(obj).first()
        sadness = int(not releases)
        coerced_releases: list[GHApi.Release] = [
            GHApi.Release(
                **r,
            )
            for r in releases
        ]
        return coerced_releases, sadness

    async def audit_versions(  # noqa: C901
        self,
        repo: str,
        count: int = 20,
        only_version: str | None = None,
    ) -> RetVal[list[dict]]:
        """
        Verify that version of a repository have differences.

        Args:
            repo: the name of the repo to verify. Can be "owner/repo" or just
            "repo" and owner is assumed to be the current user.
            count: the number of versions to look at
            only_version: deep dive on one version

        """
        project_configs, sadness = await self.get_project_configs(
            repo,
            "pyproject.toml",
        )

        project_names = []
        for path, config in project_configs.items():
            if not path.endswith("pyproject.toml"):
                continue
            name = config.get("object", {}).get("project", {}).get("name", {})
            if name:
                project_names.append(name)
        if len(project_names) > 1:
            raise NotImplementedError("Repo has more than one project :-(")

        (
            (tags, _),
            (release, _),
            (pypi, pypi_sadness),
            (test_pypi, test_pypi_sadness),
        ) = await asyncio.gather(
            self.get_remote_tags(repo),
            self.get_releases(repo),
            (self.get_pypi(project_names[0]) if project_names else _noop(2, [])),
            (
                self.get_pypi(project_names[0], testing=True)
                if project_names
                else _noop(2, [])
            ),
        )

        @dataclass(slots=True)
        class VersionSet:
            gh_tags: GHApi.Tag | None = None
            gh_releases: GHApi.Release | None = None
            pypi: GHApi.Release | None = None
            test_pypi: GHApi.Release | None = None

        all_versions: dict[
            versions.Version,
            VersionSet,
        ] = {}

        for attrname, o in itertools.chain(
            (("gh_tags", t) for t in tags),
            (("gh_releases", r) for r in release),
            (("pypi", r) for r in pypi),
            (("test_pypi", r) for r in test_pypi),
            [],
        ):
            v = getattr(o, "version", None) or versions.Version(o.tag)
            if not v.valid:
                continue
            vset = all_versions.setdefault(v, VersionSet())
            if getattr(vset, attrname, None):
                warnings.warn(
                    "Looks like conflicting poorly-written versions caused overwrite.",
                    stacklevel=2,
                )
            if isinstance(o, GHApi.Release):
                o.audit = ReleaseAudit(o)
            setattr(vset, attrname, o)

        if only_version:
            v = versions.Version(only_version)
            r = all_versions.get(v)
            if not r:
                return [], 1
            all_versions = {v: r}
        all_versions = dict(sorted(all_versions.items(), reverse=True))
        result = [
            {
                "version": v.__json__(),
                "gh_tags": r.gh_tags.__json__() if r.gh_tags else None,
                "gh_releases": (r.gh_releases.__json__() if r.gh_releases else None),
                "pypi": r.pypi.__json__() if r.pypi else None,
                "test.pypi": (r.test_pypi.__json__() if r.test_pypi else None),
                "validity": str(v.kind),
            }
            for v, r in list(all_versions.items())[:count]  # count
        ]

        return result, 0  # maybe no sadness for audit?

    async def _get_ruleset(self, owner, repo, ruleset_id):
        """Return releset for a user by Id."""
        endpoint = f"repos/{owner}/{repo}/rulesets/{ruleset_id}"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        srv.check_retval(retval, err, endpoint=endpoint)
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
        srv.check_retval(retval, err, endpoint=endpoint)
        active_rulesets = rulesets_jq.input_value(orjson.loads(out)).first()

        if not active_rulesets:
            return [], 1

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
