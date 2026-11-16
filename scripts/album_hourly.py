"""KST operating window, source-clock coverage and bounded album collection.

No credentials are used here. 01:00 <= KST < 07:00 is an intentional pause.
A watchdog is a no-op once both source charts for the current hour are published.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import json
import os
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
UTC = timezone.utc
KINDS = ('melon_top100', 'melon_hot100')
CRON = '0 0-15,22-23 * * *'
WATCHDOG_CRON = '20,40 0-15,22-23 * * *'
POLICY = 'KST 00:00 and 07:00-23:00 hourly; paused 01:00-06:59'

def now():
    return datetime.now(UTC)

def clock(value):
    value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if value.tzinfo is None:
        raise ValueError('Missing timezone')
    return value.astimezone(UTC)

def allowed(at=None):
    return not 1 <= (at or now()).astimezone(KST).hour < 7

def slot(at):
    return at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)

def remaining(at=None):
    local = (at or now()).astimezone(KST)
    if not allowed(local):
        return 0
    end = (local if local.hour == 0 else local + timedelta(days=1)).replace(hour=1, minute=0, second=0, microsecond=0)
    return max(0, int((end-local).total_seconds()))

class NightPause(RuntimeError):
    pass

@contextmanager
def night_deadline():
    """Abort an operation that crosses into the paused window on Linux runners."""
    budget = remaining()
    if budget <= 0:
        raise NightPause('Scheduled night pause')
    previous = signal.getsignal(signal.SIGALRM)
    def stop(signum, frame):
        raise NightPause('Scheduled night pause')
    signal.signal(signal.SIGALRM, stop)
    signal.setitimer(signal.ITIMER_REAL, budget)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)

def coverage(data, at=None, hours=24):
    """Only verified source hours count. Never count the intentional night pause."""
    at = at or now()
    current = slot(at)
    expected = [current-timedelta(hours=i) for i in reversed(range(hours)) if allowed(current-timedelta(hours=i))]
    rows = {}
    for kind in KINDS:
        chart = data.get('domesticCharts', {}).get(kind, {})
        observed = set()
        # An hour counts only if every registered Melon track has a valid observation.
        histories = []
        for item in data.get('tracks', {}).values():
            ident = item.get('melon', {}).get('trackId')
            if not ident:
                continue
            stamps = set()
            for point in item.get('charts', {}).get(kind, []):
                try:
                    stamp = clock(point['at'])
                    rank = point.get('rank')
                    valid = ((point.get('status') == 'ranked' and type(rank) is int and 1 <= rank <= 100)
                             or (point.get('status') == 'out' and rank is None))
                    if valid and point.get('trackId') == ident and stamp == slot(stamp) and stamp <= at+timedelta(minutes=10):
                        stamps.add(stamp)
                except (ValueError, TypeError, KeyError, AttributeError):
                    continue
            histories.append(stamps)
        if histories:
            observed = set.intersection(*histories)
        try:
            updated = clock(chart['updatedAt'])
            current_ok = chart.get('state') == 'ok' and updated == current and current in observed
        except (ValueError, TypeError, KeyError, AttributeError):
            current_ok = False
        rows[kind] = {'sourceAt': chart.get('updatedAt'), 'current': current_ok,
                      'missingSlots': [t.isoformat() for t in expected if t not in observed]}
    return {'checkedAt': at.isoformat(), 'slot': current.isoformat(), 'policy': POLICY,
            'paused': not allowed(at), 'currentComplete': all(r['current'] for r in rows.values()),
            'charts': rows, 'scopeHours': hours}

def write_report(name, data):
    (ROOT/name).write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(data, ensure_ascii=False))

def command(args, max_seconds):
    # A delayed midnight run must not keep collecting after 01:00 KST.
    budget = min(max_seconds, remaining())
    if budget <= 0:
        raise TimeoutError('Scheduled night pause')
    process = subprocess.Popen(args, cwd=ROOT, start_new_session=True)
    try:
        code = process.wait(timeout=budget)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        raise TimeoutError('Collection budget or night boundary') from None
    if code:
        raise RuntimeError('Collector failed')

def collect(attempts=3):
    if not allowed():
        return {'status': 'paused', 'policy': POLICY}
    command([sys.executable, 'scripts/check_album_release_videos.py'], 90)
    history = []
    for attempt in range(1, attempts+1):
        if not allowed():
            return {'status': 'paused', 'policy': POLICY, 'attempts': history}
        try:
            command([sys.executable, 'scripts/daily_albums.py'], 300)
            from daily_albums import validate, health
            data = validate(json.loads((ROOT/'albums/snapshot.json').read_text()), exact=True, fresh=True)
            current = coverage(data)
            data['hourlyCoverage'] = current
            (ROOT/'albums/snapshot.json').write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))+'\n')
            good = health(data)['state'] == 'complete' and current['currentComplete']
            history.append({'attempt': attempt, 'at': now().isoformat(), 'complete': good})
            write_report('albums-coverage.json', current)
            if good:
                return {'status': 'collected', 'attempts': history, 'sourceSlots': current['charts']}
        except (RuntimeError, TimeoutError) as exc:
            history.append({'attempt': attempt, 'at': now().isoformat(), 'error': type(exc).__name__})
        if attempt < attempts and remaining() > 20:
            time.sleep(20)
    return {'status': 'failed', 'error': 'Current-hour mandatory chart not verified', 'attempts': history}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('gate', 'decide', 'collect', 'report'))
    args = parser.parse_args()
    if args.action == 'gate':
        good = allowed()
        result = {'status': 'allowed' if good else 'paused', 'allowed': good, 'checkedAt': now().isoformat(), 'policy': POLICY}
        if os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                out.write('allowed='+str(good).lower()+'\n')
        write_report('albums-gate.json', result)
        return 0
    if args.action in ('decide', 'report'):
        data = json.loads((ROOT/'albums/snapshot.json').read_text())
        result = coverage(data)
        recovery_path = ROOT/'albums-recovery.json'
        recovered = json.loads(recovery_path.read_text()).get('addedPoints', 0) if recovery_path.is_file() else 0
        needed = allowed() and (not result['currentComplete'] or recovered > 0)
        result['needsCollection'] = needed
        write_report('albums-coverage.json', result)
        if args.action == 'decide' and os.getenv('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'], 'a') as out:
                out.write('needed='+str(needed).lower()+'\n')
        return 0
    result = collect()
    write_report('albums-collection.json', result)
    return int(result['status'] == 'failed')

if __name__ == '__main__':
    raise SystemExit(main())
