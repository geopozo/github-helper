from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path

import logistro
from htmy import Component, Context, component, html

from github_helper._adapters import to_json
from github_helper._adapters.to_html import _components
from github_helper._utils import load_file

_logger = logistro.getLogger(__name__)

_HTML_DIR = Path(__file__).resolve().parent
_STYLES_PATH = _HTML_DIR / "_styles"


@dataclass(frozen=True, kw_only=True, slots=True)
class RulesetRow:
    ruleset: MutableMapping

    def _error_printer(self, s):
        return html.span(str(type(s).__name__), title=str(s))

    async def htmy(self, context: Context) -> Component:  # noqa: ARG002
        ruleset = self.ruleset
        return html.tr(
            html.td(ruleset["enabled_ruleset"] or ""),
            html.td(ruleset["desired_ruleset"] or ""),
            html.td(
                html.pre(
                    to_json.format_json(
                        ruleset["diff"],
                        pretty=True,
                    ),
                ),
            ),
        )


@component
def rulesets_rows(rulesets, context: Context) -> Component:  # noqa: ARG001
    return [
        RulesetRow(
            ruleset={
                "enabled_ruleset": rulesets["enabled rulesets"][r],
                "desired_ruleset": rulesets["desired rulesets"][r],
                "diff": rulesets["diffs"][r],
            },
        )
        for r in range(len(rulesets["enabled rulesets"]))
    ]


async def rulesets_template(rulesets_data):
    _logger.debug("Building table.")
    styles = [
        html.style(await load_file(_STYLES_PATH / "common.css")),
        html.style(await load_file(_STYLES_PATH / "rulesets.css")),
    ]
    table = html.table(
        html.thead(
            html.tr(
                html.th("Enabled Rulesets", colspan=1),
                html.th("Desired Rulesets", colspan=1),
                html.th("Diffs", colspan=1),
            ),
        ),
        html.tbody(rulesets_rows(rulesets_data)),
        class_="mx-auto",
    )
    _logger.debug("Building page.")
    content = [table]
    return await _components.render_page([*styles], content)
