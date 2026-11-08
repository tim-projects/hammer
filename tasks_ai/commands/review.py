"""Execution logic for 'tasks review': read one patch at a time, one receipt per file.

Reviewing is an act, not a file state: each invocation prints one patch in full
and appends a receipt (content hashes, size, time, sequence, chain hash). Only
when every patch carries a current receipt can 'modify --reviewed' finalize the
stage, and only with a written summary.
"""

import hashlib
import json
import os
import time

from ..file_manager import FM
from ..utils import _patch_name


def _reviews_path(cli, task_path):
    return os.path.join(cli.tasks_path, 'review', os.path.basename(task_path), 'reviews.json')


def _patches_dir(cli, task_path):
    return os.path.join(cli.tasks_path, 'review', os.path.basename(task_path), 'patches')


def load_reviews(cli, task_path):
    """Read reviews.json, or empty receipts when the review has not started."""
    path = _reviews_path(cli, task_path)
    if not os.path.exists(path):
        return {'reviews': []}
    with open(path) as fh:
        return json.load(fh)


def write_reviews(cli, task_path, data):
    path = _reviews_path(cli, task_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w') as fh:
        json.dump(data, fh, indent=2)


def covered_patches(reviews, patches_dir, expected):
    """Expected patch names whose receipt still matches the file on disk."""
    covered = set()
    for receipt in reviews.get('reviews', []):
        name = receipt.get('patch')
        patch_path = os.path.join(patches_dir, name or '')
        if name in expected and os.path.exists(patch_path):
            with open(patch_path, 'rb') as fh:
                digest = hashlib.md5(fh.read()).hexdigest()
            if digest == receipt.get('md5'):
                covered.add(name)
    return covered


def receipt_hash(receipt):
    return hashlib.sha256(json.dumps(receipt, sort_keys=True).encode()).hexdigest()


def run(cli, task_id, file=None):
    """Print one patch in full and record the receipt for reading it."""
    task_path, state = cli.find_task(task_id)
    if not task_path:
        cli.error(f"Task '{task_id}' not found.", hint="Use 'hammer tasks list' to see available task Ids.")
    if state != 'REVIEW':
        cli.error(f'Task {task_id} must be in REVIEW to review patches.', hint=f'./hammer tasks move {task_id} REVIEW')

    task = FM.load(task_path)
    task_id = task.metadata.get('Id')
    patch_files = task.metadata.get('PatchFiles', [])
    patches_dir = _patches_dir(cli, task_path)
    expected = [_patch_name(info['file']) for info in patch_files]
    if not expected or not os.path.isdir(patches_dir):
        cli.error('NO_PATCHES', task_id=task_id, hint=f"Run 'tasks audit {task_id}' to generate patches.")

    reviews = load_reviews(cli, task_path)
    remaining = [name for name in expected if name not in covered_patches(reviews, patches_dir, expected)]

    if file:
        target = _patch_name(file)
        if target not in expected:
            cli.error(f"Patch '{target}' is not part of task {task_id}.", expected=', '.join(expected))
    elif remaining:
        target = remaining[0]
    else:
        cli.log(f"All {len(expected)} patch(es) of task {task_id} already reviewed.")
        cli.log(f"Finalize the review with: ./hammer tasks modify {task_id} --reviewed \"<short summary of what you read>\"")
        cli.finish({'id': task_id, 'reviewed': len(expected), 'total': len(expected), 'remaining': []})
        return

    patch_path = os.path.join(patches_dir, target)
    if not os.path.exists(patch_path):
        cli.error(f"Patch '{target}' missing.", hint=f"Run 'tasks audit {task_id}' to regenerate patches.")
    with open(patch_path, 'rb') as fh:
        content = fh.read()
    print(content.decode(errors='replace'))

    previous = reviews['reviews'][-1] if reviews['reviews'] else None
    reviews['reviews'].append({
        'seq': len(reviews['reviews']) + 1,
        'file': next(info['file'] for info in patch_files if _patch_name(info['file']) == target),
        'patch': target,
        'md5': hashlib.md5(content).hexdigest(),
        'sha256': hashlib.sha256(content).hexdigest(),
        'bytes': len(content),
        'ts': time.time(),
        'prev_hash': receipt_hash(previous) if previous else None,
    })
    # Reading again after a summary voids that summary: the stage must be
    # finalized once more against the newest content.
    reviews.pop('summary', None)
    reviews.pop('summary_at', None)
    write_reviews(cli, task_path, reviews)

    covered = covered_patches(reviews, patches_dir, expected)
    left = [name for name in expected if name not in covered]
    if left:
        cli.log(f"\n--- reviewed {target} ({len(covered)}/{len(expected)}). Next: ./hammer tasks review {task_id} ---")
    else:
        cli.log(f"\n--- all {len(expected)} patch(es) reviewed. Finalize: ./hammer tasks modify {task_id} --reviewed \"<short summary>\" ---")
    cli.finish({'id': task_id, 'patch': target, 'reviewed': len(covered), 'total': len(expected), 'remaining': left})
