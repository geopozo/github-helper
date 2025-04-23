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
from dataclasses import field

import colored
import logistro
import semver
from packaging import utils, version

_logger = logistro.getLogger(__name__)

if not sys.stdout.isatty():

    class NoColor:
        def __getattr__(self, name):
            return ""

    # Override colored's foreground, background, and style
    colored.Fore = colored.Back = colored.Style = NoColor()


def order_versions(versions: list[dict], key: str):
    if not versions:
        return versions
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
            ret += f"{colored.Fore.red}PRERELEASE DISAGREEMENT{colored.Style.reset}\n"
        if not self.projects:
            ret += f"{colored.Fore.red}No Valid Projects Found.{colored.Style.reset}\n"
        else:
            for k, v in self.projects.items():
                if k.startswith("python/"):
                    ## look at bdist/sdist
                    warn = ""
                    if not v["bdist"]:
                        warn = "bdist"
                    if not v["sdist"]:
                        warn = ", sdist" if warn else "sdist"
                    warn = (
                        f", {colored.Fore.red}missing {warn}{colored.Style.reset}"
                        if warn
                        else ""
                    )

                    pure = ""
                    if v["pure"]:
                        pure = (
                            f", {colored.Fore.green}pure: {', '.join(v['pure'])}"
                            f"{colored.Style.reset}"
                        )

                    ret += f"{colored.Style.bold}{k}{colored.Style.reset}{warn}{pure}\n"

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
                f"{colored.Fore.yellow}{colored.Style.bold}"
                f"{len(self.unknown_files)} Unknown Files:"
                f"{colored.Style.reset}\n"
            )
            for i, f in enumerate(self.unknown_files):
                if i > 3:  # noqa: PLR2004
                    ret += f" {colored.Fore.yellow}...{colored.Style.reset}\n"
                    break
                ret += f" {colored.Fore.yellow}{f}{colored.Style.reset}\n"
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
            }
        ref = self.projects[name]
        if notes.get("type") == "sdist":
            ref["sdist"] = True
        elif notes.get("type") == "bdist":
            ref["bdist"] = True
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
                    lines[-1] += f" {colored.Fore.red}missing{colored.Style.reset}"
                elif isinstance(value, dict):
                    lines.extend(self._build_tree_str(value, next_indent))
                elif isinstance(value, (list, tuple)):
                    lines[-1] += (
                        f" {colored.Fore.green}>> "
                        f"{', '.join(value)}{colored.Style.reset}"
                    )
        return lines
