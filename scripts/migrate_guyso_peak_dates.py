"""Owner-requested peak-date-only migration; no new chart observations or clocks."""
from copy import deepcopy
from pathlib import Path
from datetime import datetime, timezone
import argparse
import json
import os
from collect_album_peak_dates import apply_reviewed, REVIEW_SHA256
ROOT = Path(__file__).resolve().parents[1]


def apply(data):
    before = deepcopy(data)
    report = apply_reviewed(data, strict=True)
    restored = deepcopy(data)
    for sid, item in restored['tracks'].items():
        old = before['tracks'][sid]
        if 'melonPeakDates' in old:
            item['melonPeakDates'] = deepcopy(old['melonPeakDates'])
        else:
            item.pop('melonPeakDates', None)
    if restored != before:
        raise ValueError('Peak-date migration touched unrelated data')
    report['records'] = {sid: deepcopy(data['tracks'][sid]['melonPeakDates'])
                         for sid in report['verifiedTracks']}
    report.update(changed=data != before, sourceClocksUnchanged=True,
        unrelatedFieldsUnchanged=True, datasetSha256=REVIEW_SHA256,
        confirmedDateCount=sum(len(p['records']) for p in report['records'].values()))
    return report


def patch_remote(remote):
    import album_runtime as runtime
    d = runtime.d
    router, release, active_path = runtime.active(remote)
    meta = json.loads(remote.read(active_path+'/build-info.json') or b'{}')
    expected = os.getenv('EXPECTED_RELEASE_SHA')
    if expected:
        d.require(meta.get('commit') == expected, 'Active release differs from the reviewed deployment')
    app = remote.read(active_path+'/src/app.js') or b''
    d.require(b'guyso_peak_date_evidence' in app and b'earliest_observed_matching_peak' in app
        and '최고 성적 출처와 확인 시각'.encode() in app,
        'Deploy reviewed peak-date evidence UI before migration')
    runtime.owned(remote)
    d.require(remote.info(runtime.path('.lock')) is None, 'Another album operation is active')
    lock = os.urandom(24)
    remote.new(runtime.path('.lock'), lock)
    remote.s.chmod(runtime.path('.lock'), 0o600)
    try:
        raw = remote.read(runtime.path('current.json'))
        d.require(raw is not None, 'Existing runtime feed required')
        data = runtime.decode(raw)
        d.require(data.get('feed') == 'daily-albums', 'Wrong runtime feed')
        report = apply(data)
        from daily_albums import validate
        validate(data, exact=True)
        candidate = (json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
        (ROOT/'guyso-peak-dates-before.json').write_bytes(raw)
        from production_lock import assert_no_recovery
        assert_no_recovery(remote)
        d.require(remote.read(d.ROOT+'/.htaccess') == router and remote.info(d.ROOT+'/.deploy-lock') is None,
                  'Release changed before peak-date migration')
        d.require(remote.read(runtime.path('current.json')) == raw, 'Feed changed; refuse stale write')
        if report['changed']:
            remote.replace(runtime.path('previous.json'), raw, remote.read(runtime.path('previous.json')))
            remote.s.chmod(runtime.path('previous.json'), 0o600)
            remote.replace(runtime.path('current.json'), candidate, raw)
            remote.s.chmod(runtime.path('current.json'), 0o600)
        else:
            candidate = raw
        try:
            d.require(remote.read(runtime.path('current.json')) == candidate, 'Peak-date readback failed')
            d.require(remote.read(d.ROOT+'/.htaccess') == router, 'Router changed after migration')
        except Exception:
            if report['changed'] and remote.read(runtime.path('current.json')) == candidate:
                remote.replace(runtime.path('current.json'), raw, candidate)
            raise
        (ROOT/'guyso-peak-dates-after.json').write_bytes(candidate)
        report.update(status='published' if report['changed'] else 'already_applied',
            verifiedReadback=True, release=release, beforeSha256=d.digest(raw), afterSha256=d.digest(candidate),
            collectionGeneratedAt=data['generatedAt'], checkedAt=datetime.now(timezone.utc).isoformat(),
            routingUnchanged=True, accountStoreReadOrWritten=False)
        return report
    finally:
        if remote.read(runtime.path('.lock')) == lock:
            remote.remove_own(runtime.path('.lock'), lock)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['audit', 'publish'])
    parser.add_argument('--snapshot', type=Path, default=ROOT/'albums/snapshot.json')
    args = parser.parse_args()
    if args.action == 'audit':
        report = apply(json.loads(args.snapshot.read_text()))
    else:
        # Explicit maintenance of historical peak dates, not a scheduled hourly
        # collection. Existing pause variables, main-only gates and locks apply.
        from album_runtime import connection
        password = os.environ.pop('ISEGYE_SFTP_PASSWORD', '')
        with connection(password) as remote:
            report = patch_remote(remote)
    (ROOT/'guyso-peak-dates-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'records'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
