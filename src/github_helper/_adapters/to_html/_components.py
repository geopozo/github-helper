from htmy import Component, core, html


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


# Este componente es experimental
def table(
    data: list,
    *,
    table_id: str = "",
    class_name: str = "",
):
    return html.table(
        *[html.tr(*[html.td(v) for v in row.values()]) for row in data],
        id=table_id,
        class_=class_name,
    )
