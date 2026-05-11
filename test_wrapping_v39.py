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
    # Summary width: 30
    # Space between summary and type: 1
    # Type width: 6
    # Space between type and branch: 1
    
    # The output from the code:
    # 86  2 Implement Epic/Feature Branch  task   86-task-implement-epic-fe
    # 7 spaces + 30 chars + 1 space + 6 chars + 1 space + 25 chars.
    
    # Wait, 7 spaces + 30 summary chars + 1 space + 6 type chars + 1 space = 45 chars before branch starts.
    # Let's count the characters in the test output:
    # '| 86  2 Implement Epic/Feature Branch  task   86-task-implement-epic-fe|'
    # 1 space + 2 + 2 spaces + 2 + 1 space + 30 + 1 space + 6 + 3 spaces + 25
    # The alignment seems off in the printing logic.
    
    row = f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}"
    print(f"|{row}|")
