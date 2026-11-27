#!/usr/bin/env python3
"""Record explicit deployment lineage for the same run's monitor-only rerun.

Inputs are trusted dependency outputs, not values recovered by looking for an
older success. This credential-free writer performs no API or server mutation.
The reader separately verifies both artifact digests and original run metadata.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import re

from production_candidate import identity


def build(source_artifact_id, source_artifact_digest, source_attempt,
          source_prepare_attempt, current_prepare_attempt, *, environ=None, at=None):
    env = os.environ if environ is None else environ
    current = identity(env)
    attempt = int(env['GITHUB_RUN_ATTEMPT'])
    numbers = (source_artifact_id, source_attempt, source_prepare_attempt, current_prepare_attempt)
    if (any(type(value) is not int or value <= 0 for value in numbers)
            or not source_prepare_attempt <= source_attempt <= attempt
            or current_prepare_attempt != source_prepare_attempt
            or not isinstance(source_artifact_digest, str)
            or not re.fullmatch(r'sha256:[0-9a-f]{64}', source_artifact_digest)):
        raise ValueError('Invalid publication dependency lineage')
    now = at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError('Reference timezone required')
    return {'schemaVersion': 1, 'repository': current['repository'], 'workflow': 'production.yml',
            'runId': current['runId'], 'runAttempt': attempt, 'commit': current['commit'],
            'createdAt': now.astimezone(timezone.utc).isoformat(),
            'sourceAttempt': source_attempt, 'sourcePrepareAttempt': source_prepare_attempt,
            'currentPrepareAttempt': current_prepare_attempt, 'sourceArtifactId': source_artifact_id,
            'sourceArtifactDigest': source_artifact_digest}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source-artifact-id', type=int, required=True)
    parser.add_argument('--source-artifact-digest', required=True)
    parser.add_argument('--source-attempt', type=int, required=True)
    parser.add_argument('--source-prepare-attempt', type=int, required=True)
    parser.add_argument('--current-prepare-attempt', type=int, required=True)
    parser.add_argument('--output', default='production-publication-reference.json')
    args = parser.parse_args()
    report = build(args.source_artifact_id, args.source_artifact_digest, args.source_attempt,
                   args.source_prepare_attempt, args.current_prepare_attempt)
    Path(args.output).write_text(json.dumps(report, sort_keys=True, indent=2)+'\n')
    print(json.dumps({'status': 'reference_recorded', 'runId': report['runId'],
                      'runAttempt': report['runAttempt'], 'sourceAttempt': report['sourceAttempt']}))


if __name__ == '__main__':
    main()
