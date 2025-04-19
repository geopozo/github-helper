import re
from dataclasses import field
from typing import NamedTuple

import semver
from packaging import version

GlibcReference = {
    "2.17": "Most compatible.",
    "2.28": "Debian 10. Reasonably Compatible >2018",
    "2.29": "Transitional Version.",
    "2.31": "Ubuntu 20.04",
    "2.34": "Ubuntu 22.04",
    "2.35": "Ubuntu >22.04.1. 2022+",
    "2.36": "New?",
    "2.38": "Released Yesterday?",
}
GlibcRecommended = ("2.17", "2.28", "2.31", "2.34")


class GlibcVersions(dict):
    """Simple wrapper of dict."""


class ArchSet(NamedTuple):
    x86: bool | GlibcVersions | None
    x86_64: bool | GlibcVersions | None
    arm64: bool | GlibcVersions | None
    arm32: bool | GlibcVersions | None


class ProjectAudit:
    name: str
    language: str


class PyProjectAudit(ProjectAudit):
    pure_python: bool
    compiled: bool
    minimum_interpreter: str
    abi3_all: bool
    inconsistent_options: bool
    win: ArchSet
    mac: ArchSet
    linux_glibc: ArchSet
    linux_musl: ArchSet

    non_compliant: field(default_factory=list[str])


class ReleaseAudit:
    prerelease_agree: bool
    projects: field(default_factory=list[ProjectAudit])


def explode_versions(tag):
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
