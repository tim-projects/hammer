# Header alignment:
# Summary width 30, branch_width 25
header = f"{'#':>3} {'P':>2} {'Summary':<30} {'Type':<6} {'Branch':<25}"
print(f"|{header}|")
print(f"|{'86':>3} {'2':>2} {'Summary text here':<30} {'task':<6} {'86-task-some-branch-name':<25}|")
print(f"|{'':>3} {'':>2} {'Summary text wrap':<30} {'':<6} {'some-other-branch-name':<25}|")
