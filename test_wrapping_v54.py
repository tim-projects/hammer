# If branch_width is 25 but string is 37:
# The f-string will not truncate.
# I need to truncate the branch string if it is too long for the column!

def simple_wrap(text, width):
    result = []
    while len(text) > width:
        result.append(text[:width])
        text = text[width:]
    result.append(text)
    return result

branch = "86-task-implement-epic-feature-branch"
branch_width = 25
print(f"|{branch:<{branch_width}}|")
# It prints the whole string, which is longer than branch_width.
# My f-string just expands the column!
