class GHAdapter:
    """Allows the CLI to transform the data as required."""

    def __init__(self, json, pretty):
        self._json = json
        self._pretty = pretty
