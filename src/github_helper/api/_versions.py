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
import sys
from dataclasses import dataclass
from enum import StrEnum
from functools import total_ordering

import logistro
import semver
from colored import Back, Fore, Style
from packaging import utils
from packaging import version as pyversion

_logger = logistro.getLogger(__name__)

if not sys.stdout.isatty():

    class NoColor:
        def __getattr__(self, name):
            return ""

    # Override colored's foreground, background, and style
    Fore = Back = Style = NoColor()  # type: ignore[misc, assignment]


def filter_versions(versions: list[dict]):
    # this needs to return a list of dictionaries
    _regex = re.compile(
        r"^" + pyversion.VERSION_PATTERN + r"$",
        re.VERBOSE,
    )
    return [v for v in versions if _regex.match(v.get("tag", ""))]


def order_versions(versions: list[dict], key: str):
    if not versions:
        return versions
    return sorted(
        versions,
        key=lambda x: pyversion.parse(x[key]),
        reverse=True,
    )


_VersionTypes = semver.Version | pyversion.Version


@total_ordering
@dataclass(frozen=True, slots=True)
class Version:
    """A unified version class."""

    class Type(StrEnum):
        PYTHON = "Python"
        SEMVER = "SemVer"
        MALFORMED = "Malformed Python"

    tag: str
    valid: bool
    type: Type
    major: int
    minor: int
    patch: int
    pre: str
    dev: str
    post: str
    is_prerelease: bool
    _parsed: _VersionTypes

    def __init__(self, tag: str):
        object.__setattr__(self, "tag", tag)
        parsed_v, kind = self._test_parsers()
        if not parsed_v or not kind:
            object.__setattr__(self, "valid", False)
            return
        object.__setattr__(self, "valid", True)
        object.__setattr__(self, "type", kind)
        self._enumerate_version(parsed_v)

    def _test_parsers(
        self,
    ) -> tuple[_VersionTypes | None, Type | None]:
        """See which parsers handle the tag."""
        tag = self.tag
        try:
            parsed: _VersionTypes = pyversion.Version(tag)

            if str(parsed) != tag[1:] if tag.startswith("v") else tag:
                old_parsed = parsed
                try:
                    parsed = semver.Version.parse(tag)
                except ValueError:
                    return old_parsed, Version.Type.MALFORMED
                else:
                    return parsed, Version.Type.PYTHON
        except pyversion.InvalidVersion:
            pass
        else:
            return parsed, Version.Type.PYTHON
        try:
            parsed = semver.Version.parse(tag)
        except ValueError:
            pass
        else:
            return parsed, Version.Type.SEMVER
        return None, None

    def _enumerate_version(self, v: _VersionTypes) -> None:
        """Break tag attributes into unified attributes."""
        object.__setattr__(self, "_parsed", v)
        object.__setattr__(self, "major", v.major)
        object.__setattr__(self, "minor", v.minor)
        object.__setattr__(
            self,
            "patch",
            v.patch if hasattr(v, "patch") else v.micro,
        )
        object.__setattr__(
            self,
            "pre",
            str(
                v.prerelease
                if hasattr(v, "prerelease")
                else (f"{v.pre[0]}{v.pre[1]}" if v.pre else ""),
            ),
        )
        object.__setattr__(
            self,
            "dev",
            str(v.dev) if hasattr(v, "dev") else "",
        )
        object.__setattr__(
            self,
            "post",
            str(v.post) if hasattr(v, "post") else "",
        )
        object.__setattr__(
            self,
            "is_prerelease",
            (v.is_prerelease if hasattr(v, "is_prerelease") else bool(v.prerelease)),
        )

    def __str__(self):
        return str(self._parsed)

    def __repr__(self):
        return str(self._parsed)

    def _cmp_tuple(self) -> tuple:
        return (
            self.major,
            self.minor,
            self.patch,
            self.pre,
            self.dev,
            self.post,
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _VersionTypes):
            other = Version(str(other))
        elif not isinstance(other, Version):
            raise NotImplementedError
        return self._cmp_tuple() == other._cmp_tuple()

    def __lt__(self, other: object) -> bool:
        if isinstance(other, _VersionTypes):
            other = Version(str(other))
        elif not isinstance(other, Version):
            raise NotImplementedError
        return self._cmp_tuple() < other._cmp_tuple()


#### HERE BE DRAGONS #####


def conform_versions(versions: list[dict]):
    versions_dict: dict = {}
    for v in versions:
        temp = Version(v["tag"])
        v["conformant"] = temp.type
        if v["conformant"]:
            if v["tag"].startswith("V"):
                v["tag"][0] = "v"
            elif not v["tag"].startswith("v"):
                v["tag"] = f"v{v['tag']}"
        # always true for tag, use audit
        _logger.debug2(f"Files in {v['tag']}: {len(v.get('files', []))}")
        v["empty"] = not bool(v.get("files"))
        _logger.debug2(f"Empty {v['empty']} from {v.get('files')}")
        if v["tag"] in versions_dict:
            cur = versions_dict[v["tag"]]
            cur["empty"] = v["empty"]
            cur["files"].extend(v["files"])
        else:
            versions_dict[v["tag"]] = v
    return versions_dict


bdist_template = {
    "Windows": {
        "x86_64": [],
        "arm64": [],
        "win32": [],
    },
    "Mac": {
        "x86_64": {},
        "arm64": {},
        "universal2": {},
    },
    "Linux": {
        "x86_64": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
        "aarch64": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
        "armv7l": {
            "Glibc": {
                "2.17": [],
            },
            "musl": {},
        },
    },
}


def compare_audits(v, **audits):  # noqa: C901
    all_tags = set()
    for a in audits.values():
        audit = a.get(v, {}).get("audit", None)
        if not audit:
            continue
        for project in audit.projects.values():
            all_tags.update(project.get("all_tags", {}))
    results = {}

    # this inversion sucks
    # what to do if project is missing
    for tag in all_tags:
        results[tag] = set()
        for name, a in audits.items():
            audit = a.get(v, {}).get("audit", None)
            if not audit:
                results[tag].add(name)
                continue
            for project in audit.projects.values():
                if tag in project.get("all_tags", {}):
                    break
            else:
                results[tag].add(name)
        if not results[tag]:
            del results[tag]
    output = ""
    for tag, problems in results.items():
        output += f"{tag}: {', '.join(problems)}\n"

    return output


class ReleaseAudit:
    """Release audit turns a release object into a summary."""

    prerelease_agree: bool
    """Does the version agree with the mark about prerelease."""
    file_notes: dict[str, dict]
    """A dict representing the first interpretation of any file."""
    unknown_files: set
    """Files that couldn't be understood trying to calculate notes."""
    ignore_counter: dict[str, int]

    projects: dict
    """A list of the projects found in this release."""

    def __repr__(self):
        ignore_len = sum(self.ignore_counter.values())
        project_tag_count = [
            f"{k}: {len(v['all_tags'])}" for k, v in self.projects.items()
        ]

        return (
            f"pre-agree: {self.prerelease_agree}; "
            f"projects: {', '.join(project_tag_count)}; "
            f"{len(self.file_notes)} files w/ notes; "
            f"{len(self.unknown_files)} unknown files; "
            f"{ignore_len} ignored files."
        )

    def __init__(self, release, *, prerelease_respect=False):
        self.tag = release["tag"]
        self.version = self.explode_versions()
        self.file_notes = {}
        self.unknown_files = set()
        self.ignore_counter = {}
        self.projects = {}
        if not self.version:
            self.prerelease_agree = None
            return
        self.prerelease_agree = (
            (self.version["is_prerelease"] == release["prerelease"])
            if "prerelease" in release
            else prerelease_respect
        )

        [self.summarize_file(file) for file in release["files"]]

    def __str__(self):  # noqa: C901, PLR0912
        ret = ""
        if not self.prerelease_agree:
            ret += f"{Fore.red}PRERELEASE DISAGREEMENT{Style.reset}\n"
        if not self.projects:
            ret += f"{Fore.red}No Valid Projects Found.{Style.reset}\n"
        else:
            for k, v in self.projects.items():
                if k.startswith("python/"):
                    ## look at bdist/sdist
                    warn = ""
                    if not v["bdist"]:
                        warn = "bdist"
                    if not v["sdist"]:
                        warn = ", sdist" if warn else "sdist"
                    warn = f", {Fore.red}missing {warn}{Style.reset}" if warn else ""

                    pure = ""
                    if v["pure"]:
                        pure = (
                            f", {Fore.green}pure: {', '.join(v['pure'])}{Style.reset}"
                        )

                    ret += f"{Style.bold}{k}{Style.reset}{warn}{pure}\n"

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
            ret += (
                f"{Fore.yellow}{Style.bold}"
                f"{len(self.unknown_files)} Unknown Files:"
                f"{Style.reset}\n"
            )
            for i, f in enumerate(self.unknown_files):
                if i > 3:  # noqa: PLR2004
                    ret += f" {Fore.yellow}...{Style.reset}\n"
                    break
                ret += f" {Fore.yellow}{f}{Style.reset}\n"
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
        self.file_notes[filename] = notes
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

    # So, refactor, python project should be it's own class
    # And maybe should have its own adapters?
    def _build_python_project_summary(self, notes):  # noqa: PLR0912, C901
        name = f"python/{notes['name']}"
        if name not in self.projects:
            self.projects[name] = {
                "sdist": False,
                "bdist": False,
                "pure": [],
                "bdist-tree": None,
                "unknown-tags": [],
                "all_tags": set(),
            }
        ref = self.projects[name]
        if notes.get("type") == "sdist":
            ref["sdist"] = True
        elif notes.get("type") == "bdist":
            ref["bdist"] = True
            ref["all_tags"].update(notes.get("tags"))
            for t in notes.get("tags"):
                pair = f"{t.interpreter}-{t.abi}"
                # t.abi, t.interpreter, t.platform
                if t.platform == "any" and t.abi == "none":
                    ref["pure"].append(t.interpreter)
                    continue

                if not ref["bdist-tree"]:
                    ref["bdist-tree"] = copy.deepcopy(bdist_template)

                if t.platform == "any":
                    if "All OS" not in ref["bdist-tree"]:
                        ref["bdist-tree"]["All OS"] = [pair]
                    else:
                        ref["bdist-tree"]["All OS"].append(pair)
                elif r := self._parse_mac_platform(t.platform):
                    arch_dict = ref["bdist-tree"]["Mac"][r["arch"]]
                    if r["version"] not in arch_dict:
                        arch_dict[r["version"]] = [pair]
                    else:
                        arch_dict[r["version"]].append(pair)
                elif r := self._parse_win_platform(t.platform):
                    ref["bdist-tree"]["Windows"][r].append(pair)
                elif (r := self._parse_manylinux_platform(t.platform)) or (
                    r := self._parse_musllinux_platform(t.platform)
                ):
                    if r["arch"] not in ref["bdist-tree"]["Linux"]:
                        ref["bdist-tree"]["Linux"][r["arch"]] = {
                            "Glibc": {"2.17": []},
                            "musl": {},
                        }
                    libc = r["libc"]
                    libc_dict = ref["bdist-tree"]["Linux"][r["arch"]][libc]
                    if r["version"] not in libc_dict:
                        libc_dict[r["version"]] = [pair]
                    else:
                        libc_dict[r["version"]].append(pair)
                else:
                    ref["unknown-tags"].append(str(t))

    def _parse_mac_platform(self, tag):
        pattern = r"^macosx_(\d+)(?:_(\d+))?_(.+)$"
        m = re.match(pattern, tag)
        if not m:
            return {}

        major = int(m.group(1))
        minor = int(m.group(2) or 0)  # Default minor version to 0 if omitted
        arch = m.group(3)
        return {"version": f"{major!s}.{minor!s}", "arch": arch}

    def _parse_win_platform(self, tag: str):
        tag = tag.lower()
        if tag == "win32":
            return "win32"
        if tag.startswith("win_"):
            arch = tag.split("_", 1)[1]
            if arch == "amd64":
                return "x86_64"
            elif arch == "arm64":
                return "arm64"
        return False

    def _parse_manylinux_platform(self, tag: str):
        if tag.startswith("manylinux_"):
            # PEP 600 perennial tag: manylinux_X_Y_arch
            m = re.match(r"^manylinux_([0-9]+)_([0-9]+)_(.+)$", tag)
            if not m:
                return {}
            glibc_major = int(m.group(1))
            glibc_minor = int(m.group(2))
            arch = m.group(3)
            return {
                "version": f"{glibc_major}.{glibc_minor}",
                "arch": arch,
                "libc": "Glibc",
            }
        elif tag.startswith("manylinux"):
            # Legacies: *1_x86_64, *2010_i686, *2014_x86_64, etc.
            m = re.match(r"^manylinux(\d+)_(.+)$", tag)
            if not m:
                return {}
            identifier = m.group(1)  # e.g. "1", "2010", "2014"
            arch = m.group(2)
            # Map known legacy identifiers to glibc versions (optional)
            version = None
            if identifier == "1":
                version = "2.5"
            elif identifier == "2010":
                version = "2.12"
            elif identifier == "2014":
                version = "2.17"
            else:
                return {}
            return {"version": version, "arch": arch, "libc": "Glibc"}
        else:
            return {}

    def _parse_musllinux_platform(self, tag: str):
        m = re.match(r"^musllinux_([0-9]+)_([0-9]+)_(.+)$", tag)
        if not m:
            return False
        musl_major = int(m.group(1))
        musl_minor = int(m.group(2))
        arch = m.group(3)
        return {
            "version": f"{musl_major}.{musl_minor}",
            "arch": arch,
            "libc": "musl",
        }

    def _build_tree_str(self, obj, indent="", *, is_last=True):
        lines = []

        if isinstance(obj, dict):
            items = list(obj.items())
            for i, (key, value) in enumerate(items):
                is_last = i == len(items) - 1
                branch = "`-- " if is_last else "|-- "
                next_indent = indent + ("    " if is_last else "|   ")
                lines.append(f"{indent}{branch}{key}")
                if not value:
                    lines[-1] += f" {Fore.red}missing{Style.reset}"
                elif isinstance(value, dict):
                    lines.extend(self._build_tree_str(value, next_indent))
                elif isinstance(value, (list, tuple)):
                    lines[-1] += f" {Fore.green}>> {', '.join(value)}{Style.reset}"
        return lines
