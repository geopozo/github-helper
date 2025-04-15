from tabulate import tabulate


def format_table(data, *, pretty=False, headers="keys"):
    return tabulate(
        data,
        headers=headers if pretty else "",
        tablefmt="psql" if pretty else "plain",
    )
