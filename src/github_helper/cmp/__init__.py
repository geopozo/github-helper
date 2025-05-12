"""Functions for doing comparisons of objects."""

from typing import Any


async def json_diff(original: Any, target: Any, algo="jsondiff"):
    """Conduct a tree diff using selected algorithm."""
    match algo:
        case "jsondiff":
            import jsondiff

            return jsondiff.diff(original, target, marshal=True)
        case _:
            raise NotImplementedError(f"{algo} is not implemented.")
