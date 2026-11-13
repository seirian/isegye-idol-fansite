"""No external requests or production writes. Test the actual album batch boundary."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'scripts'))
import album_releases as releases
import daily_albums as daily
import album_runtime as runtime
import inour_sftp as d
from test_schedule_feed import FeedRemote, OLD
from prepare_album_release import prepare

NOW=lambda: datetime.now(timezone.utc).isoformat()

def complete_data():
    prepare()
    data=json.loads((ROOT/'albums/release-seed/snapshot.json').read_text())
    data['generatedAt']=NOW(); data['feed']='daily-albums'
    for kind in daily.KINDS:
        data['domesticCharts'][kind].update(state='ok',checkedAt=data['generatedAt'],updatedAt=data['generatedAt'])
    for row in data['tracks'].values():
        if row.get('melon',{}).get('state')=='ok':row['melon']['checkedAt']=data['generatedAt']
    cover=next(iter(data['assets']['covers']))
    for album in releases.releases():
        for i,track in enumerate(album['tracks']):
            data['tracks'][track['id']]={'match':'unmatched','appleHistory':[],
                'melon':{'state':'ok','albumId':album['melonAlbumId'],'trackId':str(10000000+i),
                    'album':album['title'],'title':track['title'],'artist':'이세계아이돌 (ISEGYE IDOL)',
                    'checkedAt':data['generatedAt']},
                'artwork':{'asset':cover,'provider':'melon'}}
    return data

def remote():
    result=FeedRemote()
    result.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=json.dumps({
        'dailyAlbums':{'schemaVersion':1,'catalogTrackIds':sorted(s['id'] for s in releases.load_catalog()['songs'])}}).encode()
    return result

class AlbumsDaily(unittest.TestCase):
    def test_release_has_five_ordered_tracks_and_sources(self):
        rows=releases.load_catalog()['songs']; added=[s for s in rows if s['album']=='Across Dimensions']
        self.assertEqual(len(rows),26); self.assertEqual(len(added),5)
        self.assertEqual([s['title'] for s in added],added[0]['albumTracks'])
        self.assertTrue(all(s['date']=='2026-11-09' and s['dateKind']=='발매일' for s in added))
        from enhance_catalog import load_music
        bound={s['id']:s for s in releases.extend_music(load_music())['songs']}
        for song in added:
            self.assertEqual(bound[song['id']]['videoId'],song['videoId'])
            self.assertEqual(bound[song['id']]['videoSource']['channelUrl'],'https://www.youtube.com/@isegyeidol_ofcl')
            self.assertEqual(bound[song['id']]['videoSource']['checkedAt'],releases.releases()[0]['checkedAt'])
    def test_production_composition_preserves_originals_and_daily_music_deduplication(self):
        from enhance_catalog import load_music
        base=load_music();music=releases.extend_music(base)
        self.assertEqual(music['songs'][:len(base['songs'])],base['songs'])
        self.assertEqual(len(music['songs']),159)
        data={'songs':[], 'albums':[], 'videos':[{'id':'untouched'}]}
        composed=releases.compose_review(data,music)
        self.assertEqual(len(composed['songs']),5);self.assertEqual(len(composed['albums']),1)
        self.assertEqual(composed['videos'],data['videos'])
        self.assertTrue(all(s['albumId']==composed['albums'][0]['id'] for s in composed['songs']))
        with self.assertRaises(ValueError):releases.extend_music(music)
    def test_complete_health_and_optional_failure(self):
        doc=complete_data(); self.assertEqual(daily.health(doc)['state'],'complete')
        doc['providers']['bugs']['state']='error'
        report=daily.health(doc); self.assertEqual(report['state'],'complete'); self.assertIn('bugs:error',report['optionalWarnings'])
    def test_missing_peak_source_is_visible_but_not_publication_blocking(self):
        doc=complete_data()
        report=daily.health(doc)
        self.assertEqual(report['state'],'complete')
        self.assertIn('peak-source:rebels:unverified',report['optionalWarnings'])
    def test_wrong_album_identity_and_missing_tracks_fail(self):
        doc=complete_data();doc['tracks']['rebels']['melon']['albumId']='1'
        self.assertIn('identity:rebels',daily.health(doc)['incompleteRequired'])
        del doc['tracks']['rebels']
        with self.assertRaises(ValueError):daily.validate(doc,exact=True)
    def test_chart_error_is_not_success_or_zero(self):
        doc=complete_data();doc['domesticCharts']['melon_top100']['state']='error'
        self.assertIn('melon_top100',daily.health(doc)['incompleteRequired'])
    def test_previous_evidence_keeps_original_timestamp_and_error_gap(self):
        previous=complete_data();old=deepcopy(previous['tracks']['rebels']['melon'])
        result=deepcopy(previous); result['tracks']['rebels']={'melon':{'state':'unmatched'},'youtube':{'state':'error'}}
        daily.preserve(previous,result)
        row=result['tracks']['rebels']['melon']
        self.assertEqual(row['checkedAt'],old['checkedAt']);self.assertEqual(row['fetchState'],'error')
        self.assertIn('melon:rebels',daily.health(result)['incompleteRequired'])
        point=result['tracks']['rebels']['charts']['melon_top100'][-1]
        self.assertEqual(point['status'],'error');self.assertIsNone(point['rank'])
    def test_asset_paths_and_brand_keys_fail_closed(self):
        for path in ('../../.auth-private/config.json','albums/asset-cache/other.webp'):
            doc=complete_data();next(iter(doc['assets']['covers'].values()))['path']=path
            with self.assertRaises(ValueError):daily.asset_entries(doc)
        doc=complete_data();doc['assets']['brands']['__proto__']=next(iter(doc['assets']['brands'].values()))
        with self.assertRaises(ValueError):daily.asset_entries(doc)
    def test_stale_evidence_is_not_relabelled_fresh(self):
        doc=complete_data();doc['tracks']['rebels']['melon']['checkedAt']=(datetime.now(timezone.utc)-timedelta(hours=4)).isoformat()
        self.assertIn('melon:rebels',daily.health(doc)['incompleteRequired'])
        doc=complete_data();doc['domesticCharts']['melon_hot100']['updatedAt']=(datetime.now(timezone.utc)-timedelta(hours=4)).isoformat()
        self.assertIn('melon_hot100',daily.health(doc)['incompleteRequired'])
    def test_hot100_official_night_pause_is_not_a_fresh_rank(self):
        observed=datetime.fromisoformat('2026-11-10T06:00:00+09:00')
        chart={'state':'ok','source':daily.HOT100_SOURCE,
            'checkedAt':observed.isoformat(),'updatedAt':'2026-11-10T01:00:00+09:00'}
        self.assertTrue(daily.hot100_night_pause(chart,observed))
        self.assertEqual(chart['updatedAt'],'2026-11-10T01:00:00+09:00')
        for change in ({'updatedAt':'2026-11-09T01:00:00+09:00'},
                       {'updatedAt':'2026-11-10T02:00:00+09:00'},
                       {'updatedAt':'2026-11-10T01:30:00+09:00'},
                       {'checkedAt':'2026-11-10T02:00:00+09:00'},
                       {'state':'error'},{'source':'https://example.invalid/'}):
            self.assertFalse(daily.hot100_night_pause(chart|change,observed))
        self.assertFalse(daily.hot100_night_pause(chart,datetime.fromisoformat('2026-11-10T07:13:00+09:00')))
        doc=complete_data();doc['generatedAt']=observed.isoformat()
        doc['domesticCharts']['melon_hot100']=chart
        report=daily.health(doc)
        self.assertNotIn('melon_hot100',report['incompleteRequired'])
        self.assertEqual(report['scheduledSourcePauses'][0]['lastPublishedAt'],chart['updatedAt'])
    def test_stale_run_refused(self):
        doc=complete_data();doc['generatedAt']=(datetime.now(timezone.utc)-timedelta(hours=3)).isoformat()
        with self.assertRaises(ValueError):daily.validate(doc,exact=True,fresh=True)
    def test_atomic_publication_idempotence_and_backup(self):
        r=remote();doc=complete_data();result=runtime.publish(r,doc)
        self.assertTrue(result['verifiedReadback']);self.assertEqual(result['totalTracks'],26)
        old=r.read(runtime.path('current.json'));self.assertEqual(runtime.publish(r,doc)['sha256'],result['sha256'])
        doc['generatedAt']=NOW();runtime.publish(r,doc)
        self.assertEqual(r.read(runtime.path('previous.json')),old)
        self.assertTrue(all(name.startswith(runtime.DIR+'/') for name in r.writes))
        self.assertNotIn(runtime.path('.lock'),r.files)
        self.assertEqual(r.mode[runtime.path('current.json')],0o600)
    def test_incomplete_run_preserves_previous_feed(self):
        r=remote();doc=complete_data();runtime.publish(r,doc);old=r.read(runtime.path('current.json'))
        doc['domesticCharts']['melon_hot100']['state']='error'
        with self.assertRaises(d.Stop):runtime.publish(r,doc)
        self.assertEqual(r.read(runtime.path('current.json')),old)
    def test_foreign_lock_and_unsafe_paths_not_removed(self):
        r=remote();doc=complete_data();runtime.publish(r,doc);r.files[runtime.path('.lock')]=b'other'
        with self.assertRaises(d.Stop):runtime.publish(r,doc)
        self.assertEqual(r.files[runtime.path('.lock')],b'other')
        for name in ('../../.auth-private/config.json','/web/.htaccess','assets/../current.json'):
            with self.assertRaises(d.Stop):runtime.path(name)
    def test_old_runtime_and_concurrent_deploy_refused(self):
        r=remote();r.files[d.ROOT+'/_isegye_releases/'+OLD+'/build-info.json']=b'{}'
        with self.assertRaises(d.Stop):runtime.publish(r,complete_data())
        self.assertFalse(r.writes)
        r=remote();r.dirs.add(d.ROOT+'/.deploy-lock')
        with self.assertRaises(d.Stop):runtime.publish(r,complete_data())
    def test_generated_gateway_keeps_access_gate_and_approved_sources(self):
        import build_albums_host as host, promote_albums
        source=(ROOT/'auth/Gateway.php').read_text();generated=host.patched(source)
        self.assertLess(generated.index("if (!$access['allowed'])"),generated.index("$path === '/api/albums'"))
        self.assertEqual((ROOT/'auth/Gateway.php').read_text(),source)
        self.assertTrue(promote_albums.approval()['operatorApprovedDeployment'])
    def test_workflow_does_not_run_collectors_with_sftp_credentials(self):
        text=(ROOT/'.github/workflows/albums-daily.yml').read_text()
        block=text.split('      - name: Collect registered albums')[1].split('      - name:')[0]
        self.assertNotIn('SFTP_PASSWORD',block)
        self.assertIn("cron: '0 0-15,22-23 * * *'",text)
        self.assertIn('runs-on: ubuntu-24.04',text)
        self.assertNotIn('continue-on-error',text)

if __name__=='__main__':unittest.main()
