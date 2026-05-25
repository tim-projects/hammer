# (Extracted repair: writing the correct TasksCLI init and migration block)
    def __init__(self, as_json=False, command=None, quiet=False, dev=False, yes=False):
        self.as_json = as_json
        self.quiet = quiet
        self.dev = dev
        self.yes = yes
        self.output_messages = []
        self.root = self._get_git_root()

        # Resolve absolute path to repo.py (works for both source checkout and system install)
        install_dir = Path(__file__).resolve().parent.parent
        self.repo_script = str(install_dir / "repo.py")

        # Determine tasks directory
        self.tasks_dir = TASKS_DIR
        if dev:
            self.tasks_dir = "/tmp/.tasks"
            if not os.path.exists(self.tasks_dir):
                os.makedirs(self.tasks_dir, exist_ok=True)
        else:
            # Check pyproject.toml for override first
            pyproject_path = os.path.join(self.root, "pyproject.toml")
            if os.path.exists(pyproject_path):
                try:
                    import toml
                    with open(pyproject_path, "r") as f:
                        pyproject_data = toml.load(f)
                        self.tasks_dir = (
                            pyproject_data.get("tool", {})
                            .get("tasks_ai", {})
                            .get("tasks_dir", self.tasks_dir)
                        )
                except Exception:
                    pass

        if os.path.isabs(self.tasks_dir):
            self.tasks_path = self.tasks_dir
        else:
            self.tasks_path = os.path.join(self.root, self.tasks_dir)

        # Now that self.tasks_path is set, we can check .tasks/config.yaml if not in dev mode
        if not dev:
            cfg = self._get_config()
            if cfg and isinstance(cfg, dict) and "tasks_dir" in cfg:
                td = cfg["tasks_dir"]
                if td:
                    self.tasks_dir = str(td)
                    if os.path.isabs(self.tasks_dir):
                        self.tasks_path = self.tasks_dir
                    else:
                        self.tasks_path = os.path.join(self.root, self.tasks_dir)
        self.logs_path = os.path.join(self.tasks_path, "logs")
        if os.path.exists(self.tasks_path):
            self._migrate_live_to_done()
            self._auto_archive()
            if command and command != "delete":
                self._clear_delete_marks()
