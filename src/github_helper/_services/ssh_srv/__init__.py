"""A service to warn user if they need to start an ssh session."""

import os
import re
import subprocess
from pathlib import Path

import logistro

_logger = logistro.getLogger(__name__)


class NoSSHKeyError(RuntimeError):
    """Return this error if the user has no SSH key."""


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
    out = subprocess.check_output(  # noqa: S602
        "ssh-agent -s -t 5m",  # noqa: S607
        shell=True,
        text=True,
    )
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
        subprocess.run(  # noqa: S603
            ["ssh-add", str(_find_key())],  # noqa: S607
            check=True,
        )
    except BaseException as e:
        raise RuntimeError(
            "Tried to add your ssh key to our agent. But that failed. "
            "You can run `eval $(ssh-agent -s)` and `ssh-add PATH_TO_KEY` "
            "manually if you need to.",
        ) from e


def _ensure_ssh_agent():
    _logger.debug("Looking for keys in ssh_add.")
    # If agent already has your key, do nothing
    try:
        r = subprocess.run(  # noqa: S603
            ["ssh-add", "-l"],  # noqa: S607
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            env=os.environ,
        )
        if r.returncode == 0:
            return
    except FileNotFoundError:
        # ssh-add not found; bail out
        _logger.exception("✖ ssh-add not found in PATH, it's needed.\n")
        raise

    # Otherwise, start a fresh agent and add the key
    _start_ssh_agent_and_add_key()


def check_ssh_ready():
    """Will run various checks to see if we can use our services."""
    # why not check gh auth as well?
    _ensure_ssh_agent()
