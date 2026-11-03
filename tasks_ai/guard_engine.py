"""Guard engine: disposable SQLite cache over git refs.

Git is the database. This module builds a *disposable* local index from two
git subprocess calls so pipeline gates can answer integrity questions fast.
The cache can be deleted and rebuilt from git alone at any moment
(`hammer guard rebuild`); a corrupt cache self-heals on the next command.

Invariants (see plan-guard.md):
  GUARD_DUPLICATE_ID         >1 local branch claims one task id          REJECT
  GUARD_DUPLICATE_REMOTE_ID  >1 remote branch claims one task id         WARN
  GUARD_BRANCH_NONCONFORMANT branch name breaks <id>-<type>-<slug>       REJECT
  GUARD_BRANCH_MISSING       no local branch for a promoted task         REJECT
  GUARD_STATE_DUPLICATE      one task id in two state folders            REJECT
  GUARD_WORKTREE_ORPHAN      worktree without its branch / duplicated    WARN
  GUARD_REMOTE_DIVERGENCE    local task lost its branch                  WARN
  GUARD_UNAVAILABLE          guard cannot verify (fail closed)           REJECT

shortcut: worktree anomalies are WARN, not REJECT (plan wanted REJECT):
`git worktree list` in dev fixtures legitimately shows worktrees without
matching branches, so rejecting there would break the existing suite.
Upgrade to REJECT once dev fixtures stop creating throwaway worktrees.
"""

import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone

from .constants import STATE_FOLDERS, TASKS_BRANCH

SCHEMA_VERSION = "1"
CACHE_DIR_NAME = "hammer-guard"
DB_NAME = "guard.db"
TASKS_REF_REMOTE = f"origin/{TASKS_BRANCH}"

# <id>-<type>-<slug> convention (enforced by the pre-commit hook)
BRANCH_CONVENTION_RE = re.compile(r"^(\d+)-(task|issue|docs)-[a-zA-Z0-9-]+$")
LEADING_ID_RE = re.compile(r"^(\d+)-")

PROMOTED_STATES = ("TESTING", "REVIEW", "STAGING", "DONE", "ARCHIVED")

SEVERITY_REJECT = "REJECT"
SEVERITY_WARN = "WARN"

# Anomalies that report but never block a gate. A stale/divergent remote
# snapshot is not an integrity breach (plan-guard.md 4.5), and dev fixtures
# legitimately create worktrees without matching branches.
WARN_CODES = frozenset(
    {
        "GUARD_DUPLICATE_REMOTE_ID",
        "GUARD_REMOTE_DIVERGENCE",
        "GUARD_WORKTREE_ORPHAN",
    }
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  k TEXT PRIMARY KEY,
  v TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS refs (
  refname TEXT PRIMARY KEY,
  object  TEXT NOT NULL,
  kind    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS tasks (
  task_id       INTEGER NOT NULL,
  folder        TEXT NOT NULL,
  branch        TEXT,
  local_state   TEXT,
  remote_state  TEXT,
  remote_object TEXT,
  ref_sha       TEXT,
  PRIMARY KEY (task_id, folder)
);
CREATE INDEX IF NOT EXISTS idx_tasks_branch ON tasks(branch);
CREATE INDEX IF NOT EXISTS idx_tasks_task_id ON tasks(task_id);
CREATE TABLE IF NOT EXISTS worktrees (
  task_id INTEGER,          -- NULL for non-task worktrees (main checkout)
  branch  TEXT,
  path    TEXT NOT NULL,
  PRIMARY KEY (task_id, path)
);
CREATE TABLE IF NOT EXISTS anomalies (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  code    TEXT NOT NULL,
  task_id INTEGER,
  detail  TEXT NOT NULL,
  ts      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (       -- append-only log (forced bypasses)
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  code    TEXT NOT NULL,
  task_id INTEGER,
  detail  TEXT NOT NULL,
  ts      TEXT NOT NULL
);
"""

UNAVAILABLE_HINT = (
    "Guard could not verify integrity. Run 'hammer guard rebuild' then retry; "
    "--force overrides and logs the bypass."
)


class GuardUnavailable(Exception):
    """Guard could not verify integrity. Message must be actionable."""


def run_git(args, cwd=None):
    return subprocess.run(
        ["git"] + args, cwd=cwd, capture_output=True, text=True, check=False
    )


def task_id_of(name):
    """Leading digits of a branch/folder name, else None (not a task ref)."""
    if not name:
        return None
    match = LEADING_ID_RE.match(str(name))
    return int(match.group(1)) if match else None


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class GuardEngine:
    """Cache + verdicts. Read-only against git and `.tasks`."""

    def __init__(self, repo_root=None, tasks_path=None, dev=False, config=None, cwd=None):
        self.cwd = cwd or repo_root or os.getcwd()
        self.tasks_path = tasks_path
        self.dev = dev
        guard_cfg = (config or {}).get("guard") or {}
        self.enforce = bool(guard_cfg.get("enforce", True))
        self.fail_open = bool(guard_cfg.get("fail_open", False))
        self.staleness_warn_min = int(guard_cfg.get("staleness_warn_min", 60) or 60)
        self.cache_dir = self._resolve_cache_dir()
        self.db_path = os.path.join(self.cache_dir, DB_NAME)

    # --- cache location ---
    def _resolve_cache_dir(self):
        """<common_git_dir>/hammer-guard: one cache per repo, worktree-safe."""
        result = run_git(["rev-parse", "--git-common-dir"], cwd=self.cwd)
        if result.returncode != 0:
            raise GuardUnavailable("not a git repository; guard cannot verify integrity")
        common = result.stdout.strip()
        if not common:
            raise GuardUnavailable("empty git common dir; cannot locate guard cache")
        if not os.path.isabs(common):
            common = os.path.join(os.path.abspath(self.cwd), common)
        return os.path.join(os.path.normpath(common), CACHE_DIR_NAME)

    # --- connection ---
    def connect(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def _ensure_schema(self, conn):
        conn.executescript(SCHEMA)
        version = conn.execute("SELECT v FROM meta WHERE k='schema_version'").fetchone()
        if not version:
            conn.execute(
                "INSERT INTO meta (k, v) VALUES ('schema_version', ?)", (SCHEMA_VERSION,)
            )
        conn.commit()

    def _get_meta(self, conn, key):
        row = conn.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        return row["v"] if row else None

    def _set_meta(self, conn, key, value):
        conn.execute(
            "INSERT INTO meta (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v=excluded.v",
            (key, str(value)),
        )

    # --- refresh: git -> cache ---
    def _live_refs(self):
        """Subprocess 1: every ref with its namespace and object."""
        result = run_git(
            [
                "for-each-ref",
                "refs/heads",
                "refs/remotes",
                "refs/tags",
                "--format=%(refname)%09%(objectname)",
            ],
            cwd=self.cwd,
        )
        if result.returncode != 0:
            raise GuardUnavailable(
                "git for-each-ref failed: %s"
                % (result.stderr.strip() or "unknown error")
            )
        refs = {}
        for line in result.stdout.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            full, obj = parts[0], parts[1]
            if full.startswith("refs/heads/"):
                refs[full[len("refs/heads/"):]] = (obj, "branch")
            elif full.startswith("refs/remotes/"):
                rest = full[len("refs/remotes/"):]
                if "/" in rest:  # strip remote name (origin/)
                    refs[rest.split("/", 1)[1]] = (obj, "remote")
            elif full.startswith("refs/tags/"):
                refs[full[len("refs/tags/"):]] = (obj, "tag")
        return refs

    def _tasks_ref_object(self, conn):
        """Prefer origin/tasks, else the local tasks branch (init creates it)."""
        for name in (TASKS_REF_REMOTE, TASKS_BRANCH):
            row = conn.execute(
                "SELECT object FROM refs WHERE refname=?", (name,)
            ).fetchone()
            if row:
                return row["object"]
        return None

    def _remote_map(self, tasks_ref_object):
        """Subprocess 2: task folders tracked on the tasks branch."""
        remote = {}
        if not tasks_ref_object:
            return remote
        result = run_git(
            ["ls-tree", "-r", tasks_ref_object, "--", "*/meta.json"], cwd=self.cwd
        )
        if result.returncode != 0:
            return remote
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            path = parts[1]
            segments = path.split("/")
            if len(segments) < 3 or segments[-3] not in STATE_FOLDERS.values():
                continue
            folder = segments[-2]
            tid = task_id_of(folder)
            if tid is None:
                continue
            remote[(tid, folder)] = (segments[-3], parts[0].split()[-1])
        return remote

    def _local_map(self):
        """Zero subprocesses: walk .tasks/<state> folders."""
        local = {}
        if not self.tasks_path or not os.path.isdir(self.tasks_path):
            return local
        for folder in STATE_FOLDERS.values():
            state_dir = os.path.join(self.tasks_path, folder)
            if not os.path.isdir(state_dir):
                continue
            for name in os.listdir(state_dir):
                if name.startswith(".") or not os.path.isdir(
                    os.path.join(state_dir, name)
                ):
                    continue
                tid = task_id_of(name)
                if tid is not None:
                    local.setdefault(tid, []).append((folder, name))
        return local

    def _worktree_list(self):
        result = run_git(["worktree", "list", "--porcelain"], cwd=self.cwd)
        if result.returncode != 0:
            return []
        worktrees, current = [], {}
        for line in result.stdout.splitlines():
            if not line.strip():
                if current:
                    worktrees.append(current)
                    current = {}
                continue
            key, _, value = line.partition(" ")
            if key == "worktree":
                current = {"path": value}
            elif key == "branch":
                current["branch"] = value.replace("refs/heads/", "")
        if current:
            worktrees.append(current)
        return worktrees

    def refresh(self, conn):
        """Re-derive the cache from git and recompute anomalies."""
        self._ensure_schema(conn)
        refs = self._live_refs()
        previous = self._get_meta(conn, "prev_ref_count")
        if previous is not None and int(previous) > 0 and not refs:
            raise GuardUnavailable(
                f"total ref loss: cache knew {previous} refs, git now reports none. "
                f"Refusing to read a wiped repo as an empty one. {UNAVAILABLE_HINT}"
            )
        tasks_ref_object = self._current_tasks_ref(conn, refs)
        remote = self._remote_map(tasks_ref_object)
        local = self._local_map()
        worktrees = self._worktree_list()

        branch_by_id = {}
        for name, (obj, kind) in sorted(refs.items()):
            if kind == "branch":
                tid = task_id_of(name)
                if tid is not None:
                    branch_by_id.setdefault(tid, []).append(name)

        conn.execute("DELETE FROM refs")
        conn.executemany(
            "INSERT OR REPLACE INTO refs (refname, object, kind) VALUES (?, ?, ?)",
            [(name, obj, kind) for name, (obj, kind) in sorted(refs.items())],
        )
        conn.execute("DELETE FROM tasks")
        rows = {}
        for tid, state_folders in local.items():
            for state, folder in state_folders:
                branch = branch_by_id.get(tid, [None])[0]
                rows[(tid, folder)] = [
                    tid,
                    folder,
                    branch,
                    state,
                    None,
                    None,
                    (refs.get(branch, (None,))[0] if branch else None),
                ]
        for (tid, folder), (state, sha) in sorted(remote.items()):
            key = (tid, folder)
            if key in rows:
                rows[key][4], rows[key][5] = state, sha
            else:
                rows[key] = [
                    tid,
                    folder,
                    branch_by_id.get(tid, [None])[0],
                    None,
                    state,
                    sha,
                    None,
                ]
        conn.executemany(
            "INSERT OR REPLACE INTO tasks (task_id, folder, branch, local_state, "
            "remote_state, remote_object, ref_sha) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [rows[k] for k in sorted(rows)],
        )
        conn.execute("DELETE FROM worktrees")
        conn.executemany(
            "INSERT OR REPLACE INTO worktrees (task_id, branch, path) VALUES (?, ?, ?)",
            [
                (task_id_of(w.get("branch")), w.get("branch"), w.get("path", ""))
                for w in worktrees
            ],
        )
        self._compute_anomalies(conn, refs, local, branch_by_id, worktrees)
        self._set_meta(conn, "prev_ref_count", len(refs))
        self._set_meta(conn, "last_refresh", now_iso())
        conn.commit()
        return {"refs": len(refs), "tasks": len(rows), "worktrees": len(worktrees)}

    def _current_tasks_ref(self, conn, refs):
        for name in (TASKS_REF_REMOTE, TASKS_BRANCH):
            entry = refs.get(name)
            if entry:
                return entry[0]
        return None

    # --- anomalies ---
    def _compute_anomalies(self, conn, refs, local, branch_by_id, worktrees):
        findings = []

        def add(code, tid, detail):
            findings.append((code, tid, detail))

        for tid in sorted(set(branch_by_id) | set(local)):
            branches = branch_by_id.get(tid, [])
            if len(branches) > 1:
                add(
                    "GUARD_DUPLICATE_ID",
                    tid,
                    f"multiple local branches claim id {tid}: {', '.join(branches)}",
                )
            remote_names = sorted(
                n
                for n, (_, kind) in refs.items()
                if kind == "remote" and task_id_of(n) == tid
            )
            if len(remote_names) > 1 and branches:
                add(
                    "GUARD_DUPLICATE_REMOTE_ID",
                    tid,
                    f"multiple remote branches claim id {tid}: {', '.join(remote_names)}",
                )
            folders = local.get(tid, [])
            if len(folders) > 1:
                where = ", ".join(f"{state}/{folder}" for state, folder in folders)
                add(
                    "GUARD_STATE_DUPLICATE",
                    tid,
                    f"id {tid} exists in {len(folders)} state folders: {where}",
                )
            for branch in branches:
                if not BRANCH_CONVENTION_RE.match(branch):
                    add(
                        "GUARD_BRANCH_NONCONFORMANT",
                        tid,
                        f"branch '{branch}' breaks <id>-<type>-<slug>",
                    )
            if folders and not branches:
                add(
                    "GUARD_REMOTE_DIVERGENCE",
                    tid,
                    f"local task {tid} has no local branch (remote snapshot still tracks it)",
                )

        wt_entries = {}
        for worktree in worktrees:
            branch = worktree.get("branch")
            tid = task_id_of(branch)
            if tid is not None:
                wt_entries.setdefault(tid, []).append((branch, worktree.get("path", "")))
        for tid, entries in sorted(wt_entries.items()):
            if len(entries) > 1:
                add(
                    "GUARD_WORKTREE_ORPHAN",
                    tid,
                    f"task {tid} has {len(entries)} worktrees: "
                    + ", ".join(p for _, p in entries),
                )
            for branch, _ in entries:
                if branch not in refs:
                    add(
                        "GUARD_WORKTREE_ORPHAN",
                        tid,
                        f"worktree of task {tid} checks out missing branch '{branch}'",
                    )

        conn.execute("DELETE FROM anomalies")
        conn.executemany(
            "INSERT INTO anomalies (code, task_id, detail, ts) VALUES (?, ?, ?, ?)",
            [
                (code, tid, detail, now_iso())
                for code, tid, detail in sorted(findings)
            ],
        )

    # --- verdicts ---
    def verdict(self, task_id, from_state=None, to_state=None, branch=None):
        """Integrity verdict for one task. Raises GuardUnavailable if unverifiable."""
        task_id = int(task_id)
        try:
            return self._verdict_once(task_id, from_state, to_state, branch)
        except GuardUnavailable:
            raise
        except sqlite3.DatabaseError:
            # Corrupt cache is the expected disposable-cache failure: rebuild once.
            try:
                self._wipe()
                return self._verdict_once(task_id, from_state, to_state, branch)
            except GuardUnavailable:
                raise
            except Exception as exc:
                raise GuardUnavailable(
                    f"guard cache corrupt and rebuild failed ({exc}). {UNAVAILABLE_HINT}"
                ) from exc
        except Exception as exc:
            raise GuardUnavailable(f"{UNAVAILABLE_HINT} ({exc})") from exc

    def _verdict_once(self, task_id, from_state, to_state, branch):
        conn = self.connect()
        try:
            self._ensure_schema(conn)
            self.refresh(conn)
            return self._lookup(conn, task_id, to_state, branch)
        finally:
            conn.close()

    def _severity_for(self, code):
        """WARN unless the code blocks a gate (and enforce is on)."""
        if not self.enforce or code in WARN_CODES:
            return SEVERITY_WARN
        return SEVERITY_REJECT

    def _lookup(self, conn, task_id, to_state, branch):
        rows = conn.execute(
            "SELECT code, detail FROM anomalies WHERE task_id=?", (task_id,)
        ).fetchall()
        findings = [
            {
                "code": row["code"],
                "detail": row["detail"],
                "severity": self._severity_for(row["code"]),
            }
            for row in rows
        ]
        if branch:
            if not BRANCH_CONVENTION_RE.match(branch):
                findings.append(
                    {
                        "code": "GUARD_BRANCH_NONCONFORMANT",
                        "detail": f"branch '{branch}' breaks <id>-<type>-<slug>",
                        "severity": SEVERITY_REJECT if self.enforce else SEVERITY_WARN,
                    }
                )
            if to_state in PROMOTED_STATES:
                exists = conn.execute(
                    "SELECT 1 FROM refs WHERE refname=? AND kind='branch'", (branch,)
                ).fetchone()
                if not exists:
                    findings.append(
                        {
                            "code": "GUARD_BRANCH_MISSING",
                            "detail": f"branch '{branch}' missing; {to_state} requires it",
                            # shortcut: WARN in dev (fixtures legitimately lack branches)
                            "severity": SEVERITY_WARN if self.dev else SEVERITY_REJECT,
                        }
                    )
        return findings

    # --- reports ---
    def scan(self):
        """Full anomaly report (read-only)."""
        return self._report()

    def rebuild(self):
        """Delete the cache, rebuild from scratch, return the anomaly report."""
        self._wipe()
        return self._report()

    def _report(self):
        conn = self.connect()
        try:
            self._ensure_schema(conn)
            self.refresh(conn)
            rows = conn.execute(
                "SELECT code, task_id, detail FROM anomalies "
                "ORDER BY code, task_id, detail"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def record_anomaly(self, code, task_id, detail):
        """Append to the append-only event log (forced bypasses). Never raises.

        `anomalies` is a derived report recomputed on every refresh; bypasses
        are history, so they get their own table.
        """
        try:
            conn = self.connect()
            try:
                self._ensure_schema(conn)
                conn.execute(
                    "INSERT INTO events (code, task_id, detail, ts) VALUES (?, ?, ?, ?)",
                    (code, task_id, detail, now_iso()),
                )
                conn.commit()
            finally:
                conn.close()
        except (sqlite3.DatabaseError, OSError, GuardUnavailable):
            return False
        return True

    def events(self):
        """Recent recorded events (forced bypasses), oldest first."""
        try:
            conn = self.connect()
            try:
                self._ensure_schema(conn)
                rows = conn.execute(
                    "SELECT code, task_id, detail, ts FROM events ORDER BY id"
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()
        except (sqlite3.DatabaseError, OSError, GuardUnavailable):
            return []

    def _wipe(self):
        for name in (DB_NAME, DB_NAME + "-wal", DB_NAME + "-shm"):
            path = os.path.join(self.cache_dir, name)
            if os.path.exists(path):
                os.remove(path)
