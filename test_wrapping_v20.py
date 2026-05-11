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
    
    # Try using exact spacing
    id_f = "3"
    p_f = "2"
    t_f = "6"
    
    # Just construct the string directly
    line = f"{id_str:>{id_f}} {p_str:>{p_f}} {s_line:<{summary_width}} {type_str:<{t_f}} {b_line:<{branch_width}}"
    
    # If i > 0, we need to replace the ID/P/Type with spaces
    # The columns are 3, 2, sum, 6, branch
    if i > 0:
        # replace the beginning
        line = " " * 3 + " " + " " * 2 + " " + s_line.ljust(summary_width) + " " + " " * 6 + " " + b_line.ljust(branch_width)
    print(line)
