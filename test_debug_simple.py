summary_lines = ['Test Nested Branching Fix', '12345']
branch_lines = ['116-task-test-nested-bran', 'ching-fix-1234']
max_lines = max(len(summary_lines), len(branch_lines))
for i in range(max_lines):
    print(f"Loop i={i}")
    s_line = summary_lines[i] if i < len(summary_lines) else ""
    b_line = branch_lines[i] if i < len(branch_lines) else ""
    print(f"  {s_line=} {b_line=}")
