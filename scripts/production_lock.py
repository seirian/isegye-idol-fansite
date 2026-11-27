"""Exclusive, attributable locks for the fixed production root.

No lock is reclaimed by age. A lost acquire response is unknown, not ownership.
Termination handlers enter the caller's existing rollback/finally path; a hard
kill can still leave a lock, whose exact owner is retained for guarded recovery.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
import re
import signal
import sys
import threading

import inour_sftp as d

REPO = 'seirian/isegye-idol-fansite'
LOCK = d.ROOT + '/.deploy-lock'
RECOVERY_LOCK = d.ROOT + '/.deploy-recovery-lock'
OWNER_NAME = 'owner.json'
SCHEMA = 1


class Interrupted(d.Stop):
    """Cancellation reaches the existing rollback code, then owned cleanup."""


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode()


def now():
    return datetime.now(timezone.utc).isoformat()


def owner_identity(purpose, commit=None):
    d.require(re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', purpose) is not None,
              'Invalid production lock purpose')
    actions = os.getenv('GITHUB_ACTIONS') == 'true'
    repo = os.getenv('GITHUB_REPOSITORY', REPO)
    ref = os.getenv('GITHUB_REF', 'local')
    run = os.getenv('GITHUB_RUN_ID', '')
    attempt = os.getenv('GITHUB_RUN_ATTEMPT', '')
    sha = commit or os.getenv('GITHUB_SHA', '')
    workflow_ref = os.getenv('GITHUB_WORKFLOW_REF', '')
    if actions:
        d.require(repo == REPO and ref.startswith('refs/heads/') and
                  re.fullmatch(r'[1-9][0-9]*', run or '') is not None and
                  re.fullmatch(r'[1-9][0-9]*', attempt or '') is not None and
                  re.fullmatch(r'[0-9a-f]{40}', sha or '') is not None and
                  workflow_ref.startswith(REPO + '/.github/workflows/'),
                  'Verified Actions identity required for production lock')
    # Local identities are useful for isolated tests but are never reclaimable
    # as a terminal GitHub owner by the recovery command.
    return {'schemaVersion': SCHEMA, 'repository': repo, 'ref': ref,
            'runId': int(run) if actions else None,
            'runAttempt': int(attempt) if actions else None,
            'workflowRef': workflow_ref if actions else 'local',
            'commit': sha if re.fullmatch(r'[0-9a-f]{40}', sha or '') else None,
            'nonce': os.urandom(24).hex(), 'purpose': purpose,
            'acquiredAt': now(), 'updatedAt': now(), 'phase': 'acquired'}


def public_owner(owner):
    return {key: owner.get(key) for key in
            ('schemaVersion', 'repository', 'ref', 'runId', 'runAttempt',
             'workflowRef', 'commit', 'purpose', 'acquiredAt', 'updatedAt', 'phase')}


def decode_owner(raw):
    d.require(isinstance(raw, bytes) and 0 < len(raw) <= 4096,
              'Production lock owner missing or oversized')
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeError):
        raise d.Stop('Invalid production lock owner') from None
    keys = {'schemaVersion', 'repository', 'ref', 'runId', 'runAttempt',
            'workflowRef', 'commit', 'nonce', 'purpose', 'acquiredAt', 'updatedAt', 'phase'}
    d.require(isinstance(doc, dict) and set(doc) == keys and doc['schemaVersion'] == SCHEMA and
              doc['repository'] == REPO and isinstance(doc['ref'], str) and
              re.fullmatch(r'[0-9a-f]{48}', doc.get('nonce', '')) is not None and
              re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', doc.get('purpose', '')) is not None and
              re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', doc.get('phase', '')) is not None,
              'Unrecognized production lock owner')
    for key in ('acquiredAt', 'updatedAt'):
        try:
            stamp = datetime.fromisoformat(doc[key])
            d.require(stamp.tzinfo is not None, 'Lock owner time requires timezone')
        except (ValueError, TypeError):
            raise d.Stop('Invalid lock owner time') from None
    return doc


@dataclass
class HeldLock:
    path: str
    owner: dict
    raw: bytes
    report: dict | None = None
    handlers: dict = field(default_factory=dict)
    released: bool = False

    def record(self, state, **extra):
        value = {'state': state, 'owner': public_owner(self.owner),
                 'ownerSha256': d.digest(self.raw), **extra}
        if self.report is not None:
            self.report['productionLock'] = value
        return value

    def install_handlers(self):
        if threading.current_thread() is not threading.main_thread():
            return
        def interrupted(signum, _frame):
            # Do not run SFTP inside a signal callback. Unwind through the
            # existing publication rollback and finally blocks instead.
            self.record('interrupted', signal=signum)
            raise Interrupted('Production writer interrupted; owned cleanup required')
        for signum in (signal.SIGINT, signal.SIGTERM):
            self.handlers[signum] = signal.getsignal(signum)
            signal.signal(signum, interrupted)

    def restore_handlers(self):
        for signum, previous in self.handlers.items():
            signal.signal(signum, previous)
        self.handlers.clear()


def assert_no_recovery(remote):
    d.require(remote.info(RECOVERY_LOCK) is None,
              'Production lock recovery in progress; writer stopped')


def acquire(remote, *, purpose, report=None, commit=None, recovery=False):
    path = RECOVERY_LOCK if recovery else LOCK
    handle = HeldLock(path, owner_identity(purpose, commit), b'', report)
    handle.raw = encoded(handle.owner)
    remote.parents(path)
    if not recovery:
        assert_no_recovery(remote)
    if remote.info(path) is not None:
        if report is not None:
            report['productionLock'] = {'state': 'busy', 'ownerConfirmed': False}
        raise d.Stop('Production lock busy; existing owner preserved')
    handle.install_handlers()
    try:
        # Atomic exclusive mkdir. If this request loses its response, ownership
        # is unknown and no pre-existing/empty directory is deleted.
        remote.s.mkdir(path, 0o700)
        remote.directory(path)
        remote.s.chmod(path, 0o700)
        remote.new(path + '/' + OWNER_NAME, handle.raw)
        remote.s.chmod(path + '/' + OWNER_NAME, 0o600)
        d.require(remote.read(path + '/' + OWNER_NAME) == handle.raw,
                  'Production lock owner readback failed')
        if not recovery:
            assert_no_recovery(remote)
        handle.record('acquired')
        return handle
    except BaseException:
        # Only an exact random token written by this process permits cleanup.
        # Never turn a mkdir timeout or a missing owner file into authorization.
        try:
            if remote.read(path + '/' + OWNER_NAME) == handle.raw:
                release(remote, handle)
            else:
                handle.record('acquire_unknown')
        except Exception:
            handle.record('acquire_unknown')
        finally:
            handle.restore_handlers()
        raise


def checkpoint(remote, handle, phase):
    d.require(re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', phase) is not None,
              'Invalid production lock phase')
    d.require(not handle.released, 'Released production lock')
    value = dict(handle.owner, phase=phase, updatedAt=now())
    raw = encoded(value)
    remote.replace(handle.path + '/' + OWNER_NAME, raw, handle.raw)
    remote.s.chmod(handle.path + '/' + OWNER_NAME, 0o600)
    handle.owner, handle.raw = value, raw
    handle.record('acquired')


def release(remote, handle):
    """Atomically retire the owned directory before cleaning its own marker.

    A cleanup interruption leaves an attributable quarantine, not an empty
    anonymous production lock. Standard SFTP rename must refuse replacement.
    """
    if handle.released:
        return
    primary_error = sys.exc_info()[0]
    try:
        remote.parents(handle.path)
        remote.directory(handle.path)
        d.require(remote.read(handle.path + '/' + OWNER_NAME) == handle.raw,
                  'Production lock owner changed; cleanup refused')
        retired = handle.path + '.released-' + handle.owner['nonce']
        remote.parents(retired)
        d.require(remote.info(retired) is None, 'Production lock retirement target exists')
        remote.s.rename(handle.path, retired)
        remote.directory(retired)
        d.require(remote.read(retired + '/' + OWNER_NAME) == handle.raw,
                  'Production lock retirement readback failed')
        handle.released = True
        remote.remove_own(retired + '/' + OWNER_NAME, handle.raw)
        remote.s.rmdir(retired)
        handle.record('released')
    except Exception as exc:
        handle.record('released_cleanup_pending' if handle.released else 'cleanup_failed',
                      errorType=type(exc).__name__)
        if primary_error is None:
            raise
    finally:
        handle.restore_handlers()
