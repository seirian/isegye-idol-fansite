"""Night-window, source timestamps, archive recovery and bounded retry regressions."""
from contextlib import contextmanager, nullcontext
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import errno
import hashlib
import json
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import album_hourly as hourly
import album_runtime as runtime
import album_observation_archive as archive
from test_albums_daily import complete_data, remote
import inour_sftp as d

class Hourly(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(runtime, 'night_deadline', side_effect=nullcontext))
        self.enterContext(patch.object(runtime, 'remaining', return_value=3600))
    def test_deadline_refuses_already_paused_window(self):
        with patch.object(hourly, 'remaining', return_value=0):
            with self.assertRaises(hourly.NightPause):
                with hourly.night_deadline():
                    self.fail('paused operation executed')
    def test_night_boundaries_and_week(self):
        for day in range(7):
            for hour in range(24):
                value=datetime(2026,11,8+day,hour,0,tzinfo=hourly.KST)
                self.assertEqual(hourly.allowed(value),not 1<=hour<7)
                self.assertEqual(hourly.allowed(value.astimezone(timezone.utc)),not 1<=hour<7)
        self.assertTrue(hourly.allowed(hourly.clock('2026-11-11T00:59:59+09:00')))
        self.assertFalse(hourly.allowed(hourly.clock('2026-11-11T01:00:00+09:00')))
        self.assertFalse(hourly.allowed(hourly.clock('2026-11-11T06:59:59+09:00')))
        self.assertTrue(hourly.allowed(hourly.clock('2026-11-11T07:00:00+09:00')))
    def test_midnight_budget(self):
        self.assertEqual(hourly.remaining(hourly.clock('2026-11-11T00:59:40+09:00')),20)
        self.assertEqual(hourly.remaining(hourly.clock('2026-11-11T06:59:59+09:00')),0)
        self.assertEqual(hourly.remaining(hourly.clock('2026-11-11T23:59:40+09:00')),3620)
    def doc(self):
        at=hourly.clock('2026-11-11T09:00:00+09:00')
        point={'at':at.isoformat(),'trackId':'123','rank':10,'status':'ranked'}
        data={'generatedAt':at.isoformat(),'tracks':{'x':{'melon':{'trackId':'123','albumId':'45'},
              'charts':{k:[deepcopy(point)] for k in hourly.KINDS}}},
              'domesticCharts':{k:{'state':'ok','updatedAt':at.isoformat(),'source':archive.SOURCES[k]} for k in hourly.KINDS}}
        return data,at
    def test_source_hour_not_generation_timestamp(self):
        data,at=self.doc()
        self.assertTrue(hourly.coverage(data,at)['currentComplete'])
        data['generatedAt']=(at+timedelta(hours=1)).isoformat()
        self.assertFalse(hourly.coverage(data,at+timedelta(hours=1))['currentComplete'])
    def test_missing_one_track_is_not_complete(self):
        data,at=self.doc();data['tracks']['y']={'melon':{'trackId':'456'},'charts':{}}
        self.assertFalse(hourly.coverage(data,at)['currentComplete'])
    def test_errors_and_fabricated_rank_not_counted(self):
        for mutation in ({'status':'error','rank':None},{'rank':0},{'rank':101},{'rank':True},{'trackId':'other'}):
            data,at=self.doc();data['tracks']['x']['charts']['melon_top100'][0].update(mutation)
            self.assertFalse(hourly.coverage(data,at)['currentComplete'])
    def test_out_of_chart_is_a_real_observation(self):
        data,at=self.doc()
        for kind in hourly.KINDS:data['tracks']['x']['charts'][kind][0].update(status='out',rank=None)
        self.assertTrue(hourly.coverage(data,at)['currentComplete'])
    def test_night_hours_excluded_from_gap_report(self):
        data,at=self.doc();report=hourly.coverage(data,at)
        for row in report['charts'].values():
            self.assertTrue(all(hourly.allowed(hourly.clock(v)) for v in row['missingSlots']))
    def test_recover_only_real_points_no_clock_changes(self):
        data,at=self.doc();candidate=deepcopy(data)
        for kind in hourly.KINDS:data['tracks']['x']['charts'][kind]=[]
        data['generatedAt']=(at-timedelta(hours=1)).isoformat();original=data['generatedAt']
        added,conflicts=archive.recover_points(data,candidate,at)
        self.assertEqual((added,conflicts),(2,0));self.assertEqual(data['generatedAt'],original)
        self.assertEqual(archive.recover_points(data,candidate,at),(0,0))
    def test_archive_identity_and_source_rejected(self):
        for mutate in (lambda d:d['tracks']['x']['melon'].update(trackId='wrong'),
                       lambda d:d['tracks']['x']['melon'].update(albumId='wrong'),
                       lambda d:[v.update(source='https://evil.invalid') for v in d['domesticCharts'].values()]):
            data,at=self.doc();candidate=deepcopy(data);mutate(candidate)
            for kind in hourly.KINDS:data['tracks']['x']['charts'][kind]=[]
            self.assertEqual(archive.recover_points(data,candidate,at),(0,0))
    def test_conflict_keeps_published_point(self):
        data,at=self.doc();candidate=deepcopy(data)
        for kind in hourly.KINDS:candidate['tracks']['x']['charts'][kind][0]['rank']=1
        self.assertEqual(archive.recover_points(data,candidate,at),(0,2))
        self.assertEqual(data['tracks']['x']['charts']['melon_top100'][0]['rank'],10)
    def test_archive_errors_future_and_old_not_accepted(self):
        data,at=self.doc();candidate=deepcopy(data)
        for kind in hourly.KINDS:candidate['tracks']['x']['charts'][kind][0].update(status='error',rank=None)
        self.assertEqual(archive.recover_points(data,candidate,at),(0,0))
        for delta in (-timedelta(days=3),timedelta(minutes=1)):
            candidate['generatedAt']=(at+delta).isoformat()
            with self.assertRaises(ValueError):archive.recover_points(data,candidate,at)
    def test_archive_digest_and_duplicate_members(self):
        buf=BytesIO()
        with zipfile.ZipFile(buf,'w') as z:z.writestr('albums/snapshot.json','{}')
        with self.assertRaises(ValueError):archive.read_snapshot(buf.getvalue(),'sha256:'+'0'*64)
    def test_no_auth_to_other_hosts(self):
        with self.assertRaises(ValueError):archive.request('https://example.invalid/',token='synthetic')
    def test_no_network_or_sleep_at_night(self):
        factory=unittest.mock.Mock()
        result=runtime.execute('restore','synthetic',factory=factory,permitted=lambda:False)
        self.assertEqual(result['status'],'paused');factory.assert_not_called()
        with patch.object(hourly,'allowed',return_value=False),patch.object(hourly,'command') as command:
            self.assertEqual(hourly.collect()['status'],'paused');command.assert_not_called()
    def test_connect_retry_is_bounded_and_keeps_password(self):
        count=[];delays=[]
        @contextmanager
        def connect(password,progress):
            count.append(password);progress['stage']='connect'
            raise TimeoutError('private connection details must not be logged')
            yield
        result=runtime.execute('restore','synthetic',factory=connect,sleeper=delays.append,permitted=lambda:True)
        self.assertEqual(count,['synthetic']*3);self.assertEqual(delays,[5,15])
        self.assertEqual(result['failedStage'],'connect')
        self.assertNotIn('private connection details',json.dumps(result))
    def test_security_failures_never_retried(self):
        for exc in (d.Stop('Host key mismatch'),PermissionError('Denied'),ValueError('Bad data')):
            attempts=[]
            @contextmanager
            def connect(password,progress):
                attempts.append(1);raise exc;yield
            result=runtime.execute('restore','synthetic',factory=connect,permitted=lambda:True)
            self.assertEqual(len(attempts),1);self.assertEqual(result['status'],'failed')
    def test_transient_classification(self):
        self.assertTrue(runtime.transient(OSError(errno.ECONNRESET,'reset')))
        self.assertFalse(runtime.transient(OSError(errno.EACCES,'denied')))
    def test_newer_published_generation_not_overwritten(self):
        r=remote();data=complete_data();runtime.publish(r,data)
        before=r.read(runtime.path('current.json'))
        data['generatedAt']=(hourly.clock(data['generatedAt'])-timedelta(seconds=10)).isoformat()
        with self.assertRaises(d.Stop):runtime.publish(r,data)
        self.assertEqual(r.read(runtime.path('current.json')),before)
        self.assertNotIn(runtime.path('.lock'),r.files)
    def test_orphaned_own_lock_recoverable_not_foreign(self):
        r=remote();data=complete_data();runtime.publish(r,data)
        token=b'synthetic-owner-token';r.files[runtime.path('.lock')]=token
        result=runtime.publish(r,data,{'lock':token})
        self.assertTrue(result['verifiedReadback']);self.assertNotIn(runtime.path('.lock'),r.files)
        r.files[runtime.path('.lock')]=b'foreign'
        with self.assertRaises(d.Stop):runtime.publish(r,data,{'lock':token})
        self.assertEqual(r.files[runtime.path('.lock')],b'foreign')
    def test_successful_retry_publishes_identical_candidate(self):
        r=remote();data=complete_data();attempts=[]
        @contextmanager
        def connect(password,progress):
            attempts.append(password)
            if len(attempts)==1:
                progress['stage']='connect';raise TimeoutError()
            yield r
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'albums').mkdir();(root/'albums/snapshot.json').write_text(json.dumps(data))
            # Only the candidate read uses this mock root; core uses the real assets.
            with patch.object(runtime,'ROOT',root),patch.object(runtime,'publish',return_value={'status':'published','verifiedReadback':True}) as publish:
                result=runtime.execute('publish','synthetic',factory=connect,sleeper=lambda _:None,permitted=lambda:True)
                self.assertEqual(result['status'],'published');self.assertEqual(len(attempts),2)
                self.assertEqual(publish.call_args.args[1]['generatedAt'],data['generatedAt'])
    def test_workflow_archives_before_publish_and_isolates_credentials(self):
        text=(ROOT/'.github/workflows/albums-daily.yml').read_text()
        self.assertLess(text.index('Archive collected observations'),text.index('Atomically publish'))
        for name in ('Collect registered albums','Recover verified observations'):
            block=text.split('      - name: '+name)[1].split('      - name:')[0]
            self.assertNotIn('SFTP_PASSWORD',block)
        self.assertIn('scripts/album_hourly.py gate',text)
        self.assertIn('steps.due.outputs.needed',text)
        self.assertNotIn('continue-on-error',text)

if __name__=='__main__':unittest.main()
