from collections.abc import MutableMapping
from dataclasses import dataclass

import logistro
from htmy import Component, Context, Renderer, component, html

_logger = logistro.getLogger(__name__)

github_com = r"https://www.github.com"


@dataclass(frozen=True, kw_only=True, slots=True)
class RepoRow:
    repo: MutableMapping

    async def htmy(self, context: Context) -> Component:  # noqa: ARG002
        repo = self.repo
        _logger.debug(f"Building html row for {repo['name']}")
        return html.tr(
            html.td(
                *[
                    html.a(repo["owner"], href=f"{github_com}/{repo['owner']}"),
                    html.span("/"),
                    html.a(
                        repo["name"],
                        href=f"{github_com}/{repo['owner']}/{repo['name']}",
                    ),
                ],
            ),
        )


@component
def repo_rows(repos, context: Context) -> Component:  # noqa: ARG001
    return [RepoRow(repo=repo) for repo in repos]


async def repos(repos_data):
    _logger.debug("Building table.")
    table = html.table(repo_rows(repos_data))
    _logger.debug("Building page.")
    page = (
        html.DOCTYPE.html,
        html.html(
            html.body(
                table,
            ),
        ),
    )
    _logger.debug("Rendering.")
    return await Renderer().render(page)
