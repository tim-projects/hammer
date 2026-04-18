import os
import shutil

def setup_test_repo(repo_dir):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 1. Copy check.py
    check_py = os.path.join(base_dir, "check.py")
    if os.path.exists(check_py):
        shutil.copy(check_py, repo_dir)
    
    # 2. Setup .tasks/config.yaml
    config_dir = os.path.join(repo_dir, ".tasks")
    os.makedirs(config_dir, exist_ok=True)
    
    import yaml
    config_data = {
        "repo": {
            "lint": shutil.which("ruff"),
            "test": shutil.which("pytest"),
            "type_check": shutil.which("pyright"),
            "format": shutil.which("ruff"),
        }
    }
    with open(os.path.join(config_dir, "config.yaml"), "w") as f:
        yaml.dump(config_data, f)

    # 3. Symlink venv
    venv_dir = os.path.join(base_dir, "venv")
    if os.path.exists(venv_dir):
        os.symlink(venv_dir, os.path.join(repo_dir, "venv"))
