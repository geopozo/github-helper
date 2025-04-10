from collections.abc import MutableMapping
from dataclasses import dataclass

import logistro
from htmy import Component, Context, Renderer, component, html

_logger = logistro.getLogger(__name__)

github_com = r"https://www.github.com"
style = """
span.topic {
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
    font-weight: 250;
}

tr.repo-row.private {
    font-weight: 550;
}

tr.repo-row.archived td{
   background-color: rgba(255, 0, 0, 0.04);
}

"""


@dataclass(frozen=True, kw_only=True, slots=True)
class RepoRow:
    repo: MutableMapping

    async def htmy(self, context: Context) -> Component:  # noqa: ARG002
        repo = self.repo
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
                    html.a(s, href=f"{github_com}/{s}") if s != "(404)" else s
                    for s in repo["collaborators"]
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
    table = html.table(repo_rows(repos_data))
    _logger.debug("Building page.")
    scripts = [
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
            html.SafeStr("""
  const publicCheckbox = document.getElementById('toggle-public');
  const privateCheckbox = document.getElementById('toggle-private');
  const archivedCheckbox = document.getElementById('toggle-archive');

  function toggleRows() {
    document.querySelectorAll('tr.public').forEach(row => {
      row.style.display = publicCheckbox.checked ? '' : 'none';
      updateVisibleRowClasses()
    });
    document.querySelectorAll('tr.private').forEach(row => {
      row.style.display = privateCheckbox.checked ? '' : 'none';
      updateVisibleRowClasses()
    });
    document.querySelectorAll('tr.archived').forEach(row => {
      row.style.display = archivedCheckbox.checked ? '' : 'none';
      updateVisibleRowClasses()
    });
  }

  publicCheckbox.addEventListener('change', toggleRows);
  privateCheckbox.addEventListener('change', toggleRows);
  archivedCheckbox.addEventListener('change', toggleRows);
  toggleRows();
"""),
        ),
        html.script(
            html.SafeStr("""
 const input = document.getElementById('owner-filter');

  input.addEventListener('input', () => {
    const filter = input.value.toLowerCase();
    const rows = document.querySelectorAll('table tbody tr');

    rows.forEach(row => {
      const match = [...row.querySelectorAll('td.owner')].some(td =>
        td.textContent.toLowerCase().includes(filter)
      );
      row.style.display = match ? '' : 'none';
    });
    updateVisibleRowClasses()
  });
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
                        html.input_(
                            type_="text",
                            id_="owner-filter",
                            name="owner-filter",
                            placeholder="Owner",
                        ),
                        "Owner",
                    ),
                    style="margin-bottom: 1rem;",
                ),
                table,
                *scripts,
            ),
        ),
    )
    _logger.debug("Rendering.")
    return await Renderer().render(page)
