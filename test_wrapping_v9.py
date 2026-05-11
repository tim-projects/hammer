t = {"id": "86", "p": 2, "summary": "Implement Epic/Feature Branch Workflow very very long", "type": "task", "branch": "86-task-implement-epic-feature-branch-and-more"}
summary_width = 30
branch_width = 25
def simple_wrap(text, width):
    result = []
    while len(text) > width:
        result.append(text[:width])
        text = text[width:]
    result.append(text)
    return result

import textwrap
summary_lines = textwrap.wrap(t["summary"], width=summary_width)
branch_lines = simple_wrap(t["branch"], branch_width)
max_lines = max(len(summary_lines), len(branch_lines))
for i in range(max_lines):
    id_str = str(t.get("id", "")) if i == 0 else ""
    p_str = str(t["p"]) if i == 0 else ""
    s_line = summary_lines[i] if i < len(summary_lines) else ""
    type_str = t["type"] if i == 0 else ""
    b_line = branch_lines[i] if i < len(branch_lines) else ""
    
    # Use f-string alignment correctly for wrapped lines by adding spaces
    # 3 (id) + 1 (space) + 2 (p) + 1 (space) + summary_width + 1 (space) + 6 (type) + 1 (space)
    padding_before_branch = " " * (3 + 1 + 2 + 1 + summary_width + 1 + 6 + 1)
    if i == 0:
        print(f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}")
    else:
        print(f"{'':>3} {'':>2} {s_line:<{summary_width}} {'':<6} {b_line:<{branch_width}}")
