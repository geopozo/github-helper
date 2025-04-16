import re

from packaging import version


def order_versions(versions: list[dict], key: str):
    return sorted(
        versions,
        key=lambda x: version.parse(x[key]),
        reverse=True,
    )


def filter_versions(versions: list[dict], key: str):
    _regex = re.compile(
        r"^" + version.VERSION_PATTERN + r"$",
        re.VERBOSE,
    )
    return [v for v in versions if _regex.match(v[key])]
