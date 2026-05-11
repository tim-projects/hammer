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
    
    # Let's count indices in line 2:
    # 7 spaces (0-6)
    # Summary (7-36)
    # Space (37)
    # Type (38-43)
    # Space (44)
    # Branch (45-69)
    
    # Correct alignment!
    
    # Wait, the summary_width in test is 30.
    # 7 + 30 = 37. Index 37 is the 38th character. Correct.
    
    # I think I am looking at it wrong.
    # If the summary is 30, it occupies 7 to 36.
    # The space after is 37.
    # The Type column is 38-43.
    # The space after is 44.
    # The branch column is 45-69.
    
    # It works fine in my test!
    
    row = f"{id_str:>3} {p_str:>2} {s_line:<{summary_width}} {type_str:<6} {b_line:<{branch_width}}"
    if i > 0:
        row = f"{' ':>3} {' ':>2} {s_line:<{summary_width}} {'':<6} {b_line:<{branch_width}}"
        
    print(f"|{row}|")
