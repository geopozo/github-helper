"""A service to warn user if they need to start an ssh session."""

import os
import platform
import re
import subprocess
import sys
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


def _start_ssh_agent_and_add_key():
    _logger.debug("Trying to start agent and add keys.")
    # 1) Launch ssh-agent
    out = subprocess.check_output("ssh-agent -s", shell=True, text=True)
    # ssh-agent -s prints lines like:
    #    SSH_AUTH_SOCK=/tmp/ssh-XXXXXXXXXXXXXXXXXX/agent.PID; export SSH_AUTH_SOCK;
    #    SSH_AGENT_PID=12345; export SSH_AGENT_PID;
    for line in out.splitlines():
        m = re.match(r"^(SSH_AUTH_SOCK|SSH_AGENT_PID)=([^;]+);", line)
        if m:
            os.environ[m.group(1)] = m.group(2)

    # 2) Add your key (this will ask for the passphrase once)
    try:
        _logger.debug(f"Trying to add key {_find_key()}.")
        subprocess.run(
            ["ssh-add", str(_find_key())],
            check=True,
        )
    except BaseException as e:
        raise RuntimeError(
            "Tried to add your ssh key to our agent. But that failed. "
            "You can run `eval (ssh-agent -s)` and `ssh-add PATH_TO_KEY` "
            "manually if you need to.",
        ) from e


def _ensure_ssh_agent():
    _logger.debug("Looking for keys in ssh_add.")
    # If agent already has your key, do nothing
    try:
        r = subprocess.run(
            ["ssh-add", "-l"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            env=os.environ,
        )
        out = r.stdout.decode().lower()
        if r.returncode == 0 and "no identities" not in out:
            return
    except FileNotFoundError:
        # ssh-add not found; bail out
        sys.stderr.write("✖ ssh-add not found in PATH, it's needed.\n")
        sys.exit(1)

    # Otherwise, start a fresh agent and add the key
    _start_ssh_agent_and_add_key()


def check_ssh_ready():
    """Will run various checks to see if we can use our services."""
    # why not check gh auth as well?
    _ensure_ssh_agent()
