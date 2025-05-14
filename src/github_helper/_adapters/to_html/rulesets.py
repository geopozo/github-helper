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
_HLJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.11.1"


@dataclass(frozen=True, kw_only=True, slots=True)
class RulesetRow:
    ruleset: MutableMapping

    def _error_printer(self, s):
        return html.span(str(type(s).__name__), title=str(s))

    async def htmy(self, context: Context) -> Component:  # noqa: ARG002
        ruleset = self.ruleset
        return html.tr(
            html.td(ruleset["enabled_ruleset"] or "", class_="table-col"),
            html.td(ruleset["desired_ruleset"] or "", class_="table-col"),
            html.td(
                html.pre(
                    html.code(
                        to_json.format_json(
                            ruleset["diff"],
                            pretty=True,
                        ),
                        class_="language-json rounded-md",
                    ),
                )
                if isinstance(ruleset["diff"], dict)
                else ruleset["diff"],
                class_="table-col",
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
        html.style(
            await load_file(_STYLES_PATH / "common.css"),
            type="text/tailwindcss",
        ),
        html.link(
            href=f"{_HLJS_URL}/styles/default.min.css",
            rel="stylesheet",
        ),
    ]
    table = html.table(
        html.thead(
            html.tr(
                html.th("Enabled Rulesets", class_="table-header"),
                html.th("Desired Rulesets", class_="table-header"),
                html.th("Diffs", class_="table-header"),
            ),
        ),
        html.tbody(rulesets_rows(rulesets_data)),
        class_="table table-auto w-11/12",
    )
    scripts = [
        html.script(src=f"{_HLJS_URL}/highlight.min.js"),
        html.script(html.SafeStr("hljs.highlightAll();")),
    ]
    _logger.debug("Building page.")
    content = [table, *scripts]
    return await _components.render_page([*styles], content)
