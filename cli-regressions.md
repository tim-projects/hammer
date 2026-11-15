--- cli-files/cli_main_two_weeks_ago.py	2026-05-27 21:16:22.818187611 +0000
+++ cli-files/cli_current.py	2026-05-27 21:14:57.508938590 +0000
@@ -20,6 +20,7 @@
     ALLOWED_TRANSITIONS,
     ALLOWED_CONFIG_KEYS,
 )
+from .counter import TaskCounterProtector
 from .file_manager import FM
 from .context import ProjectContext
 from .git_client import GitClient
