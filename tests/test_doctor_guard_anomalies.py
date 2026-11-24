"""User tests for task 320: doctor reports structural guard anomalies safely."""

import json
import os
import subprocess

from tests.hammer_test_base import HammerTestBase, ensure_dev_repo

STORY = "Sufficiently long story content here to pass validation"
TECH = "Sufficiently long technical description here to pass validation"
CRITERIA = "Sufficiently long acceptance criteria here to pass validation"
PLAN = "Sufficiently long planning details here to pass validation"
TITLE = "Doctor Guard Anomaly Probe Task"
BASE_ID = 9300


class DoctorGuardAnomalyTestBase(HammerTestBase):
    def setUp(self):
        super().setUp()
        fixture_hammer = os.path.join(self.repo_path, "hammer")
        if os.path.lexists(fixture_hammer):
            os.remove(fixture_hammer)
        os.symlink(os.path.join(os.getcwd(), "hammer"), fixture_hammer)

    @property
    def dev_repo_dir(self):
        return ensure_dev_repo(self.dev_tasks_dir)

    def git(self, args, cwd=None):
        return subprocess.run(
            ["git"] + args,
            cwd=cwd or self.repo_path,
            capture_output=True,
            text=True,
            check=False,
        )

    def create_task(self):
        self.seed_task_id_floor(BASE_ID - 1)
        result = self.run_tasks(
            [
                "create",
                TITLE,
                "--story",
                STORY,
                "--tech",
                TECH,
                "--criteria",
                CRITERIA,
                "--plan",
                PLAN,
            ]
        )
        assert result.returncode == 0, result.stdout
        return json.loads(result.stdout)["data"]

    def doctor(self, fix=False):
        args = [os.path.join(self.repo_path, "hammer"), "tasks", "--dev", "doctor"]
        if fix:
            args.append("--fix")
        return subprocess.run(
            args, cwd=self.repo_path, capture_output=True, text=True, check=False
        )


class TestDoctorReportsGuardAnomalies(DoctorGuardAnomalyTestBase):
    def test_doctor_output_lists_guard_code_task_detail_and_hint(self):
        payload = self.create_task()
        duplicate = f"{payload['id']}-task-duplicate-branch"
        self.git(["branch", duplicate], cwd=self.dev_repo_dir)

        result = self.doctor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = result.stdout + result.stderr
        self.assertIn("GUARD_DUPLICATE_ID", text)
        self.assertIn(str(payload["id"]), text)
        self.assertIn(duplicate, text)
        self.assertIn("hammer tasks mount", text)

    def test_doctor_fix_reports_structural_anomaly_without_repairing_it(self):
        payload = self.create_task()
        duplicate = f"{payload['id']}-task-duplicate-branch"
        self.git(["branch", duplicate], cwd=self.dev_repo_dir)

        result = self.doctor(fix=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = result.stdout + result.stderr
        self.assertIn("GUARD_DUPLICATE_ID", text)
        self.assertIn("hammer tasks mount", text)
        self.assertEqual(
            0,
            self.git(
                ["rev-parse", "--verify", duplicate], cwd=self.dev_repo_dir
            ).returncode,
            "doctor --fix deleted a structurally ambiguous branch",
        )

    def test_doctor_without_fix_does_not_write_bug_report_files(self):
        payload = self.create_task()
        duplicate = f"{payload['id']}-task-duplicate-branch"
        self.git(["branch", duplicate], cwd=self.dev_repo_dir)
        before = set(os.listdir(self.dev_tasks_dir))

        result = self.doctor()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, set(os.listdir(self.dev_tasks_dir)))
