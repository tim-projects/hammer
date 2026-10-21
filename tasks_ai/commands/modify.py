import hashlib
import json
import os
import re

from ..constants import CURRENT_TASK_FILENAME
from ..file_manager import FM
from ..utils import parse_filename


def _review_paths(cli, filepath, state_folder):
    """Resolve the review directory and patches directory for a task."""
    from ..constants import STATE_FOLDERS

    review_dir = os.path.join(cli.tasks_path, STATE_FOLDERS.get(state_folder, state_folder.lower()))
    task_folder_name = os.path.basename(filepath)
    patches_dir = os.path.join(review_dir, task_folder_name, "patches")
    return review_dir, task_folder_name, patches_dir


def _patch_md5(patch_path):
    with open(patch_path, "rb") as fh:
        return hashlib.md5(fh.read()).hexdigest()


def _has_real_patches(task, patches_dir):
    """A task has real changes to review only if it has patch files on disk."""
    patch_files = task.metadata.get("PatchFiles", [])
    return bool(patch_files) and os.path.isdir(patches_dir) and bool(os.listdir(patches_dir))


def run(cli, filename, task_type=None, title=None, story=None, tech=None, criteria=None, plan=None, repro=None, notes=None, progress=None, findings=None, mitigations=None, tests_passed=None, priority=None, regression_check=None, reviewed=None):
    """Execution logic for 'tasks modify'."""
    filepath, _ = cli.find_task(filename)
    if not filepath:
        cli.error(f"Task '{filename}' not found.")
    task = FM.load(filepath)
    fname = os.path.basename(filepath)
    task_id = fname.rsplit('.', 1)[0]
    tt, _ = parse_filename(fname)
    updated = False
    if task_type:
        task.metadata['Ty'] = task_type
        updated = True
    if title:
        title = title.strip()
        if len(title) < 10:
            cli.error('Title too vague.')
        task.metadata['Ti'] = title
        updated = True
    if story:
        task.parts['story'] = story
        updated = True
    if tech:
        task.parts['tech'] = tech
        updated = True
    if criteria:
        if isinstance(criteria, list):
            task.parts['criteria'] = '\n'.join(c if re.match('^\\s*- \\[( |x)\\] ', c) else f'- [ ] {c}' for c in criteria)
        else:
            task.parts['criteria'] = criteria
        updated = True
    if plan:
        if isinstance(plan, list):
            task.parts['plan'] = '\n'.join((f'{i}. {p}' for i, p in enumerate(plan, 1)))
        else:
            task.parts['plan'] = plan
        updated = True
    if repro:
        if isinstance(repro, list):
            task.parts['repro'] = '\n'.join((f'{i}. {r}' for i, r in enumerate(repro, 1)))
        else:
            task.parts['repro'] = repro
        updated = True
    if notes or progress or findings or mitigations:
        n = task.parts.get('notes', '- Progress: \n- Findings: \n- Mitigations: \n')
        if notes:
            n = notes
        if progress:
            n = re.sub('- Progress:.*', f'- Progress: {progress}', n)
        if findings:
            n = re.sub('- Findings:.*', f'- Findings: {findings}', n)
        if mitigations:
            n = re.sub('- Mitigations:.*', f'- Mitigations: {mitigations}', n)
        task.parts['notes'] = n
        updated = True
    if tests_passed is not None:
        task.metadata['Tp'] = bool(tests_passed)
        updated = True
    if reviewed is not None:
        task.metadata['Reviewed'] = bool(reviewed)
        if reviewed:
            review_dir, task_folder_name, patches_dir = _review_paths(cli, filepath, 'REVIEW')
            gen_time = task.metadata.get('PatchGenTime')
            patch_files = task.metadata.get('PatchFiles', [])
            if gen_time and patch_files and os.path.isdir(patches_dir) and os.listdir(patches_dir):
                # Real changes to review: the user must have opened each patch file
                # (at least once after generation) and we record a verifiable md5.
                import time

                records = []
                for patch_info in patch_files:
                    patch_filename = f"{patch_info['file'].replace(os.sep, '_')}.patch"
                    patch_path = os.path.join(patches_dir, patch_filename)
                    if not os.path.exists(patch_path):
                        cli.error(
                            f"Patch file '{patch_filename}' missing.",
                            hint=f"Run 'tasks audit {task.metadata.get('Id')}' to regenerate patches.",
                        )
                    if gen_time and os.path.getatime(patch_path) < gen_time:
                        cli.error(
                            f"Patch '{patch_filename}' has not been reviewed since generation.",
                            hint=f"Open the file to confirm review, e.g. 'cat {patch_path}'",
                        )
                    records.append(
                        {
                            "file": patch_info["file"],
                            "patch": patch_filename,
                            "md5": _patch_md5(patch_path),
                        }
                    )
                reviews_path = os.path.join(review_dir, task_folder_name, "reviews.json")
                with open(reviews_path, "w") as fh:
                    json.dump(
                        {"reviews": records, "reviewed_at": time.time()}, fh, indent=2
                    )
            cli.log(
                f"💡 HINT: Manual review confirmed for [{task.metadata.get('Id')}].\n"
                f"Now run:\n1. './hammer tasks audit {task.metadata.get('Id')}' to generate a formal audit record.\n"
                f"2. './hammer tasks verify {task.metadata.get('Id')} --proof \"<evidence>\"' to bind proof to the audit hash.\n"
                f"3. './hammer tasks modify {task.metadata.get('Id')} --regression-check' to pass the gate."
            )
        updated = True
    if priority is not None:
        task.metadata['Pr'] = priority
        updated = True
    if regression_check is not None:
        if regression_check:
            review_dir, task_folder_name, patches_dir = _review_paths(cli, filepath, 'REVIEW')
            has_changes = _has_real_patches(task, patches_dir)
            if has_changes:
                # Reviews are verifiable and mandatory when there are real changes.
                if not task.metadata.get('Reviewed'):
                    cli.error(
                        'REGRESSION_CHECK_NOT_PASSED',
                        task_id=task_id,
                        hint=f"Run 'tasks modify {task_id} --reviewed' after manually reading the patches.",
                    )
                reviews_path = os.path.join(review_dir, task_folder_name, 'reviews.json')
                if not os.path.exists(reviews_path):
                    cli.error(
                        'REGRESSION_CHECK_NOT_PASSED',
                        task_id=task_id,
                        hint=f"Run 'tasks modify {task_id} --reviewed' to record verifiable per-patch md5 reviews.",
                    )
                with open(reviews_path) as fh:
                    review_records = json.load(fh).get('reviews', [])
                for rec in review_records:
                    patch_path = os.path.join(patches_dir, rec["patch"])
                    if not os.path.exists(patch_path) or _patch_md5(patch_path) != rec.get("md5"):
                        cli.error(
                            'AUDIT_MISMATCH',
                            task_id=task_id,
                            hint=f"Patch content changed since review of '{rec.get('patch')}'. Re-run 'tasks modify {task_id} --reviewed' after re-reading.",
                        )
                # The audit record binds an MD5 of all patch file contents.
                audit_path = os.path.join(review_dir, f'{task_id}.audit')
                if not os.path.exists(audit_path):
                    cli.error('AUDIT_MISSING', audit_path=audit_path)
                from ..audit import verify_audit
                from ..pipeline import PipelineError

                if not verify_audit(filepath, patches_dir, audit_path):
                    cli.error('AUDIT_MISMATCH', task_id=task_id)
                # sha256 integrity over criteria.md + verification_proof.log + audit (.audit_hash)
                try:
                    cli.pipeline.check_audit_integrity(cli, task_id, filepath)
                except PipelineError as e:
                    cli.error(e.code, **e.kwargs)
            else:
                # No actual changes to review: auto-pass (do not require Reviewed).
                cli.log(f"No patch changes to verify for [{task_id}]; auto-passing regression check.")
            task.metadata['Rc'] = 'PASSED'
        else:
            task.metadata['Rc'] = ''
        updated = True
    if updated:
        cli._atomic_write(filepath, task)
        dump_path = os.path.join(filepath, CURRENT_TASK_FILENAME)
        if os.path.exists(dump_path):
            dump = FM.load(dump_path)
            dump.parts['content'] = task.parts.get('notes', '')
            cli._atomic_write(dump_path, dump)
        cli._append_log(filepath, 'Mod')
        cli._run_git(['add', '--all'], cwd=cli.tasks_path)
        cli._run_git(['commit', '--allow-empty', '-m', f'Mod {os.path.basename(filepath)}'], cwd=cli.tasks_path)
        cli.log(f"Modified: [{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}")
        _, _branch = parse_filename(os.path.basename(filepath))
    else:
        cli.log('No changes.')
    cli.finish({'id': task.metadata.get('Id'), 'task_id': task_id, 'title': task.metadata.get('Ti', '')})