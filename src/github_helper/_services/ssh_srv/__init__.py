"""A service to warn user if they need to start an ssh session."""

import os
import platform
import subprocess
from pathlib import Path

import logistro

_logger = logistro.getLogger(__name__)

_extra_args = {}
if platform.system() == "Windows":
    _logger.debug("Is windows.")
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    creationflags = subprocess.CREATE_NO_WINDOW
    extra_args = {"startupinfo": startupinfo, "creationflags": creationflags}


class NoSSHKeyError(RuntimeError):
    """Return this error if the user has no SSH key."""


class SSHKeyPasswordError(RuntimeError):
    """Error to be returned if user needs to enter ssh password."""

    def __init__(self, msg=None):
        """Create an SSHKey error with default or custom message."""
        default_message = (
            "It looks like you have your secret key encrypted with a "
            "password. You should run the command `ssh-agent -s` so that "
            "you only have to enter your password once this terminal session."
            " gh-helper will not run without out this."
        )
        super().__init__(msg or default_message)


def _ssh(key):
    return Path.home() / ".ssh" / key


_accepted_algos = [
    "id_ed25519",
    "id_ecdsa",
    "id_rsa",
    "id_dsa",
    "id_xmss",
]

_possible_keys = [_ssh(key) for key in _accepted_algos]


def _find_key():
    for key in _possible_keys:
        if key.exists():
            return key
    raise NoSSHKeyError("Could not find a valid SSH Key for using git.")


def _is_key_encrypted():
    _logger.debug("Checking for password.")
    # ssh-keygen -yf returns public key; fails if passphrase is required and not cached
    try:
        _ = subprocess.run(  # noqa: S603 We trust this input
            ["ssh-keygen", "-yf", str(_find_key())],  # noqa: S607 partial path
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            env={
                **os.environ,
                "DISPLAY": "",
                "SSH_ASKPASS": "false",
            },  # disable askpass fallback
            stdin=subprocess.DEVNULL,
            **extra_args,
        )
    except subprocess.CalledProcessError:
        return True  # key requires passphrase
    else:
        return False  # no passphrase needed


def _is_key_loaded_in_agent():
    _logger.debug("Checking for agent.")
    try:
        result = subprocess.run(  # noqa: S603 We trust this input
            ["ssh-add", "-l"],  # noqa: S607 partial path
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        return False
    else:
        return result.returncode == 0 and b"No identities" not in result.stdout


def check_ssh_ready():
    """Will run various checks to see if we can use our services."""
    _logger.debug("Checking ssh.")
    # why not check gh auth as well?
    if not _is_key_encrypted():
        return

    if _is_key_loaded_in_agent():
        return

    raise SSHKeyPasswordError
