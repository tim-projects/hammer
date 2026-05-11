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
    
    # ID width = 3, Space = 1, Priority width = 2, Space = 1, Summary width = 30, Space = 1, Type width = 6, Space = 1
    # Total fixed prefix = 3+1+2+1 = 7.
    # The first line has: ' 86' (3 chars, id) + ' ' + ' 2' (2 chars, priority)
    # The output from the code: ' 86  2 '
    # 3 (id) + 1 (space) + 2 (priority) + 1 (space) = 7 spaces/chars. Correct.
    
    # The type column: 6 chars.
    
    row = f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}"
    
    # The wrapped line has: 7 spaces (prefix) + 30 (summary) + 1 space + 6 (type space) + 1 space + branch
    # Let's see: 7 + 30 + 1 + 6 + 1 + 25 = 70.
    
    # It looks correct. Maybe it is just the visual width on your terminal.
    # Let's try adding explicit spaces to ensure it doesn't wrap oddly.
    row_manual = f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}"
    if i > 0:
        row_manual = " " * 3 + " " + " " * 2 + " " + s_line.ljust(summary_width) + " " + "      " + " " + b_line.ljust(branch_width)
        
    print(f"|{row_manual}|")
