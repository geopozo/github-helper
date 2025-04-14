import json

from github_helper._utils import AutoEncoder


def to_json_string(data, *, pretty=False):
    return json.dumps(
        data,
        indent=2 if pretty else 0,
        cls=AutoEncoder,
    )
