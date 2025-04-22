"""
Github and Pypi versions can contain multiple files: here are tools.

How do I improve parsing?

1. If you want to process a new type of file:
    a. Modify `_get_file_notes()`
    b. Return a dictionary with a known action + needed key-value pairs
        I. Possibly modify the existing action in `add_file()` to deal
            with new information
        II. Make sure `__str__` knows how to print that information.
    c. Create a new action:
        I. Add the action to `add_file()`
        II. If it's going to add to `self.projects`, you either need to
            - Create a new entry in `__str__()` to print it
            - Modify the existing code (but you'd probably be doing b.)
2. If you want to update the OS Compatibility tree, to include new tags,
    look at the bdist branch conditional in _build_python_summary


"""

import copy
import re
from dataclasses import field

import logistro
import semver
from packaging import utils, version

_logger = logistro.getLogger(__name__)


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


bdist_template = {
    "All OS": [],
    "Windows": {
        "x86_64": [],
        "Arm64": [],
        "Win32": [],
    },
    "Mac": {
        "Apple ARM": [],
        "Intel": [],
    },
    "Linux": {
        "x86_64": {
            "Glibc": {
                "2.17": [],
            },
            "musl": [],
        },
        "Arm64": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
        "Arm32": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
    },
}


class ReleaseAudit:
    prerelease_agree: bool
    projects: field(default_factory=dict)
    file_notes: field(default_factory=dict[str, dict])
    unknown_files: field(default_factory=set)
    ignore_counter: field(default_factory=dict[str, int])

    def __init__(self, release):
        self.tag = release["tag"]
        self.version = self.explode_versions()
        if not self.version:
            return
        self.prerelease_agree = self.version["is_prerelease"] == release["prerelease"]

        self.file_notes = {}
        self.unknown_files = set()
        self.ignore_counter = {}
        self.projects = {}
        [self.summarize_file(file) for file in release["files"]]

    def explode_versions(self):
        v = None
        try:
            v = version.Version(self.tag)
        except version.InvalidVersion:
            pass
        try:
            v = semver.Version.parse(self.tag)
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

    def __str__(self):  # noqa: C901, PLR0912
        ret = ""
        if not self.prerelease_agree:
            ret += "PRERELEASE DISAGREEMENT\n"
        if self.projects:
            for k, v in self.projects.items():
                if k.startswith("python/"):
                    ## look at bdist/sdist
                    warn = ""
                    if not v["bdist"]:
                        warn = "bdist"
                    if not v["sdist"]:
                        warn = ", sdist" if warn else "sdist"
                    warn = f", missing {warn}" if warn else ""

                    pure = ""
                    if v["pure"]:
                        pure = f", pure: {", ".join(v['pure'])}"

                    ret += f"{k}{warn}{pure}\n"

                    ## look at tags
                    ret += (
                        "\n".join(self._build_tree_str(v["bdist-tree"])) + "\n"
                        if v["bdist-tree"]
                        else ""
                    )

                    if v["unknown-tags"]:
                        ret += " Unknown Tags:\n "
                        ret += "\n ".join(v["unknown-tags"]) + "\n"
        if self.unknown_files:
            ret += f"{len(self.unknown_files)} Unknown Files:\n"
            for i, f in enumerate(self.unknown_files):
                if i > 3:  # noqa: PLR2004
                    ret += "...\n"
                    break
                ret += f"{f}\n"
        if self.ignore_counter:
            ret += "ignored: "
            for k, v in self.ignore_counter.items():
                ret += f"{k} {v} time(s)"
            ret += "\n"
        return ret

    def summarize_file(self, filename: str):
        notes = self._get_file_notes(filename)
        match notes.get("action"):
            case "ignore":
                why = notes.get("type", "other")
                self.ignore_counter[why] = self.ignore_counter.get(why, 0) + 1
            case "python-compat":
                self._build_python_project_summary(notes)
            case _:
                self.unknown_files.add(filename)
        return notes

    # the action you return will trigger behavior above
    def _get_file_notes(self, filename: str):
        if filename in (f"{self.tag}.zip", f"{self.tag}.tar.gz"):
            return {"type": "gh-archive", "action": "ignore"}
        elif filename.endswith("tar.gz"):
            try:
                name, version = utils.parse_sdist_filename(filename)
            except utils.InvalidSdistFilename:
                _logger.debug(f"Invalid Sdist Filename: {filename}")
            else:
                return {
                    "name": name,
                    "type": "sdist",
                    "language": "python",
                    "action": "python-compat",
                }
        elif filename.endswith(".whl"):
            try:
                name, version, build, compat_tags = utils.parse_wheel_filename(filename)
            except utils.InvalidWheelFilename:
                _logger.debug(f"Invalid Wheel Filename: {filename}")
                return {"error": "invalid name", "value": filename}
            else:
                return {
                    "name": name,
                    "type": "bdist",
                    "language": "python",
                    "tags": compat_tags,
                    "action": "python-compat",
                }
        elif filename.endswith(("sigstore.json", ".sha256")):
            return {"type": "metadata", "action": "ignore"}
        return {"error": "unrecognized name", "value": filename}

    def _build_python_project_summary(self, notes):
        name = f"python/{notes['name']}"
        if name not in self.projects:
            self.projects[name] = {
                "sdist": False,
                "bdist": False,
                "pure": [],
                "bdist-tree": None,
                "unknown-tags": [],
            }
        ref = self.projects[name]
        if notes.get("type") == "sdist":
            ref["sdist"] = True
        elif notes.get("type") == "bdist":
            ref["bdist"] = True
            for t in notes.get("tags"):
                # t.abi, t.interpreter, t.platform
                if t.platform == "any" and t.abi == "none":
                    ref["pure"].append(t.interpreter)
                    continue
                if not ref["bdist-tree"]:
                    ref["bdist-tree"] = copy.deepcopy(bdist_template)
                pair = f"{t.interpreter}-{t.abi}"
                if t.platform == "any":
                    ref["bdist-tree"]["All OS"].append(pair)
                else:
                    ref["unknown-tags"].append(str(t))

    def _build_tree_str(self, obj, indent="", *, is_last=True):
        lines = []

        if isinstance(obj, dict):
            items = list(obj.items())
            for i, (key, value) in enumerate(items):
                is_last = i == len(items) - 1
                branch = "`-- " if is_last else "|-- "
                next_indent = indent + ("    " if is_last else "|   ")
                lines.append(f"{indent}{branch}{key}")
                lines.extend(self._build_tree_str(value, next_indent))
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                is_last = i == len(obj) - 1
                branch = "`-- " if is_last else "|-- "
                lines.append(f"{indent}{branch}{item}")
        return lines
