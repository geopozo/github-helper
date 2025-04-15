import base64

import jq  # type: ignore [import-not-found]
import logistro
import orjson

from github_helper import _gh_service as srv

_logger = logistro.getLogger(__name__)


async def get_file(owner, repo, path, ref=None):
    """Return orgs for a user."""
    _logger.warning(
        "This function has only been tested for textish files, not binary.",
    )
    files_jq = jq.compile(".content")
    endpoint = f"/repos/{owner}/{repo}/contents/{path}"
    if ref:
        endpoint += f"?ref={ref}"
    _logger.debug(f"Calling API: {endpoint}")
    retval, out, err = await srv.gh_api(endpoint)
    srv.check_retval(retval, err, endpoint=endpoint)
    file = files_jq.input_value(orjson.loads(out)).first()
    return base64.b64decode(file)
