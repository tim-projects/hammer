COLORS = {
    "HEADER": "\033[1;37m",  # White bold
    "PROGRESSING": "\033[1;32m",  # Green
    "READY": "\033[1;33m",  # Yellow
    "TESTING": "\033[1;35m",  # Magenta
    "REVIEW": "\033[1;34m",  # Blue
    "STAGING": "\033[1;36m",  # Cyan
    "DONE": "\033[0;32m",  # Green
    "ARCHIVED": "\033[0;37m",  # Grey
    "RESET": "\033[0m",
    "LINE": "\033[38;5;238m",  # Darker grey
}

PRIO_COLORS = {
    "1": "\033[1;31m",  # Red bold
    "2": "\033[31m",  # Red
    "3": "\033[33m",  # Yellow
    "9": "\033[37m",  # Grey
}


def format_table(headers, rows, status_idx=None, prio_idx=None):
    if not rows:
        return "No data."

    # Calculate column widths
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))

    L = COLORS["LINE"]
    R = COLORS["RESET"]

    # Header
    output = []

    # Helper for borders
    def b(left_border, m, r, sep="─┬─"):
        return f"{L}{left_border}{sep.join('─' * (w + 2) for w in widths)}{r}{R}"

    output.append(b("┌", "┬", "┐"))

    header_line = (
        f"{L}│{R} "
        + f" {L}│{R} ".join(
            f"{COLORS['HEADER']}{h:<{widths[i]}}{R}" for i, h in enumerate(headers)
        )
        + f" {L}│{R}"
    )
    output.append(header_line)
    output.append(b("├", "┼", "┤"))

    # Rows
    for row in rows:
        formatted_row = []
        for i, cell in enumerate(row):
            cell_str = str(cell)
            color = ""
            reset = ""

            # Status color
            if status_idx is not None and i == status_idx:
                color = COLORS.get(cell_str, "")
                reset = COLORS["RESET"] if color else ""
            # Priority color
            elif prio_idx is not None and i == prio_idx:
                color = PRIO_COLORS.get(cell_str, "")
                reset = COLORS["RESET"] if color else ""

            formatted_row.append(f"{color}{cell_str:<{widths[i]}}{reset}")

        row_str = f"{L}│{R} " + f" {L}│{R} ".join(formatted_row) + f" {L}│{R}"
        output.append(row_str)

    output.append(b("└", "┴", "┘"))
    return "\n".join(output)
