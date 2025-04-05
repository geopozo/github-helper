import orjson
from tabulate import tabulate


class GHAdapter:
    """Allows the CLI to transform the data as required."""

    def _to_json_string(self, data):
        return orjson.dumps(
            data,
            option=orjson.OPT_INDENT_2 if self._pretty else None,
        ).decode()

    def _to_table(self, data):
        return tabulate(
            data,
            headers="keys" if self._pretty else "",
            tablefmt="psql" if self._pretty else "plain",
        )

    def __init__(self, json, pretty):
        self._json = json
        self._pretty = pretty

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

    def transform_repos_data(self, repos_data):
        if self._json:
            return self._to_json_string(repos_data)
        if self._pretty:
            for repo in repos_data:
                repo["name"] = repo["name"][:24]
                repo["collaborators"] = ",".join(
                    [s[:6] for s in repo["collaborators"]],
                )
            return self._to_table(repos_data)
        return self._to_table(
            [
                [
                    repo["name"][:24],
                    repo["visibility"],
                    "archived" if repo["archived"] else "active",
                    repo["owner"],
                    ",".join(
                        [s[:6] for s in repo["collaborators"]],
                    ),
                ]
                for repo in repos_data
            ],
        )

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
