from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path

import logistro
from htmy import Component, Context, component, html

from github_helper._adapters.to_html import _components
from github_helper._utils import load_file

_logger = logistro.getLogger(__name__)

github_com = r"https://www.github.com"
_HTML_DIR = Path(__file__).resolve().parent
_STYLES_PATH = _HTML_DIR / "_styles"
_JS_PATH = _HTML_DIR / "_js"


@dataclass(frozen=True, kw_only=True, slots=True)
class RepoRow:
    repo: MutableMapping

    def _error_printer(self, s):
        return html.span(str(type(s).__name__), title=str(s))

    async def htmy(self, context: Context) -> Component:  # noqa: ARG002
        repo = self.repo
        permission_msg = {
            0: "Can read and clone this repository.",
            1: "Can pull and also manage issues and pull requests.",
            2: "Can read, clone, and push to this repository",
            3: "Can also manage issues, pull requests, and some repository settings.",
            4: "Full access to the repository, including settings and collaborators.",
        }

        _logger.debug(f"Building html row for {repo['name']}")
        return html.tr(
            html.td(html.span("📌" if repo["pinned"] else "")),
            html.td(
                html.a(
                    repo["owner"],
                    href=f"{github_com}/{repo['owner']}",
                    target="_blank",
                ),
                class_="owner",
            ),
            html.td(html.span("/")),
            html.td(
                html.a(
                    repo["name"],
                    href=f"{github_com}/{repo['owner']}/{repo['name']}",
                    target="_blank",
                ),
                class_="repo",
            ),
            html.td(html.span(repo["version"]), class_="text-center"),
            html.td(html.span("⑂" if repo["fork"] else "")),
            html.td(
                html.span(repo["description"] or ""),
                class_="description",
            ),
            html.td(
                html.a(
                    "🔧",
                    href=f"{github_com}/{repo['owner']}/{repo['name']}/settings/access",
                    target="_blank",
                ),
                *[
                    self._error_printer(s)
                    if isinstance(s, Exception)
                    else html.a(
                        s["user"],
                        html.sup(
                            str(s["permission"]),
                            class_="badge",
                        ),
                        href=f"{github_com}/{s['user']}",
                        class_="collaborator",
                        target="_blank",
                        title=permission_msg[s["permission"]],
                    )
                    if isinstance(s, dict)
                    else s
                    for s in (
                        sorted(
                            repo["collaborators"],
                            key=lambda d: d["permission"],
                            reverse=True,
                        )
                        if repo["collaborators"]
                        and isinstance(repo["collaborators"][0], dict)
                        else repo["collaborators"]
                    )
                ],
                class_="collaborators",
            ),
            html.td(
                html.a(
                    "🔧",
                    href=f"{github_com}/{repo['owner']}/{repo['name']}",
                    target="_blank",
                ),
                *[html.span(s, class_=f"topic {s}") for s in repo["topics"]],
                class_="topics",
            ),
            class_=(
                "repo-row "
                f"{repo['visibility']} "
                f"{'archived' if repo['archived'] else ''}"
            ),
        )


@component
def repo_rows(repos, context: Context) -> Component:  # noqa: ARG001
    return [RepoRow(repo=repo) for repo in repos]


async def repos(repos_data):
    _logger.debug("Building table.")
    styles = html.style(await load_file(_STYLES_PATH / "repos.css"))
    table = html.table(
        html.thead(
            html.tr(
                html.th("Repository", colspan=4),
                html.th("Head Tag", colspan=2),
                html.th("Description", colspan=1),
                html.th("Collaborators", colspan=1),
                html.th("Topics", colspan=1),
            ),
        ),
        html.tbody(repo_rows(repos_data)),
        class_="mx-auto",
    )
    modal_iframe = _components.modal(
        "my-modal",
        "closeModal()",
        html.iframe(src="", height="500", class_="w-full"),
    )
    _logger.debug("Building page.")
    scripts = [
        html.script(
            html.SafeStr(
                "\n".join(
                    [
                        await load_file(_JS_PATH / "repos.js"),
                        await load_file(_JS_PATH / "modal.js"),
                    ],
                ),
            ),
        ),
    ]
    content = [
        html.div(
            html.label(
                html.input_(
                    type_="checkbox",
                    id_="toggle-public",
                    checked=True,
                ),
                " Show Public",
            ),
            html.label(
                html.input_(
                    type_="checkbox",
                    id_="toggle-private",
                    checked=True,
                    style="margin-left:1rem;",
                ),
                " Show Private",
            ),
            html.label(
                html.input_(
                    type_="checkbox",
                    id_="toggle-archive",
                    checked=True,
                    style="margin-left:1rem;",
                ),
                " Show Archived",
            ),
            html.br(),
            html.label(
                " Owner",
                html.input_(
                    type_="text",
                    id_="owner-filter",
                    name="owner-filter",
                    placeholder="Owner",
                    class_="rounded shadow-sm sm:text-sm p-1",
                ),
            ),
            html.label(
                " Repo",
                html.input_(
                    type_="text",
                    id_="repo-filter",
                    name="repo-filter",
                    placeholder="Repo",
                    class_="rounded shadow-sm sm:text-sm p-1",
                ),
            ),
            style="margin-bottom: 1rem;",
            class_="mx-auto",
            id_="controls",
        ),
        table,
        modal_iframe,
        *scripts,
    ]
    return await _components.render_page([styles], content)
