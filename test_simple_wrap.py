def simple_wrap(text, width):
    result = []
    while len(text) > width:
        result.append(text[:width])
        text = text[width:]
    result.append(text)
    return result

print(simple_wrap("116-task-test-nested-branching-fix-1234", 25))
