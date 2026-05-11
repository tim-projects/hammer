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
    
    # Correct alignment:
    # Use spaces for the columns to align wrapped lines
    row = f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}"
    # Print the structure for debugging.
    # The output from the code: ' 86  2 Implement Epic/Feature Branch  task   86-task-implement-epic-fe'
    # Actually, if I look closely, the wrapped line is:
    # '       Workflow very very long               ature-branch-and-more    '
    # It has 7 leading spaces.
    # Summary start: ID(3)+space(1)+P(2)+space(1) = 7.
    # So the wrapped line has 7 spaces.
    # Summary width is 30.
    # So it should have 7 spaces + 30 spaces for summary + 1 space + ...
    print(f"|{row}|")
