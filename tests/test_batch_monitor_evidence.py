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
        with patch.object(m,'listing',return_value=([self.run],True)),patch.object(m.policy,'artifact_files',return_value=files or {}),patch.object(m,'extra_artifact',return_value=extra or {}):
            return m.inspect(kind,self.at,'a'*40,lambda path:{'jobs':[],'total_count':0})
    def test_green_execution_without_publication_not_green(self):
        row=self.project('music')
        self.assertEqual(row['run']['conclusion'],'success')
        self.assertEqual(row['dataState'],'attention')
    def test_catalog_does_not_claim_publication(self):
        self.assertEqual(self.project('catalog')['dataState'],'unknown')
    def test_production_requires_current_commit_and_verification(self):
        report={'status':'deployed_and_verified','commit':'a'*40,'browserVerified':True,'privatePathsBlocked':True}
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
