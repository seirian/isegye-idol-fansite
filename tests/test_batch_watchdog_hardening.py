"""Review-v2 guards: no live HTTP, account, credential or production access."""
from contextlib import redirect_stdout
from datetime import timedelta
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import batch_watchdog as w
from test_batch_watchdog_reliability import AT, ENV, run


class RunHistory(unittest.TestCase):
    def test_unfiltered_pagination_exceeds_filtered_search_ceiling(self):
        calls=[]
        rows=[run(i,minutes=120) for i in range(1,1002)]
        rows[-1].update(run_attempt=13,run_started_at=(AT-timedelta(minutes=3)).isoformat())
        def getter(endpoint):
            calls.append(endpoint)
            self.assertNotIn('branch=',endpoint)
            self.assertNotIn('created=',endpoint)
            page=int(endpoint.rsplit('page=',1)[1])
            return {'total_count':len(rows),'workflow_runs':rows[(page-1)*100:page*100]}
        result=w.workflow_runs('schedule-refresh.yml',getter)
        self.assertEqual(result[0]['id'],1001)
        self.assertEqual(len(calls),11)
        self.assertEqual(w.recovery_action(result,AT,w.due_slot('schedule',AT),False),'cooldown')

    def test_non_main_run_is_counted_for_paging_not_for_recovery(self):
        rows=[run(1,head_branch='feature',status='in_progress'),run(2)]
        result=w.workflow_runs('schedule-refresh.yml',lambda _: {'total_count':2,'workflow_runs':rows})
        self.assertEqual([r['id'] for r in result],[2])

    def test_listing_changes_fail_closed(self):
        getter=Mock(side_effect=[{'total_count':101,'workflow_runs':[run(i) for i in range(1,101)]},
                                 {'total_count':102,'workflow_runs':[run(101),run(102)]}])
        with self.assertRaisesRegex(ValueError,'changed'):
            w.workflow_runs('schedule-refresh.yml',getter)

    def test_duplicate_run_ids_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            w.workflow_runs('schedule-refresh.yml',lambda _: {'total_count':2,'workflow_runs':[run(),run()]})

    def test_latest_attempt_must_not_fall_back_to_creation(self):
        with self.assertRaisesRegex(ValueError,'Latest attempt'):
            w.started(run(run_attempt=2,run_started_at=None))

    def test_invalid_attempt_and_status_fail_closed(self):
        for changes in ({'run_attempt':0},{'run_attempt':True},{'status':'unknown'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                w.workflow_runs('schedule-refresh.yml',lambda _: {'total_count':1,'workflow_runs':[run(**changes)]})


class Evidence(unittest.TestCase):
    def report(self):
        return {'evidenceVersion':2,'verifiedReadback':True,'generatedAt':AT.isoformat(),
                'publishedAt':(AT+timedelta(seconds=1)).isoformat(),
                'readbackAt':(AT+timedelta(seconds=2)).isoformat()}

    def test_v2_requires_flag_and_all_ordered_clocks(self):
        value=self.report();due=w.due_slot('schedule',AT)
        self.assertTrue(w.schedule_readback_ok(value,due,AT))
        for field in ('verifiedReadback','generatedAt','publishedAt','readbackAt'):
            bad=copy.deepcopy(value);bad.pop(field)
            with self.subTest(field=field):self.assertFalse(w.schedule_readback_ok(bad,due,AT))
        value['readbackAt']=(AT-timedelta(seconds=1)).isoformat()
        self.assertFalse(w.schedule_readback_ok(value,due,AT))

    def test_v2_rejects_future_naive_and_unsupported_evidence(self):
        for changes in ({'readbackAt':(AT+timedelta(hours=1)).isoformat()},
                        {'publishedAt':'2026-11-15T14:22:00'},
                        {'evidenceVersion':3},{'evidenceVersion':True},{'verifiedReadback':False}):
            with self.subTest(changes=changes):
                self.assertFalse(w.schedule_readback_ok({**self.report(),**changes},w.due_slot('schedule',AT),AT))

    def test_legacy_is_compatible_but_not_an_explicit_flag(self):
        self.assertTrue(w.schedule_readback_ok({},w.due_slot('schedule',AT),AT))
        self.assertFalse(w.schedule_readback_ok({'verifiedReadback':False},w.due_slot('schedule',AT),AT))

    def archive(self,items):
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w') as z:
            for name,value in items:z.writestr(name,value)
        raw=buf.getvalue()
        r=run(kind='music',conclusion='success')
        entry={'id':7,'name':'daily-music-1-1','expired':False,'size_in_bytes':len(raw),
               'digest':'sha256:'+hashlib.sha256(raw).hexdigest(),
               'workflow_run':{'id':1,'head_sha':r['head_sha']}}
        return r,entry,raw

    def test_artifact_second_page_current_attempt_found(self):
        r,entry,raw=self.archive([('music-publication.json','{}')])
        old=[{'id':i+100,'name':'older','expired':True} for i in range(100)]
        def getter(endpoint,**kw):
            if kw.get('binary'):return raw
            return {'total_count':101,'artifacts':[entry] if 'page=2' in endpoint else old}
        self.assertEqual(w.artifact_files(r,'daily-music','music-daily.yml',getter),{'music-publication.json':{}})

    def test_incomplete_artifact_listing_does_not_allow_recollection(self):
        r,entry,raw=self.archive([('music-publication.json','{}')])
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            w.artifact_files(r,'daily-music','music-daily.yml',lambda *a,**kw:{'total_count':2,'artifacts':[entry]})

    def test_non_object_evidence_rejected(self):
        r,entry,raw=self.archive([('music-publication.json','[]')])
        with self.assertRaisesRegex(ValueError,'JSON object'):
            w.artifact_files(r,'daily-music','music-daily.yml',lambda *a,**kw:raw if kw.get('binary') else {'artifacts':[entry]})

    def test_archive_size_mismatch_rejected(self):
        r,entry,raw=self.archive([('music-publication.json','{}')]);entry['size_in_bytes']+=1
        with self.assertRaisesRegex(ValueError,'checksum'):
            w.artifact_files(r,'daily-music','music-daily.yml',lambda *a,**kw:raw if kw.get('binary') else {'artifacts':[entry]})

    def test_symlink_evidence_rejected(self):
        info=zipfile.ZipInfo('music-publication.json');info.create_system=3
        info.external_attr=(stat.S_IFLNK | 0o777)<<16
        r,entry,raw=self.archive([(info,'{}')])
        with self.assertRaises(ValueError):
            w.artifact_files(r,'daily-music','music-daily.yml',lambda *a,**kw:raw if kw.get('binary') else {'artifacts':[entry]})

    def test_expanded_evidence_aggregate_is_bounded(self):
        value=json.dumps({'padding':'a'*1000})
        r,entry,raw=self.archive([('music-publication.json',value),('albums-publication.json',value)])
        # Compressed bytes remain within limit while the approved expanded files do not.
        buf=io.BytesIO()
        with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED) as z:
            z.writestr('music-publication.json',value);z.writestr('albums-publication.json',value)
        raw=buf.getvalue();entry.update(size_in_bytes=len(raw),digest='sha256:'+hashlib.sha256(raw).hexdigest())
        with patch.object(w,'MAX_ARCHIVE',1500),self.assertRaisesRegex(ValueError,'expanded'):
            w.artifact_files(r,'daily-music','music-daily.yml',lambda *a,**kw:raw if kw.get('binary') else {'artifacts':[entry]})


class InspectionFailure(unittest.TestCase):
    def test_invalid_completion_records_failure_without_api_writes(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV,clear=True),\
             patch.object(w,'ROOT',Path(d)),patch.object(sys,'argv',['watchdog','--apply']),\
             patch.object(w,'require_trusted_completion',side_effect=ValueError('bad source')),\
             patch.object(w,'api') as api,redirect_stdout(io.StringIO()):
            self.assertEqual(w.main(),1)
            api.assert_not_called()
            report=json.loads((Path(d)/'batch-watchdog.json').read_text())
            self.assertEqual(report['state'],'inspection_failed')
            self.assertEqual(report['batches'],[])

    def test_incident_api_failure_is_not_green(self):
        with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,ENV,clear=True),\
             patch.object(w,'ROOT',Path(d)),patch.object(sys,'argv',['watchdog','--apply']),\
             patch.object(w,'recover_batch',return_value={'state':'healthy'}),\
             patch.object(w,'api',side_effect=RuntimeError('unavailable')),redirect_stdout(io.StringIO()):
            self.assertEqual(w.main(),1)
            self.assertEqual(json.loads((Path(d)/'batch-watchdog.json').read_text())['incidentError'],'RuntimeError')

if __name__=='__main__':unittest.main()
