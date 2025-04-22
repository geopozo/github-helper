from tabulate import tabulate


def format_table(data, *, pretty=False, headers="keys", colalign=None):
    return tabulate(
        data,
        headers=headers if pretty else "",
        colalign=colalign,
        tablefmt="psql" if pretty else "plain",
    )
