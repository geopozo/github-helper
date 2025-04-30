"""Tools for auditing packages."""

import logistro

from github_helper.api.versions import Version

from ._py_audit import PythonAudit
from ._types import ReturnMessages

_logger = logistro.getLogger(__name__)


class ReleaseAudit:
    """
    Release audit turns a release object into a summary.

    The release audit goes through an audit, file by file,
    and tries to sort them as well as looking to see if sub-processors
    understand them.
    """

    prerelease_agree: bool
    """Does the version agree with the mark about prerelease."""
    unknown_files: set
    """Files that couldn't be understood trying to calculate notes."""
    ignored_files: dict[str, int]

    projects: dict
    """A list of the projects found in this release."""

    def status(self):
        ret = ""
        if not self.prerelease_agree:
            ret += "Prerelease Disagreement.\n"
        if self.unknown_files:
            ret += "Unknown Files: \n "
            ret += "\n".join(self.unknown_files)
            ret += "\n"
        if self.ignored_files:
            ret += "Ignored Files:\n"
            for k, v in self.ignored_files.items():
                ret += f" {k}: {v!s}\n"
        return ret

    def __init__(self, release):
        """Audit a release object."""
        self.tag = release.tag
        self.unknown_files = set()
        self.ignored_files = {}
        self.version = Version(self.tag)
        self.python_audit = PythonAudit(self.version)

        if not self.version.valid:  # we should not audit not valid
            self.prerelease_agree = None
            return

        self.prerelease_agree = self.version.is_prerelease == release.prerelease

        for filename in release.files:
            notes = self.process_file(filename)

            match notes.get("action"):
                case "ignore":
                    why = notes.get("type", "other")
                    self.ignored_files[why] = self.ignored_files.get(why, 0) + 1
                case "resolved":
                    pass
                case _:
                    self.unknown_files.add(filename)

    # the action you return will trigger behavior above
    def process_file(self, filename: str) -> ReturnMessages:
        if filename in (f"{self.tag}.zip", f"{self.tag}.tar.gz"):
            return {"type": "gh-archive", "action": "ignore"}
        elif filename.endswith(("sigstore.json", ".sha256")):
            return {"type": "metadata", "action": "ignore"}
        elif note := self.python_audit.check_file(filename):
            return note
        return {"error": "unrecognized name", "value": filename}
