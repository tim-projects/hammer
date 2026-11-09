import hashlib
import json
import os
import re
import time

from ..constants import CURRENT_TASK_FILENAME
from ..file_manager import FM
<<<<<<< HEAD
from ..utils import _patch_name, commit_task_paths, parse_filename
=======
from ..utils import commit_task_paths, parse_filename, resolve_content
>>>>>>> main


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
    # Bulk submission: any long-form flag may name a file instead of a string.
    story = resolve_content(cli, story)
    tech = resolve_content(cli, tech)
    criteria = resolve_content(cli, criteria, lines=True)
    plan = resolve_content(cli, plan, lines=True)
    repro = resolve_content(cli, repro, lines=True)
    notes = resolve_content(cli, notes)
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
        review_dir, task_folder_name, patches_dir = _review_paths(cli, filepath, 'REVIEW')
        has_changes = _has_real_patches(task, patches_dir)
        if has_changes:
            summary = reviewed if isinstance(reviewed, str) else None
            if summary is None:
                cli.error(
                    'REVIEW_SUMMARY_REQUIRED',
                    task_id=task_id,
                    hint=f"Finalize with a summary: 'tasks modify {task_id} --reviewed \"<what you read in each patch>\"'.",
                )
            if len(summary.strip()) < 40:
                cli.error(
                    'REVIEW_SUMMARY_TOO_SHORT',
                    task_id=task_id,
                    hint='Summarize what you read in each patch (at least 40 characters).',
                )
            from .review import covered_patches, load_reviews, write_reviews

            reviews_path = os.path.join(review_dir, task_folder_name, 'reviews.json')
            if not os.path.exists(reviews_path):
                cli.error(
                    'REVIEW_INCOMPLETE',
                    task_id=task_id,
                    missing=', '.join(_patch_name(info['file']) for info in task.metadata.get('PatchFiles', [])),
                    hint=f"Read each patch with 'tasks review {task_id}' before finalizing.",
                )
            reviews = load_reviews(cli, filepath)
            expected = [_patch_name(info['file']) for info in task.metadata.get('PatchFiles', [])]
            missing = [name for name in expected if name not in covered_patches(reviews, patches_dir, expected)]
            if missing:
                cli.error(
                    'REVIEW_INCOMPLETE',
                    task_id=task_id,
                    missing=', '.join(missing),
                    hint=f"{len(missing)} patch(es) unread. Run 'tasks review {task_id}'.",
                )
            reviews['summary'] = summary.strip()
            reviews['summary_at'] = time.time()
            reviews['reviewed_at'] = reviews.get('reviewed_at', time.time())
            write_reviews(cli, filepath, reviews)
            commit_task_paths(cli, os.path.join(review_dir, task_folder_name), f'Review summary {task_id}', reviews_path)
            task.metadata['Reviewed'] = True
            cli.log(
                f"💡 Review finalized for [{task_id}] ({len(expected)} patch(es), summary recorded).\n"
                f"Now run:\n1. './hammer tasks audit {task_id}' to generate a formal audit record.\n"
                f"2. './hammer tasks verify {task_id} --proof \"<evidence>\"' to bind proof to the audit hash.\n"
                f"3. './hammer tasks modify {task_id} --regression-check' to pass the gate."
            )
        else:
            task.metadata['Reviewed'] = True
            cli.log(f'No patch changes to review for [{task_id}]; review auto-passed.')
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
                    review_records = json.load(fh)
                if not review_records.get('summary'):
                    cli.error(
                        'REVIEW_SUMMARY_REQUIRED',
                        task_id=task_id,
                        hint=f"Finalize the review: 'tasks modify {task_id} --reviewed \"<what you read in each patch>\"'.",
                    )
                for rec in review_records.get('reviews', []):
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
        commit_task_paths(cli, filepath, f'Mod {os.path.basename(filepath)}')
        cli.log(f"Modified: [{task.metadata.get('Id', '')}] {tt} | {task.metadata.get('Ti', '')}")
        _, _branch = parse_filename(os.path.basename(filepath))
    else:
        cli.log('No changes.')
    cli.finish({'id': task.metadata.get('Id'), 'task_id': task_id, 'title': task.metadata.get('Ti', '')})