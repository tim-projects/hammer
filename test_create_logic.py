import re


def test_creation_flow():
    title = "Implement feature X"
    numeric_id = 163

    # Existing create logic for main task
    clean_title = re.sub(r"[^a-zA-Z0-9]+", "-", title.lower()).strip("-")
    task_id = f"{numeric_id}-task-{clean_title[:30]}".strip("-")

    # New logic for pair task
    pair_title = f"Write user tests for {numeric_id}: {title}"
    pair_numeric_id = numeric_id + 1
    clean_pair_title = re.sub(r"[^a-zA-Z0-9]+", "-", pair_title.lower()).strip("-")
    pair_task_id = f"{pair_numeric_id}-task-{clean_pair_title[:30]}".strip("-")

    print(f"Main Task: {task_id}")
    print(f"Pair Task: {pair_task_id}")


test_creation_flow()
