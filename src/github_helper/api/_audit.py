import fnmatch
from pathlib import Path

from github_helper._services.gh import GHError
from github_helper._utils import load_json

_SCRIPT_DIR = Path(__file__).resolve().parent
_TEMPLATE_PATH = _SCRIPT_DIR / "templates"


def get_required_rulesets(configs, repo_full_name):
    rulesets_files = set()

    required = {"repo"}
    valid = required | {"include", "exclude"}

    for cfg in configs:
        missing, invalid = (required - cfg.keys(), cfg.keys() - valid)
        if missing or invalid:
            raise ValueError(
                f"Ruleset json not structured properly. Missing keys: {missing}."
                if missing
                else f" Invalid keys: {invalid}."
                if invalid
                else "",
            )

        if "include" in cfg:
            if not isinstance(cfg["include"], list):
                raise TypeError("'include' must be a list")
            if fnmatch.fnmatch(repo_full_name, cfg["repo"]):
                rulesets_files = rulesets_files | set(cfg["include"])
        if "exclude" in cfg:
            if not isinstance(cfg["exclude"], list):
                raise TypeError("'exclude' must be a list")
            if fnmatch.fnmatch(repo_full_name, cfg["repo"]):
                rulesets_files = rulesets_files - set(cfg["exclude"])
    return rulesets_files


async def load_template_ruleset(path):
    if Path(path).is_file():
        return await load_json(path=path)

    if Path(path).is_dir():
        raise GHError("File name required")

    template_path = _TEMPLATE_PATH / path
    return await load_json(path=template_path)


def remove_keys(d, dotted_keys):
    for dotted_key in dotted_keys:
        keys = dotted_key.split(".")
        for key in keys[:-1]:
            d = d.get(key, {})
        d.pop(keys[-1], None)
