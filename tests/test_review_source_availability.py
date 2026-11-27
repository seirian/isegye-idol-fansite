"""Execute the generated adapter, including dependencies of source labels."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from build_review_2nd import production_adapter


class ReviewSourceAvailabilityTests(unittest.TestCase):
    def test_adapter_executes_available_unavailable_and_unknown_source_labels(self):
        # Only the unused page sections are minimal fixtures. Source labels and
        # their dependency come from the real baseline renderer, then pass
        # through the same extraction used by review and production builds.
        source = (ROOT/'catalog/video-ui.js').read_text().splitlines()
        labels = '\n'.join(line for line in source if line.startswith((
            'const MUSIC_VIDEO_LABELS=', 'function musicVideoBlocked(', 'function musicVideoLabel(')))
        catalog = {'music': {'songs': [
            {'id': 'available', 'videoSource': {'kind': 'fan_backup', 'availability': 'available'}},
            {'id': 'unavailable', 'videoSource': {'kind': 'fan_backup', 'availability': 'unavailable'}},
            {'id': 'unknown', 'videoSource': {'kind': 'fan_backup', 'availability': 'unknown'}}]}}
        app = '''const drawings={};
let storage;
const badge=()=>'';
const saveButton=()=>'';
function shell(){}
const liveMonitor={};
function liveHomeView(){return '';}
function liveView(){return '';}
function liveMount(){}
const CATALOG='''+json.dumps(catalog)+''';
'''+labels+'''
const catalogProfiles=new Map();
function catalogMembersView(){return '';}
function catalogMemberView(id){return musicVideoLabel(CATALOG.music.songs.find(s=>s.id===id));}
function catalogMusicView(params){}
function visualLiveThumbnail(){}
const HISTORY_TYPES={};
function visualLiveArt(){}
function historyLink(){}
'''
        with tempfile.TemporaryDirectory() as temporary:
            baseline = Path(temporary)
            (baseline/'src').mkdir()
            (baseline/'src/app.js').write_text(app)
            (baseline/'src/lib.js').write_text('export const escapeHtml=String;\n')
            (baseline/'src/data.js').write_text('export const MEMBERS=[];\n')
            (baseline/'src/portraits.js').write_text('export const PORTRAITS={};\n')
            adapter = production_adapter(baseline)
        result = subprocess.run(['node', '-e',
            "const vm=require('node:vm');const fs=require('node:fs');"
            "process.stdout.write(vm.runInNewContext(fs.readFileSync(0,'utf8')+"
            "'\\nJSON.stringify([ProductionUI.member(\"available\"),ProductionUI.member(\"unavailable\"),ProductionUI.member(\"unknown\")])'));"],
            input=adapter, text=True, capture_output=True, check=True)
        available, unavailable, unknown = json.loads(result.stdout)
        self.assertIn('팬 백업', available)
        self.assertNotIn('영상 확인 불가', available)
        self.assertIn('영상 확인 불가', unavailable)
        self.assertIn('영상 확인 불가', unknown)


if __name__ == '__main__':
    unittest.main()
