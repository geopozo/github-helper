import json
import urllib.parse

import logistro
from tabulate import tabulate

import github_helper._api_to_html_adapter as html_adapter
from github_helper._utils import AutoEncoder

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

    def _to_json_string(self, data):
        return json.dumps(
            data,
            indent=2 if self._pretty else 0,
            cls=AutoEncoder,
        )

    def _to_table(self, data, headers="keys"):
        return tabulate(
            data,
            headers=headers if self._pretty else "",
            tablefmt="psql" if self._pretty else "plain",
        )

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

    def transform_orgs_data(self, orgs_data):
        if self._json:
            return self._to_json_string(orgs_data)
        for org in orgs_data:
            org["name"] = org["name"][:24]
        return self._to_table(orgs_data)

    def transform_user_data(self, user_data):
        if self._json:
            return self._to_json_string({"user": user_data})
        if self._pretty:
            return self._to_table([{"user": user_data}])
        return user_data

    def transform_scopes_data(self, scopes_data):
        if self._json:
            return self._to_json_string(
                scopes_data,
            )
        if self._pretty:
            return self._to_table(
                [{"scope": scope} for scope in scopes_data],
            )
        return self._to_table([scopes_data])

    async def transform_repos_data(self, repos_data):
        if self._html:
            generated_html = str(await html_adapter.repos(repos_data))
            if not self._url:
                return generated_html
            encoded = urllib.parse.quote(generated_html)
            return f"data:text/html;charset=utf-8,{encoded}"

        if self._json:
            return self._to_json_string(repos_data)

        data = [
            [
                f"https://github.com/{repo['owner']}/{repo['name']}",
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

        return self._to_table(data, ("repo", "type", "people", "topics"))

    def transform_tags_data(self, tags_data):
        if self._json:
            return self._to_json_string(tags_data)
        return self._to_table(tags_data)

    def transform_releases_data(self, releases_data):
        if self._json:
            return self._to_json_string(releases_data)
        if self._pretty:
            return self._to_table(releases_data)
        return self._to_table(
            [
                [
                    release["tag"],
                    "published" if release["published"] else "unpublished",
                ]
                for release in releases_data
            ],
        )

    def transform_audit_rulesets_data(self, audit_rulesets_data):
        if self._json:
            return self._to_json_string(audit_rulesets_data)
        for rule in audit_rulesets_data:
            rule["template"] = rule["template"][:24]
        return self._to_table(audit_rulesets_data)
