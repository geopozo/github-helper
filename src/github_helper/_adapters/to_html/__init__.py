from collections.abc import MutableMapping
from dataclasses import dataclass
from pathlib import Path

import logistro
from htmy import Component, Context, Renderer, component, html

from github_helper._utils import load_file

_logger = logistro.getLogger(__name__)

github_com = r"https://www.github.com"
_HTML_DIR = Path(__file__).resolve().parent
_STYLES_PATH = _HTML_DIR / "styles"
_JS_PATH = _HTML_DIR / "js"


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
                html.a(repo["owner"], href=f"{github_com}/{repo['owner']}"),
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
            html.td(html.span(repo["version"])),
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


def modal(modal_id: str, close_method: str) -> Component:
    return html.div(
        html.div(
            html.div(
                html.button(
                    "X",
                    type="button",
                    class_="-me-4 -mt-4 p-2 text-gray-500",
                    onclick=close_method,
                ),
                class_="flex items-start justify-end",
            ),
            html.div(html.iframe(src="", height="500", class_="w-full")),
            class_="w-full max-w-md rounded-lg bg-white p-6 shadow-lg",
        ),
        id=modal_id,
        class_="fixed inset-0 z-50 grid place-content-center bg-black/50 p-4",
        role="dialog",
        style="display: none;",
    )


async def repos(repos_data):
    _logger.debug("Building table.")
    style = html.style(await load_file(_STYLES_PATH / "repos.css"))
    table = html.table(repo_rows(repos_data), class_="mx-auto")
    modal_iframe = modal("my-modal", "closeModal()")
    _logger.debug("Building page.")
    scripts = [
        html.script(src="https://cdn.tailwindcss.com"),
        html.script(html.SafeStr(html.SafeStr(await load_file(_JS_PATH / "repos.js")))),
    ]
    page = (
        html.DOCTYPE.html,
        html.html(
            html.head(style),
            html.body(
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
            ),
        ),
    )
    _logger.debug("Rendering.")
    return await Renderer().render(page)
