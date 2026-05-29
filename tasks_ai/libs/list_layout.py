import shutil
import textwrap

C_HEADER = "\033[1;47;30m"
C_ID = "\033[1;32m"
C_PRIO = "\033[1;35m"
C_TYPE = "\033[36m"
C_RESET = "\033[0m"


def render_table(all_data):
    term_width = shutil.get_terminal_size(fallback=(180, 24)).columns
    fixed_cols = 3 + 1 + 2 + 1 + 7 + 1 + 6 + 1 + 30
    summary_min = 30
    available = max(term_width - fixed_cols, 10)
    branch_width = 30
    summary_width = max(summary_min, available)

    print(
        f"{C_HEADER}{'#':>3} {'P':>2} {'Summary':<{summary_width}} {'Status':<7} {'Type':<6} {'Branch':<{branch_width}}{C_RESET}"
    )

    for state, tasks in all_data.items():
        for t in tasks:
            summary_lines = textwrap.wrap(t["summary"], width=summary_width) or [""]

            def simple_wrap(text, width):
                res = []
                while len(text) > width:
                    res.append(text[:width])
                    text = text[width:]
                res.append(text)
                return res

            branch_lines = simple_wrap(t["branch"], branch_width) or [""]
            max_lines = max(len(summary_lines), len(branch_lines))

            for i in range(max_lines):
                id_str = str(t["id"]) if i == 0 else ""
                p_str = str(t["p"]) if i == 0 else ""
                s_line = summary_lines[i] if i < len(summary_lines) else ""
                status_str = t["state"] if i == 0 else ""
                type_str = t["type"] if i == 0 else ""
                b_line = branch_lines[i] if i < len(branch_lines) else ""

                id_f = f"{C_ID}{id_str:>3}{C_RESET}" if i == 0 else "   "
                p_f = f"{C_PRIO}{p_str:>2}{C_RESET}" if i == 0 else "  "
                status_f = f"{C_TYPE}{status_str:<7}{C_RESET}" if i == 0 else "       "
                type_f = f"{C_TYPE}{type_str:<6}{C_RESET}" if i == 0 else "      "

                print(
                    f"{id_f} {p_f} {s_line:<{summary_width}} {status_f} {type_f} {b_line:<{branch_width}}"
                )
