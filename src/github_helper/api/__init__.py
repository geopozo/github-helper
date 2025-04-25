"""A CLI dashboard for github status."""

import asyncio
import re
import tomllib
import warnings
from pathlib import Path

import aiohttp
import colored
import jq  # type: ignore [import-not-found]
import logistro
import orjson

from github_helper._services import gh as srv
from github_helper._services import repos as repo_srv
from github_helper._services import ssh_srv
from github_helper._services.gh import GHError, ScopesError, ScopesWarning
from github_helper._utils import load_json
from github_helper.api import _audit, _compare_versions

_logger = logistro.getLogger(__name__)
_SCRIPT_DIR = Path(__file__).resolve().parent
_TEMPLATE_PATH = _SCRIPT_DIR / "templates"


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

    async def get_project_configs(self, repo):
        """Find all projects in a repo."""
        owner, repo = self._split_full_name(full_name=repo)
        folder_repos = repo_srv.RepoFolder()
        projects = {}

        _logger.debug(f"Downloading repo {owner}/{repo}")
        r = await folder_repos.add_repo(
            owner,
            repo,
            url="ssh://git@github.com",
        )
        ref = "main" if "main" in await r.list_branches() else "master"
        py_files = await r.get_files_by_name("pyproject.toml", ref=ref)
        js_files = await r.get_files_by_name("package.json", ref=ref)
        if py_files:
            projects["py"] = {}
            for f in py_files:
                _logger.debug2(f"Found py: {f['path']}")
                projects["py"][f["path"]] = {
                    "object": tomllib.loads(f["content"].decode()),
                    "_original": f["content"].decode(),
                }
        if js_files:
            projects["js"] = {}
            for f in js_files:
                _logger.debug2(f"Found js: {f['path']}")
                obj = orjson.loads(f["content"])
                projects["js"][f["path"]] = {
                    "object": obj,
                    "_original": f["content"].decode(),
                }

        sadness = int(not projects)
        return projects, sadness

    async def get_remote_tags(self, repo):
        """Return tags ("tag":"name") for a repo."""
        _ = await self.get_user()
        tags_jq = jq.compile("map({tag: .name})")
        owner, repo = self._split_full_name(full_name=repo)
        endpoint = f"repos/{owner}/{repo}/tags"
        _logger.debug(f"Calling API: {endpoint}")
        retval, out, err = await srv.gh_api(endpoint)
        srv.check_retval(retval, err, endpoint=endpoint)
        tags = tags_jq.input_value(orjson.loads(out)).first()
        sadness = int(not tags)
        return tags, sadness

    # probably need to handle specific projects
    # project metadata usually has github repo
    async def get_pypi(self, repo, *, testing=False, flatten=False):
        """Get all pypi releases for ALL projects in a repo."""
        project_configs, sadness = await self.get_project_configs(repo)
        project_names = set()
        if "py" in project_configs:
            for config in project_configs["py"].values():
                name = config.get("object", {}).get("project", {}).get("name", {})
                if name:
                    project_names.add(name)
        prefix = "test." if testing else ""

        async def fetch_json(name):
            url = f"https://{prefix}pypi.org/pypi/{name}/json"
            _logger.debug(url)
            try:
                jq_dir = (
                    r".releases // {} | "
                    r"to_entries | map("
                    r'{tag: "v\(.key)", files:'
                    r"[ .value[] | select(.yanked != true) | .filename ]"
                    r"})"
                )
                pypi_jq = jq.compile(jq_dir)
                session = aiohttp.ClientSession()
                response = await session.get(url)
                pypi_json = await response.json()
                data = pypi_jq.input_value(pypi_json).first()
                return _compare_versions.order_versions(data, "tag")
            finally:
                await response.release()
                await session.close()

        releases = {}
        for name in project_names:
            releases[name] = await fetch_json(name)
        sadness = int(not releases)
        if flatten:
            # two objects may have same tag
            releases = [release for project in releases.values() for release in project]
        return releases, sadness

    async def audit_pypi(self, repo, count=7, *, testing=False):
        """Get all pypi releases for a project and audit it."""
        releases, sadness = await self.get_pypi(
            repo,
            testing=testing,
            flatten=True,
        )
        if sadness:
            return None, sadness

        for release in releases:
            release["audit"] = _compare_versions.ReleaseAudit(
                release,
                prerelease_respect=True,
            )

        # I want count to be the API call or something
        # but it has to be ordered first.
        return (
            _compare_versions.order_versions(releases, "tag")[:count],
            sadness,
        )

    async def get_releases(self, repo):
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
        _logger.debug2("get_releases")
        _log_one_json(obj)
        releases = releases_jq.input_value(obj).first()
        sadness = int(not releases)
        return releases, sadness

    async def audit_releases(self, repo, count=7):
        """Run get_releases and process information."""
        releases, sadness = await self.get_releases(repo)
        if sadness:
            return None, sadness

        for release in releases:
            release["audit"] = _compare_versions.ReleaseAudit(release)

        # I want count to be the API call or something
        # but it has to be ordered first.
        return (
            _compare_versions.order_versions(releases, "tag")[:count],
            sadness,
        )

    async def audit_versions(self, repo):
        """
        Verify that version of a repository have differences.

        Args:
            repo: the name of the repo to verify. Can be "owner/repo" or just
            "repo" and owner is assumed to be the current user.

        """
        # puede mezclar proyectos acá
        # Ignoramos nombre de proyecto
        # todavia no probamos con mas de un projection en repositorio
        async with asyncio.TaskGroup() as tg:
            tags_task = tg.create_task(self.get_remote_tags(repo))
            releases_task = tg.create_task(self.audit_releases(repo))
            pypi_task = tg.create_task(self.audit_pypi(repo))
            test_pypi_task = tg.create_task(self.audit_pypi(repo, testing=True))
            # que hacemos con sadness?
            tags, _ = await tags_task
            releases, _ = await releases_task
            pypi, _ = await pypi_task
            test_pypi, _ = await test_pypi_task

        c_tags = _compare_versions.conform_versions(
            _compare_versions.filter_versions(tags),
        )
        c_releases = _compare_versions.conform_versions(releases)
        c_pypi = _compare_versions.conform_versions(pypi)
        c_test_pypi = _compare_versions.conform_versions(test_pypi)

        all_versions = (
            c_tags.keys() | c_releases.keys() | c_pypi.keys() | c_test_pypi.keys()
        )

        yes = f"{colored.Fore.green}True{colored.Style.reset}"
        no = f"{colored.Fore.red}False{colored.Style.reset}"

        def empty(x="Empty"):
            return f"{colored.Fore.yellow}{x}{colored.Style.reset}"

        result = _compare_versions.order_versions(
            [
                {
                    "version": v,
                    "tags": (no if v not in c_tags else yes),
                    "releases": (
                        no
                        if v not in c_releases
                        else empty(empty)
                        if c_releases[v]["empty"]
                        else yes
                    ),
                    "pypi": (
                        no
                        if v not in c_pypi
                        else empty("yanked")
                        if c_pypi[v]["empty"]
                        else yes
                    ),
                    "test.pypi": (
                        no
                        if v not in c_test_pypi
                        else empty("yanked")
                        if c_test_pypi[v]["empty"]
                        else yes
                    ),
                }
                for v in all_versions
            ],
            "version",
        )
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
