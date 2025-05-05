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


# experimental component
def select_filter(title: str, options: list) -> Component:
    return html.div(
        html.details(
            html.summary(
                html.span(title, class_="text-sm font-medium"),
                html.span("🔽", class_="transition-transform group-open:-rotate-180"),
                class_=(
                    "flex items-center gap-2 border-b border-gray-300 "
                    "pb-1 text-gray-700 transition-colors hover:border-gray-400 "
                    "hover:text-gray-900 [&::-webkit-details-marker]:hidden "
                    "cursor-pointer"
                ),
            ),
            html.div(
                html.div(
                    html.button(
                        "Reset",
                        type_="button",
                        class_=(
                            "text-sm text-gray-700 underline "
                            "transition-colors hover:text-gray-900"
                        ),
                    ),
                    class_="flex items-center justify-between px-3 py-2",
                ),
                html.fieldset(
                    html.legend("Checkboxes", class_="sr-only"),
                    html.div(
                        *[
                            html.label(
                                html.input_(
                                    type_="checkbox",
                                    class_="size-5 rounded border-gray-300 shadow-sm",
                                ),
                                html.span(
                                    o.label,
                                    class_="text-sm font-medium text-gray-700",
                                ),
                                for_="Option1",
                                class_="inline-flex items-center gap-3",
                            )
                            for o in options
                        ],
                        class_="flex flex-col items-start gap-3",
                    ),
                    class_="p-3",
                ),
                class_=(
                    "z-auto w-64 divide-y divide-gray-300 "
                    "rounded border border-gray-300 "
                    "bg-white shadow-sm group-open:absolute "
                    "group-open:start-0 group-open:top-8"
                ),
            ),
            class_="group relative",
        ),
        class_="flex gap-4 sm:gap-6",
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
