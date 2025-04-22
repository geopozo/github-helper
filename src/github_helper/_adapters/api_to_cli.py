import urllib.parse

import logistro

from github_helper._adapters import to_html, to_json, to_table
from github_helper._utils import strip_keys

_logger = logistro.getLogger(__name__)


class GHAdapter:
    """Allows the CLI to transform the data as required."""

    def _check_options(self, formatters):
        formats = {k for k, v in formatters.items() if v}
        invalid_formats = {"html", "url"} & formats
        if (self._command == "auth-status" and formats) or (
            self._command != "repos" and invalid_formats
        ):
            raise NotImplementedError(
                f"{', '.join(invalid_formats)} not valid flags for {self._command}",
            )
        return True

    def __init__(self, **args: dict):
        valid_args = {"command", "json", "pretty", "html", "url"}
        if args.keys() - valid_args:
            raise ValueError("Additional args coming in from cli")
        self._command = args.pop("command")
        self._json = args.get("json", False)
        self._pretty = args.get("pretty", False)
        self._html = args.get("html", False)
        self._url = args.get("url", False)
        self._check_options(args)

    async def transform_orgs_data(self, orgs_data):
        if self._json:
            return to_json.format_json(orgs_data, pretty=self._pretty)
        for org in orgs_data:
            org["name"] = org["name"][:24]
        return to_table.format_table(orgs_data, pretty=self._pretty)

    async def transform_project_configs_data(self, config_data):
        if self._json:
            return to_json.format_json(strip_keys(config_data), pretty=self._pretty)
        data = [
            [
                f"{language}: {path}",
                content["_original"],
            ]
            for language, config in config_data.items()
            for path, content in config.items()
        ]
        return to_table.format_table(data, pretty=self._pretty)

    async def transform_user_data(self, user_data):
        if self._json:
            return to_json.format_json({"user": user_data}, pretty=self._pretty)
        if self._pretty:
            return to_table.format_table([{"user": user_data}], pretty=self._pretty)
        return user_data

    async def transform_scopes_data(self, scopes_data):
        if self._json:
            return to_json.format_json(scopes_data, pretty=self._pretty)
        if self._pretty:
            return to_table.format_table(
                [{"scope": scope} for scope in scopes_data],
                pretty=self._pretty,
            )
        return to_table.format_table([scopes_data], pretty=self._pretty)

    async def transform_repos_data(self, repos_data):
        if self._html:
            generated_html = str(await to_html.repos(repos_data))
            if not self._url:
                return generated_html
            encoded = urllib.parse.quote(generated_html)
            return f"data:text/html;charset=utf-8,{encoded}"

        if self._json:
            return to_json.format_json(repos_data, pretty=self._pretty)

        data = [
            [
                f"{repo['owner']}/{repo['name']}",
                (
                    f"{'*' if repo['pinned'] else ''}"
                    f"{'f-' if repo['fork'] else ''}{repo['visibility']}"
                    f"{'-ar' if repo['archived'] else ''}"
                ),
                ",".join(
                    [str(s)[:6] for s in repo["collaborators"]],
                ),
                f"{','.join(repo['topics'])}",
            ]
            for repo in repos_data
        ]

        return to_table.format_table(
            data,
            pretty=self._pretty,
            headers=("repo", "type", "people", "topics"),
        )

    async def transform_tags_data(self, tags_data):
        if self._json:
            return to_json.format_json(tags_data, pretty=self._pretty)
        return to_table.format_table(tags_data, pretty=self._pretty)

    async def transform_releases_data(self, releases_data):
        if self._json:
            return to_json.format_json(releases_data, pretty=self._pretty)
        delim = "," if not self._pretty else "\n"
        return to_table.format_table(
            [
                [
                    release["tag"],
                    delim.join(release["files"]),
                ]
                for release in releases_data
            ],
            pretty=self._pretty,
            headers=("version", "files"),
        )

    async def transform_pypi_data(self, releases_data):
        if self._json:
            return to_json.format_json(releases_data, pretty=self._pretty)
        delim = "," if not self._pretty else "\n"
        return to_table.format_table(
            [
                [
                    f"{name}-{release["tag"]}",
                    delim.join(release["files"]),
                ]
                for name, subobject in releases_data.items()
                for release in subobject
            ],
            pretty=self._pretty,
            headers=("version", "files"),
        )

    async def transform_audit_releases_data(self, releases_data):
        if self._json:
            return to_json.format_json(releases_data, pretty=self._pretty)

        rows = [
            [
                release["tag"],
                release["audit"],
            ]
            for release in releases_data
        ]
        return to_table.format_table(
            rows,
            pretty=True,  # force pretty
            headers=("version", "notes"),
            colalign=("right", "left"),
        )

    async def transform_audit_rulesets_data(self, audit_rulesets_data):
        if self._json:
            return to_json.format_json(audit_rulesets_data, pretty=self._pretty)
        for rule in audit_rulesets_data:
            rule["template"] = rule["template"][:24]
        return to_table.format_table(audit_rulesets_data, pretty=self._pretty)

    async def transform_audit_versions_data(self, version_data):
        if self._json:
            return to_json.format_json(version_data, pretty=self._pretty)
        return to_table.format_table(version_data, pretty=self._pretty)
