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
    
    # Use exact padding
    # ID:3, P:2, Type:6
    id_f = f"{id_str:>3}" if i == 0 else "   "
    p_f = f"{p_str:>2}" if i == 0 else "  "
    t_f = f"{type_str:<6}" if i == 0 else "      "
    
    row = f"{id_f} {p_f} {s_line:<{summary_width}} {t_f} {b_line:<{branch_width}}"
    # Print length to debug alignment
    print(f"|{row}| Len: {len(row)}")
