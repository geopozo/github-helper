from collections.abc import Iterable

import logistro
from htmy import Component, Renderer, core, html

_logger = logistro.getLogger(__name__)


def modal(
    modal_id: str,
    close_method: str,
    children: core.BaseTag,
) -> Component:
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
            html.div(children),
            class_="w-full max-w-md rounded-lg bg-white p-6 shadow-lg",
        ),
        id=modal_id,
        class_="fixed inset-0 z-50 grid place-content-center bg-black/50 p-4",
        role="dialog",
        style="display: none;",
    )


async def render_page(
    heads: Iterable[core.BaseTag],
    content: Iterable[core.BaseTag],
):
    tailwindcss_cdn = "https://cdn.tailwindcss.com"
    _logger.debug("Rendering.")
    page = (
        html.DOCTYPE.html,
        html.html(
            html.head(html.script(src=tailwindcss_cdn), *heads),
            html.body(*content),
        ),
    )
    return await Renderer().render(page)
