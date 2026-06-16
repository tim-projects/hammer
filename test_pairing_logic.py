import re


def test_pairing():
    title = "Implement feature X"
    task_type = "task"
    clean_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")

    # Simulation
    numeric_id = 163
    task_id = f"{numeric_id}-{task_type}-{clean_title[:30]}".strip("-")

    pair_task_title = f"Write user tests for {numeric_id}: {title}"
    pair_numeric_id = numeric_id + 1
    clean_pair_title = re.sub(r"[^a-zA-Z0-9]+", "-", pair_task_title.lower()).strip("-")
    pair_task_id = f"{pair_numeric_id}-{task_type}-{clean_pair_title[:30]}".strip("-")

    print(f"Task ID: {task_id}")
    print(f"Pair Task ID: {pair_task_id}")


test_pairing()
