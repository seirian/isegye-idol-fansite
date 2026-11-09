"""Audit just the reviewed release bindings; public metadata and thumbnails only."""
import json
from pathlib import Path
import check_music_video_sources as audit
from album_releases import releases, video_bindings
from collect_album_domestic import norm
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    original=audit.selections
    audit.selections=lambda: (original()[0],video_bindings())
    audit.main()
    report=json.loads((ROOT/'test-results/music-sources/source-audit.json').read_text())
    expected={t['id']:t for r in releases() for t in r['tracks']}
    assert set(expected)=={r['songId'] for r in report['results']},'Missing release video audit'
    for result in report['results']:
        row=expected[result['songId']]
        assert any(norm(t) in norm(result['title']) for t in [row['title'],*row.get('aliases',[])]),'Release video title mismatch'
    print(json.dumps({'releaseVideoCount':len(expected),'uploaderTitleAndThumbnailVerified':True}))
