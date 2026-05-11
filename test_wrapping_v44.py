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
    
    # Let's count the characters in the test output:
    # '| 86  2 Implement Epic/Feature Branch  task   86-task-implement-epic-fe|'
    # 1 space + 2 + 2 spaces + 2 + 1 space + 30 + 1 space + 6 + 3 spaces + 25
    
    # For line 2:
    # '|       Workflow very very long               ature-branch-and-more    |'
    # 7 spaces + 30 summary + 1 space + 6 spaces + 1 space + 25 branch
    
    # Wait, the summary starts after column 1(3) + space(1) + column 2(2) + space(1) = 7 characters.
    # So line 2 has 7 leading spaces. Correct.
    # The summary is 30 characters.
    # Then there is 1 space.
    # Then there is the type column. It has 6 characters.
    # So the type column starts after summary + 1 space = 7+30+1 = 38th character.
    # The test output for line 2:
    # 7 spaces + 30 chars = 37 chars.
    # Then one space at index 38.
    # Then 6 spaces at indices 39-44. Correct.
    # Then one space at index 45. Correct.
    # Then branch column at 46-70.
    
    # It looks correctly aligned.
    # Wait, the issue might be that I am counting spaces wrong in my head.
    
    print(f"'{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}'")
