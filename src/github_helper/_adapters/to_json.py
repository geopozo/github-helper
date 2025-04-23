import json

from github_helper._utils import AutoEncoder


def format_json(data, *, pretty=False):
    return json.dumps(
        data,
        indent=2 if pretty else None,
        cls=AutoEncoder,
    )
