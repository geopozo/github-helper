# move down to note about where i stopped.
# my strategy suggested one release of the lowest common denominator
# numpy releases many combinations.
"""
Github and Pypi versions can contain multiple files: here are tools.

a) the versions can have multiple projects (separated by name).

b) compiled binary extensions: When writing python (or javascript) extensions
in C, C++, rust, etc, you have to create a separate binary for each
environment you wish to support, and there are several levels.

Here is a list of the environments we check for:

.
|-- Windows
|   |-- x86_64
|   |-- Arm64
|   `-- Win32
|-- Mac
|   |-- Apple ARM
|   |-- Intel
|   `-- Universal (1 binary twice the size, 2 architectures)
`-- Linux
    |-- x86_64
    |   |-- Glibc-2.17
    |   |-- Glibc-2.28
    |   |-- Glibc-2.31
    |   |-- Glibc-2.35
    |   `-- musl
    |-- Arm64
    |   |-- Glibc-2.17
    |   |-- Glibc-2.28
    |   |-- Glibc-2.31
    |   |-- Glibc-2.35
    |   `-- musl
    `-- Arm32
        |-- Glibc-2.17
        |-- Glibc-2.28
        |-- Glibc-2.31
        |-- Glibc-2.35
        `-- musl

On top of that, we have to see what is the minimum python version supported for
each one.
"""

import re

import logistro
import semver
from packaging import version

_logger = logistro.getLogger(__name__)


class ReleaseAudit:
    prerelease_agree: bool

    def __init__(self, release):
        self.version = self.explode_versions(release["tag"])
        if not self.version:
            return
        self.prerelease_agree = self.version["is_prerelease"] == release["prerelease"]

    def explode_versions(self, tag):
        v = None
        try:
            v = version.Version(tag)
        except version.InvalidVersion:
            pass
        try:
            v = semver.Version.parse(tag)
        except ValueError:
            pass
        if not v:
            return None
        ret = {
            "major": v.major,
            "minor": v.minor,
            "patch": v.patch if hasattr(v, "patch") else v.micro,
            "pre": v.prerelease if hasattr(v, "prerelese") else v.pre,
            "dev": v.dev if hasattr(v, "dev") else None,
            "post": v.post if hasattr(v, "post") else None,
        }
        ret["is_prerelease"] = (
            v.is_prerelease if hasattr(v, "is_prerelease") else bool(v.pre)
        )
        return ret

    def __str__(self):
        ret = ""
        if not self.prerelease_agree:
            ret += "prerelease disagreement.\n"
        return ret


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
    return {v[key] for v in versions if _regex.match(v[key])}
