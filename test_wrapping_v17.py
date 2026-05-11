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
    
    # Correct alignment by using fixed spaces for the columns instead of relying on f-string for wrapped lines
    # The columns are 3, 2, summary_width, 6, branch_width
    # Separators are single spaces
    
    id_part = f"{id_str:>3}"
    p_part = f"{p_str:>2}"
    s_part = f"{s_line:<{summary_width}}"
    t_part = f"{type_str:<6}"
    b_part = f"{b_line:<{branch_width}}"
    
    if i > 0:
        id_part = " " * 3
        p_part = " " * 2
        t_part = " " * 6
    
    print(f"'{id_part} {p_part} {s_part} {t_part} {b_part}'")
