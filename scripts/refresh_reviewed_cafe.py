"""Bounded credential-free public review before the hourly publisher.

Uses only the existing two approved boards and same-author roundup series. No
login, direct Cafe API fetch, comments, general-user posts or raw bodies retained.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import os
import cafe_batch as cb
from cafe_runtime import validate_packet


def run(start=None):
    now = datetime.now(timezone.utc)
    # Three completed KST days plus today catches delayed posts and temporary outages.
    start = start or (now.astimezone(cb.KST).date() - timedelta(days=3)).isoformat()
    import review_cafe_window
    import review_fan_series
    import review_fan_cards
    from pack_cafe_window import pack
    try:
        board = review_cafe_window.run(start)
    except Exception:
        board = {'schemaVersion': 1, 'from': start, 'checkedAt': now.isoformat(),
                 'boards': {str(m): {'state': 'unverified', 'reason': 'public_browser_unavailable'} for m in cb.IDS},
                 'notices': [], 'fan': {}}
    try:
        fans = review_fan_series.run(start)
    except Exception:
        fans = {'verified': [], 'state': 'unverified', 'checkedAt': datetime.now(timezone.utc).isoformat()}
    try:
        cards = review_fan_cards.read(fans.get('verified', []))
    except Exception:
        cards = {'cards': {}, 'checkedAt': datetime.now(timezone.utc).isoformat()}
    packet = pack(board, fans, cards)
    validate_packet(packet, datetime.now(timezone.utc).isoformat())
    return packet


if __name__ == '__main__':
    if os.getenv('PRODUCTION_PAUSED') == 'true' or os.getenv('ISEGYE_SCHEDULE_PAUSED') == 'true':
        raise SystemExit('Collection paused')
    # SFTP / authentication credentials must not enter the public browser process.
    if os.getenv('ISEGYE_SFTP_PASSWORD') or os.getenv('ISEGYE_GOOGLE_CLIENT_ID'):
        raise SystemExit('Public review must run without deployment credentials')
    packet = run()
    Path('cafe-window.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'from': packet['from'], 'checkedAt': packet['checkedAt'], 'boards': packet['boards'],
                      'fanReferences': len(packet.get('fanSeries', []))}, ensure_ascii=False))
