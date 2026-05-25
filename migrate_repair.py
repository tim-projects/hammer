    def _migrate_live_to_done(self):
        """Migrate .tasks/live to .tasks/done if it exists."""
        live_dir = os.path.join(self.tasks_path, "live")
        done_dir = os.path.join(self.tasks_path, "done")

        if os.path.exists(live_dir):
            items = [i for i in os.listdir(live_dir) if i != ".gitkeep"]
            if items:
                self.log(f"Migrating {len(items)} tasks from LIVE to DONE...")
                os.makedirs(done_dir, exist_ok=True)
                for item in items:
                    src = os.path.join(live_dir, item)
                    dst = os.path.join(done_dir, item)
                    if os.path.exists(os.path.join(self.tasks_path, ".git")):
                        res = self._run_git(
                            ["mv", os.path.join("live", item), os.path.join("done", item)],
                            cwd=self.tasks_path,
                        )
                        if res.returncode != 0:
                            if os.path.exists(dst):
                                if os.path.isdir(dst):
                                    shutil.rmtree(dst)
                                else:
                                    os.remove(dst)
                            shutil.move(src, dst)
                    else:
                        if os.path.exists(dst):
                            if os.path.isdir(dst):
                                shutil.rmtree(dst)
                            else:
                                os.remove(dst)
                        shutil.move(src, dst)

                if os.path.exists(os.path.join(self.tasks_path, ".git")):
                    self._run_git(["add", "--all"], cwd=self.tasks_path)
                    self._run_git(
                        ["commit", "-m", "Migrate LIVE tasks to DONE"],
                        cwd=self.tasks_path,
                    )
                self.log("Migration complete.")
