from pathlib import Path

import logistro
from htmy import html

from github_helper._adapters.to_html import _components
from github_helper._utils import load_file

_logger = logistro.getLogger(__name__)

_HTML_DIR = Path(__file__).resolve().parent
_STYLES_PATH = _HTML_DIR / "_styles"


async def rulesets_template():
    _logger.debug("Building table.")
    styles = html.style(await load_file(_STYLES_PATH / "rulesets.css"))
    _logger.debug("Building page.")
    content = []
    return await _components.render_page([styles], content)
