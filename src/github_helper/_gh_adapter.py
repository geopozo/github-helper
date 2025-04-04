import orjson
from tabulate import tabulate


class GHAdapter:
    """Allows the CLI to transform the data as required."""

    def _to_json_string(self, data, *, indent=None):
        return orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 if indent else None,
        ).decode()

    def _to_table(self, data, *, pretty=None):
        return tabulate(
            data,
            headers="keys" if pretty else "",
            tablefmt="psql" if pretty else "plain",
        )

    def __init__(self, json, pretty):
        self._json = json
        self._pretty = pretty

    def transform_orgs_data(self, orgs_data):
        if self._json or self._pretty:
            return orgs_data
        return [[org["name"], org["role"]] for org in orgs_data]

    def transform_user_data(self, user_data):
        if self._json or self._pretty:
            return {"user": user_data}
        return [[user_data]]

    def transform_scopes_data(self, scopes_data):
        if self._json or self._pretty:
            return [{"scope_name": scope} for scope in scopes_data]
        return [scopes_data]

    def transform_repos_data(self, repos_data):
        if self._json or self._pretty:
            return repos_data
        return [
            [
                repo["name"][:24],
                repo["visibility"],
                "archived" if repo["archived"] else "active",
                repo["owner"],
            ]
            for repo in repos_data
        ]

    def transform_tags_data(self, tags_data):
        if self._json or self._pretty:
            return tags_data
        return [[tag["name"]] for tag in tags_data]

    def transform_releases_data(self, releases_data):
        if self._json or self._pretty:
            return releases_data
        return [
            [
                release["name"],
                release["tag"],
                "published" if release["published"] else "unpublished",
            ]
            for release in releases_data
        ]

    def transform_audit_rulesets_data(self, audit_rulesets_data):
        if self._json or self._pretty:
            return audit_rulesets_data
        return [
            [audit_ruleset["template"], audit_ruleset["status"]]
            for audit_ruleset in audit_rulesets_data
        ]
