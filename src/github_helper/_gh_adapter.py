class GHAdapter:
    """Allows the CLI to transform the data as required."""

    def __init__(self, json, pretty):
        self._json = json
        self._pretty = pretty

    def transform_user_data(self, user_data):
        if self._json or self._pretty:
            return {"user": user_data}
        return [[user_data]]
