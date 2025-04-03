class GHAdapter:
    """Allows the CLI to transform the data as required."""

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
            [repo["name"], repo["visibility"], repo["archived"], repo["owner"]]
            for repo in repos_data
        ]

    def transform_tags_data(self, tags_data):
        if self._json or self._pretty:
            return tags_data
        return [[tag["name"]] for tag in tags_data]
