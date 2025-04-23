from collections.abc import MutableMapping
from dataclasses import dataclass

import logistro
from htmy import Component, Context, Renderer, component, html

_logger = logistro.getLogger(__name__)

github_com = r"https://www.github.com"
style = """

a.collaborator:link,
a.collaborator:hover,
a.collaborator:visited,
a.collaborator:focus,
a.collaborator:active,
span.topic
{
  border: 1px solid black;
  padding: 0rem .5rem;
  border-radius: 10px;
  margin: 0 .1rem;
}
td.owner {
  text-align: right;
}
td.repo {
  max-width: 15rem;
}
td.description {
  max-width: 50rem;
}
tr.repo-row td a:link,
tr.repo-row td a:hover,
tr.repo-row td a:visited,
tr.repo-row td a:focus,
tr.repo-row td a:active {
  color: black;
}
body {
  overflow-x: auto;
  width: 100%;
}
table {
  width: max-content;
}

tr.even { background-color: #f0f0f0; }
tr.odd { background-color: #ffffff; }

tr.repo-row.private {
    font-weight: 350;
}

tr.repo-row.public {
    font-weight: 500;
}

tr.repo-row.archived td{
   background-color: rgba(255, 0, 0, 0.04);
}

#controls {
    width:max-content;
}
"""


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


async def repos(repos_data):
    _logger.debug("Building table.")
    table = html.table(repo_rows(repos_data), class_="mx-auto")
    _logger.debug("Building page.")
    scripts = [
        html.script(src="https://cdn.tailwindcss.com"),
        html.script(
            html.SafeStr("""
    function updateVisibleRowClasses() {
        const rows = [...document.querySelectorAll('table tbody tr')];
        let visibleIndex = 0;

        rows.forEach(row => {
          row.classList.remove('odd', 'even');

          if (row.style.display !== 'none') {
            row.classList.add(visibleIndex % 2 === 0 ? 'even' : 'odd');
            visibleIndex++;
          }
    });
  }"""),
        ),
        html.script(
            html.SafeStr(r"""
  const publicCheckbox = document.getElementById('toggle-public');
  const privateCheckbox = document.getElementById('toggle-private');
  const archivedCheckbox = document.getElementById('toggle-archive');
  const ownerInput = document.getElementById('owner-filter');
  const repoInput = document.getElementById('repo-filter');
  function filterAll() {
    console.log("Filtering All.")
    const ownerFilter = ownerInput.value.toLowerCase();
    const repoFilter = repoInput.value.toLowerCase();
    const rows = document.querySelectorAll('table tbody tr');

    rows.forEach(row => {
      const matchOwner = [...row.querySelectorAll('td.owner')].some(td =>
        td.textContent.toLowerCase().includes(ownerFilter)
      );
      const matchRepo = [...row.querySelectorAll('td.repo')].some(td =>
        td.textContent.toLowerCase().includes(repoFilter)
      );
      archived = !(!archivedCheckbox.checked && row.classList.contains('archived'))
      private  = !(!privateCheckbox.checked && row.classList.contains('private'))
      public   = !(!publicCheckbox.checked && row.classList.contains('public'))

      toDisplay = matchOwner && matchRepo && archived && private && public
      row.style.display = toDisplay ? '' : 'none';
    });
    updateVisibleRowClasses();
  }
  publicCheckbox.addEventListener('change', filterAll);
  privateCheckbox.addEventListener('change', filterAll);
  archivedCheckbox.addEventListener('change', filterAll);
  ownerInput.addEventListener('input', filterAll);
  repoInput.addEventListener('input', filterAll);
  filterAll();
  """),
        ),
    ]
    page = (
        html.DOCTYPE.html,
        html.html(
            html.head(
                html.style(style),
            ),
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
                *scripts,
            ),
        ),
    )
    _logger.debug("Rendering.")
    return await Renderer().render(page)
