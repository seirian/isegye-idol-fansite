from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import production_lock_recovery_request as request


class RecoveryRequestTests(unittest.TestCase):
    def setUp(self):
        self.env={'GITHUB_REPOSITORY':request.REPO,'GITHUB_REF':'refs/heads/main',
                  'GITHUB_JOB':'recover','GITHUB_RUN_ID':'100','GITHUB_RUN_ATTEMPT':'2',
                  'GITHUB_SHA':'a'*40,'ALLOW_RECOVERY_ON_RERUN':'true'}
        self.at=datetime(2026,11,27,12,tzinfo=timezone.utc)
        self.run={'id':100,'run_attempt':2,'head_sha':'a'*40,'head_branch':'main',
                  'repository':{'full_name':request.REPO},'head_repository':{'full_name':request.REPO},
                  'path':request.WORKFLOW,'status':'in_progress'}
        self.previous=dict(self.run,run_attempt=1,status='completed',conclusion='success')
        self.evidence={'repository':request.REPO,'main':'a'*40,'activeWriterInspectionComplete':True}
        self.audit={'schemaVersion':1,'runId':100,'runAttempt':1,'commit':'a'*40,'mode':'audit',
                    'remoteWrites':False,'accountStoreAccessed':False,'checkedAt':self.at.isoformat(),
                    'evidence':self.evidence,'status':'recovery_candidate',
                    'diagnosticSha256':hashlib.sha256(request.encoded(self.evidence)).hexdigest()}
        self.rebuild()

    def rebuild(self, extra=None):
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(request.REPORT,json.dumps(self.audit))
            if extra: archive.writestr(extra,'untrusted')
        self.raw=stream.getvalue()
        self.artifact={'id':200,'name':'production-lock-audit-100-1','expired':False,
                       'workflow_run':{'id':100,'head_sha':'a'*40,'head_branch':'main'},
                       'size_in_bytes':len(self.raw),'digest':'sha256:'+hashlib.sha256(self.raw).hexdigest()}

    def get(self, path, binary=False):
        values={'actions/runs/100':self.run,'actions/runs/100/attempts/1':self.previous,
                'actions/runs/100/artifacts?per_page=100&page=1':{'total_count':1,'artifacts':[self.artifact]},
                'actions/artifacts/200/zip':self.raw}
        self.assertIn(path,values)
        return values[path]

    def test_initial_run_never_applies_or_reads_artifacts(self):
        def forbidden(*args,**kwargs): self.fail('Initial run must be read-only selection')
        result,audit=request.select(dict(self.env,GITHUB_RUN_ATTEMPT='1'),forbidden,self.at)
        self.assertEqual(result['mode'],'audit'); self.assertIsNone(audit)

    def test_manual_read_only_request_stays_audit_on_rerun(self):
        result,_=request.select(dict(self.env,ALLOW_RECOVERY_ON_RERUN='false'),self.get,self.at)
        self.assertEqual(result['mode'],'audit')

    def test_exact_explicit_rerun_binds_previous_digest(self):
        result,audit=request.select(self.env,self.get,self.at)
        self.assertEqual(result['mode'],'apply')
        self.assertEqual(result['auditSha256'],self.audit['diagnosticSha256'])
        self.assertEqual(audit,self.audit)

    def test_failed_previous_attempt_is_audit_only(self):
        self.previous['conclusion']='failure'
        result,_=request.select(self.env,self.get,self.at)
        self.assertEqual(result['mode'],'audit')

    def test_clear_lock_does_not_turn_into_apply(self):
        self.audit['status']='clear'; self.rebuild()
        self.assertEqual(request.select(self.env,self.get,self.at)[0]['mode'],'audit')

    def test_wrong_attempt_source_or_repository_cannot_authorize_apply(self):
        for key,value in (('run_attempt',3),('head_sha','b'*40),('head_branch','develop'),
                          ('head_repository',{'full_name':'other/repo'})):
            saved=self.previous[key]; self.previous[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError): request.select(self.env,self.get,self.at)
            self.previous[key]=saved

    def test_archive_digest_expiration_and_producer_tampering_rejected(self):
        self.artifact['digest']='sha256:'+'0'*64
        with self.assertRaises(ValueError): request.select(self.env,self.get,self.at)
        self.rebuild(); self.artifact['expired']=True
        with self.assertRaises(ValueError): request.select(self.env,self.get,self.at)
        for key,value in (('runAttempt',2),('runId',101),('commit','b'*40),
                          ('remoteWrites',True),('diagnosticSha256','0'*64)):
            saved=self.audit[key]; self.audit[key]=value; self.rebuild()
            with self.subTest(key=key), self.assertRaises(ValueError): request.select(self.env,self.get,self.at)
            self.audit[key]=saved

    def test_extra_archive_member_and_stale_diagnostic_rejected(self):
        self.rebuild(extra='../injected')
        with self.assertRaises(ValueError): request.select(self.env,self.get,self.at)
        self.rebuild()
        with self.assertRaises(ValueError): request.select(self.env,self.get,self.at+timedelta(hours=25))


if __name__ == '__main__':
    unittest.main()
