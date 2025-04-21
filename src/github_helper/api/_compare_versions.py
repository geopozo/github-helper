"""Github and Pypi versions can contain multiple files: here are tools."""

import re

import logistro
import semver
from packaging import utils, version

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


def get_file_notes(tag: str, filename: str):  # noqa: PLR0911
    if filename.endswith("tar.gz"):
        try:
            name, version = utils.parse_sdist_filename(filename)
        except utils.InvalidSdistFilename:
            _logger.debug(f"Invalid Sdist Filename: {filename}")
            return {"error": "unrecognized name"}
        else:
            return {"name": name, "type": "sdist", "language": "python"}

    elif filename.endswith(".whl"):
        try:
            name, version, build, compat_tags = utils.parse_wheel_filename(filename)
        except utils.InvalidWheelFilename:
            _logger.debug(f"Invalid Wheel Filename: {filename}")
            return {"error": "invalid name"}
        else:
            return {
                "name": name,
                "type": "bdist",
                "language": "python",
                "tags": compat_tags,
            }
    elif filename.endswith(("sigstore.json", ".sha256")):
        return {"type": "metadata"}
    elif filename in (f"{tag}.zip", f"{tag}.tar.gz"):
        return {"type": "github-archive"}
    else:
        return {"error": "unknown"}
