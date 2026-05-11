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
    
    # Let's count again
    # i=0: id_str(3)+1+p_str(2)+1+s_line(30)+1+type_str(6)+1+b_line(25) = 70
    
    # Try constructing exactly by index
    # Row parts: ID(3), space(1), P(2), space(1), Summary(30), space(1), Type(6), space(1), Branch(25)
    
    if i == 0:
        row = f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}"
    else:
        # Prefix = 7 spaces
        # Summary(30) + 1 space = 31 chars
        # Type_space(7 chars)
        # Branch(25)
        # Prefix(7) + Summary(30) + 1 + 6 + 1 + 25 = 70.
        row = " " * 7 + s_line.ljust(summary_width) + " " + " " * 6 + " " + b_line.ljust(branch_width)
        
    print(f"|{row}|")
