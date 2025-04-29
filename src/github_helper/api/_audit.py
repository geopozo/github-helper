import fnmatch
from pathlib import Path

import jsondiff as jd  # type: ignore[import-untyped]

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


def remove_excluded_keys(ruleset, excluded_keys):
    for key in excluded_keys:
        if key in ruleset:
            ruleset.pop(key)


async def json_diff(original, target, diffs):
    json_diffs = jd.diff(original, target, marshal=True)
    if not json_diffs:
        return []
    else:
        for diff_key in json_diffs:
            if diff_key == "$delete":
                for i in json_diffs[diff_key]:
                    diffs.append({"status": f"add'l. key: {i}"})
            else:
                diffs.append({"status": diff_key})
    return diffs
