"""End-to-end projection decisions with synthetic, explicit evidence only."""
from pathlib import Path
from datetime import timedelta
import sys,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import batch_monitor_snapshot as m

class EvidenceDecisions(unittest.TestCase):
    def setUp(self):
        self.at=m.stamp('2026-11-17T03:30:00Z')
        self.run={'id':42,'run_attempt':1,'head_sha':'a'*40,'status':'completed','conclusion':'success',
                  'created_at':'2026-11-17T03:10:00Z','run_started_at':'2026-11-17T03:10:00Z'}
    def project(self,kind,files=None,extra=None):
        with patch.object(m,'listing',return_value=([self.run],True)),patch.object(m.policy,'artifact_files',return_value=files or {}),patch.object(m,'extra_artifact',return_value=extra or {}),patch.object(m,'read_production_evidence',return_value=(extra or {},self.run,{})):
            return m.inspect(kind,self.at,'a'*40,lambda path:{'jobs':[],'total_count':0})
    def test_green_execution_without_publication_not_green(self):
        row=self.project('music')
        self.assertEqual(row['run']['conclusion'],'success')
        self.assertEqual(row['dataState'],'attention')
    def test_catalog_does_not_claim_publication(self):
        self.assertEqual(self.project('catalog')['dataState'],'unknown')
    def test_production_requires_current_commit_and_verification(self):
        report={'status':'deployed_and_verified','commit':'a'*40,'browserVerified':True,'privatePathsBlocked':True,'protectedFilesUnchanged':True,
                'lockRemoved':True,'checkedAt':'2026-11-17T03:11:00Z','verifiedAt':'2026-11-17T03:20:00Z'}
        self.assertEqual(self.project('production',extra=report)['dataState'],'healthy')
        report['commit']='b'*40
        self.assertEqual(self.project('production',extra=report)['dataState'],'attention')
        report['commit']='a'*40;report['browserVerified']=False
        self.assertEqual(self.project('production',extra=report)['dataState'],'attention')
    def test_broken_archive_never_green(self):
        with patch.object(m,'listing',return_value=([self.run],True)),patch.object(m.policy,'artifact_files',side_effect=ValueError):
            self.assertEqual(m.inspect('music',self.at,'a'*40,lambda path:{'jobs':[],'total_count':0})['dataState'],'unknown')
    def test_watchdog_unknown_state_not_green(self):
        for value in (None,'unrecognized','success'):
            self.assertEqual(m.watchdog_state({'checkedAt':m.iso(self.at),'state':value},self.at),'unknown')
    def test_watchdog_checked_requires_all_known_rows(self):
        report={'checkedAt':m.iso(self.at),'state':'checked','batches':[]}
        self.assertEqual(m.watchdog_state(report,self.at),'unknown')
        report['batches']=[{'batch':k,'state':'healthy'} for k in m.policy.SPECS]
        self.assertEqual(m.watchdog_state(report,self.at),'healthy')
        report['batches'][0]['state']='dispatched'
        self.assertEqual(m.watchdog_state(report,self.at),'unknown')
    def test_watchdog_paused_and_pending_not_green(self):
        for value,expected in [('paused','paused'),('pending','running'),('attention','attention'),('inspection_failed','attention')]:
            self.assertEqual(m.watchdog_state({'checkedAt':m.iso(self.at),'state':value},self.at),expected)
    def test_watchdog_stale_future_not_green(self):
        for checked in (self.at-timedelta(minutes=46),self.at+timedelta(minutes=3)):
            self.assertEqual(m.watchdog_state({'checkedAt':m.iso(checked),'state':'paused'},self.at),'unknown')
    def test_partial_listing_skips_publication_assertion(self):
        with patch.object(m,'listing',return_value=([self.run],False)),patch.object(m.policy,'artifact_files') as proof:
            row=m.inspect('music',self.at,'a'*40,lambda path:{'jobs':[],'total_count':0})
            self.assertEqual(row['dataState'],'unknown');proof.assert_not_called()

if __name__=='__main__':unittest.main()

class CatalogPublication(unittest.TestCase):
    def setUp(self):
        from test_batch_monitor import fixture_snapshot
        from refresh_catalog_videos import channels
        import hashlib,json
        self.at=m.stamp('2026-11-17T03:30:00Z');self.doc=fixture_snapshot(self.at)
        self.production=next(r for r in self.doc['batches'] if r['key']=='production')
        self.production['dataState']='healthy';self.production['evidenceRun']['commit']='a'*40
        self.catalog=next(r for r in self.doc['batches'] if r['key']=='catalog')
        self.catalog['paused']=False
        self.evidence={'schemaVersion':1,'mode':'production','buildCommit':'a'*40,'publicationClaimed':False,
            'sourceAt':m.iso(self.at-m.timedelta(minutes=20)),'builtAt':m.iso(self.at-m.timedelta(minutes=10)),
            'sources':[{'name':c['key'],'state':'ok','lastSuccessAt':m.iso(self.at-m.timedelta(minutes=20)),
                        'historicalComplete':True} for c in channels()], 'channelCount':22,'videoCount':100}
        self.publication={'catalogBundleVerified':True,'verifiedAt':m.iso(self.at-m.timedelta(minutes=5))}
    def project(self):
        import hashlib,json
        self.publication.setdefault('catalogEvidenceSha256',hashlib.sha256((json.dumps(self.evidence,ensure_ascii=False,sort_keys=True)+'\n').encode()).hexdigest())
        def artifact(getter,run,prefix,name):return self.publication if name=='auth-deployment.json' else self.evidence
        with patch.object(m,'extra_artifact',side_effect=artifact):m.attach_catalog_publication(self.doc,self.at,None)
        return self.catalog
    def test_current_built_and_deployed_catalog_verified(self):
        row=self.project();self.assertEqual(row['dataState'],'healthy');self.assertEqual(len(row['sources']),22)
    def test_missing_channel_cannot_claim_complete(self):
        self.evidence['sources'].pop();self.assertEqual(self.project()['dataState'],'unknown')
    def test_old_source_not_concealed_by_new_deployment(self):
        self.evidence['sources'][0]['lastSuccessAt']='2026-11-15T00:00:00Z'
        self.assertEqual(self.project()['dataState'],'attention')
    def test_modified_report_hash_not_trusted(self):
        self.publication['catalogEvidenceSha256']='0'*64
        self.assertEqual(self.project()['dataState'],'unknown')
    def test_wrong_commit_not_trusted(self):
        self.evidence['buildCommit']='b'*40;self.assertEqual(self.project()['dataState'],'unknown')
    def test_built_after_deployed_not_trusted(self):
        self.evidence['builtAt']=m.iso(self.at);self.assertEqual(self.project()['dataState'],'unknown')
    def test_failed_deployment_does_not_claim_catalog_success(self):
        self.production['dataState']='unknown';self.assertEqual(self.project()['dataState'],'unknown')
