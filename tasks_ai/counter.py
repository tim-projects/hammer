import hashlib
import os


def mirror_counter_floor(cli, value):
    """Keep the legacy counter current until task 495 retires it."""
    counter_path = os.path.join(cli.tasks_path, ".task_counter")
    if not os.path.exists(counter_path):
        return
    content = str(value)
    cli._atomic_write(counter_path, content)
    digest = hashlib.md5(content.encode()).hexdigest()
    cli._atomic_write(counter_path + ".hash", digest)
    if (
        cli.git.run(
            ["add", ".task_counter", ".task_counter.hash"], cwd=cli.tasks_path
        ).returncode
        == 0
    ):
        cli.git.run(
            ["commit", "--allow-empty", "-m", f"Bump task counter to {value}"],
            cwd=cli.tasks_path,
        )
