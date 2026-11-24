"""Complete scoped reads and safe diagnostics; all API/CLI responses are local fakes."""
from contextlib import redirect_stdout
from datetime import timedelta
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import batch_watchdog as w
from test_batch_watchdog_reliability import AT, ENV, run


def response(body=b'{}', status=200, headers=b'', returncode=0, stderr=b''):
    return subprocess.CompletedProcess([], returncode,
        b'HTTP/2.0 '+str(status).encode()+b' Status\r\n'+headers+b'\r\n'+body, stderr)


class ScopedInspection(unittest.TestCase):
    def test_coverage_counts_non_main_rows_without_using_them_for_decisions(self):
        entries=[run(1, head_branch='feature', status='in_progress'), run(2)]
        getter=Mock(return_value={'total_count':2, 'workflow_runs':entries})
        result=w.read_workflow_runs('schedule-refresh.yml', getter)
        self.assertEqual(set(result), {'runs','inspection'})
        self.assertEqual([r['id'] for r in result['runs']], [2])
        self.assertEqual(result['inspection'], {
            'scope':'workflow', 'workflow':'schedule-refresh.yml', 'pageSize':100,
            'pageBudget':20, 'pagesRead':1, 'expectedRuns':2, 'observedRuns':2,
            'mainRuns':1, 'complete':True})
        getter.assert_called_once_with('actions/workflows/schedule-refresh.yml/runs?per_page=100&page=1')

    def test_controller_is_readable_but_is_not_added_to_recovery_targets(self):
        getter=Mock(return_value={'total_count':0,'workflow_runs':[]})
        result=w.read_workflow_runs('batch-watchdog.yml', getter)
        self.assertTrue(result['inspection']['complete'])
        self.assertNotIn('batch-watchdog.yml', {spec[0] for spec in w.SPECS.values()})
        with self.assertRaises(w.InspectionError) as caught:
            w.workflow_runs('batch-watchdog.yml', getter)
        self.assertEqual(caught.exception.reason_code, 'unapproved_workflow')
        self.assertEqual(getter.call_count, 1)

    def test_reader_rejects_unapproved_scope_and_larger_budget_without_calls(self):
        for filename, pages in [('unapproved.yml',20),('schedule-refresh.yml',21),
                                ('schedule-refresh.yml',True),('schedule-refresh.yml',0)]:
            getter=Mock()
            with self.subTest(filename=filename,pages=pages), self.assertRaises(ValueError):
                w.read_workflow_runs(filename,getter,pages)
            getter.assert_not_called()

    def test_exact_two_thousand_rows_remain_complete_and_old_attempt_is_latest(self):
        entries=[run(i,minutes=120) for i in range(1,2001)]
        entries[-1].update(created_at='2026-10-01T00:00:00Z',run_attempt=12,
                           run_started_at=(AT-timedelta(minutes=3)).isoformat())
        calls=[]
        def getter(path):
            calls.append(path)
            page=int(path.rsplit('page=',1)[1])
            return {'total_count':2000,'workflow_runs':entries[(page-1)*100:page*100]}
        result=w.read_workflow_runs('schedule-refresh.yml',getter)
        self.assertEqual(len(calls),20)
        self.assertEqual(result['inspection']['observedRuns'],2000)
        self.assertTrue(result['inspection']['complete'])
        self.assertEqual(result['runs'][0]['id'],2000)
        self.assertEqual(w.recovery_action(result['runs'],AT,w.due_slot('schedule',AT),False),'cooldown')
        self.assertTrue(all('branch=' not in p and 'created=' not in p and 'status=' not in p for p in calls))

    def test_real_budget_overflow_reports_partial_coverage_never_partial_runs(self):
        def getter(path):
            page=int(path.rsplit('page=',1)[1])
            return {'total_count':2282,'workflow_runs':[run(i) for i in range((page-1)*100+1,page*100+1)]}
        with self.assertRaisesRegex(ValueError,'budget') as caught:
            w.read_workflow_runs('schedule-refresh.yml',getter)
        details=w.error_details(caught.exception)
        self.assertEqual(details['reasonCode'],'run_history_budget_exceeded')
        self.assertEqual(details['inspection']['expectedRuns'],2282)
        self.assertEqual(details['inspection']['observedRuns'],2000)
        self.assertEqual(details['inspection']['pagesRead'],20)
        self.assertFalse(details['inspection']['complete'])
        self.assertNotIn('runs',details)

    def test_same_count_old_completed_rerun_is_rechecked_before_dispatch(self):
        initial=run(1,minutes=120,created_at='2026-10-01T00:00:00Z')
        rerun={**initial,'run_attempt':12,'run_started_at':(AT-timedelta(minutes=3)).isoformat()}
        getter=Mock(side_effect=[{'total_count':1,'workflow_runs':[initial]},
                                {'total_count':1,'workflow_runs':[rerun]}])
        with patch.dict('os.environ',ENV,clear=True):
            result=w.recover_batch('schedule',True,getter,lambda:AT)
        self.assertEqual(result['state'],'cooldown')
        self.assertEqual(result['latestAttempt']['attempt'],12)
        self.assertTrue(result['recheckedBeforeDispatch'])
        self.assertTrue(result['inspection']['complete'])
        self.assertEqual(getter.call_count,2)
        self.assertEqual(getter.call_args_list[0],getter.call_args_list[1])

    def test_same_count_active_transition_blocks_dispatch(self):
        initial=run(1,minutes=120)
        getter=Mock(side_effect=[{'total_count':1,'workflow_runs':[initial]},
                                {'total_count':1,'workflow_runs':[{**initial,'status':'waiting','run_attempt':2}]}])
        with patch.dict('os.environ',ENV,clear=True):
            result=w.recover_batch('schedule',True,getter,lambda:AT)
        self.assertEqual(result['state'],'active')
        self.assertEqual(result['activeRuns'],[1])
        self.assertEqual(getter.call_count,2)

    def test_same_count_success_uses_new_attempt_evidence(self):
        initial=run(1,minutes=120)
        completed={**initial,'run_attempt':2,'conclusion':'success',
                   'run_started_at':(AT-timedelta(minutes=3)).isoformat()}
        getter=Mock(side_effect=[{'total_count':1,'workflow_runs':[initial]},
                                {'total_count':1,'workflow_runs':[completed]}])
        pub={'status':'published','evidenceVersion':2,'generatedAt':AT.isoformat(),
             'publishedAt':AT.isoformat(),'readbackAt':AT.isoformat(),'verifiedReadback':True,
             'collectionHealth':{'state':'complete','sources':{
                 name:{'state':'complete','lastSuccessAt':AT.isoformat()} for name in w.REQUIRED_SCHEDULE}}}
        with patch.dict('os.environ',ENV,clear=True), patch.object(w,'artifact_files',return_value={
            'schedule-publication.json':pub,'schedule-health.json':{'verified':True}}) as evidence:
            result=w.recover_batch('schedule',True,getter,lambda:AT)
        self.assertEqual(result['state'],'healthy')
        self.assertEqual(result['evidenceAttempt'],2)
        self.assertEqual(evidence.call_args.args[0]['run_attempt'],2)
        self.assertEqual(getter.call_count,2)

    def test_changed_incomplete_duplicate_and_untrusted_results_have_distinct_codes(self):
        cases=[
            ([{'total_count':101,'workflow_runs':[run(i) for i in range(1,101)]},
              {'total_count':102,'workflow_runs':[run(101),run(102)]}], 'run_history_changed'),
            ([{'total_count':2,'workflow_runs':[run()]}], 'run_history_incomplete'),
            ([{'total_count':2,'workflow_runs':[run(),run()]}], 'duplicate_run_id'),
            ([{'total_count':1,'workflow_runs':[run(head_repository={'full_name':'other/fork'})]}], 'invalid_run_provenance'),
            ([{'total_count':1,'workflow_runs':[run(run_attempt=0)]}], 'invalid_run_attempt'),
            ([{'total_count':1,'workflow_runs':[run(status='unknown')]}], 'invalid_run_status'),
            ([{'total_count':1,'workflow_runs':[run(status={})]}], 'invalid_run_status'),
            ([{'total_count':1,'workflow_runs':[run(run_attempt=2,run_started_at=None)]}], 'invalid_run_clock'),
            ([{'total_count':True,'workflow_runs':[]}], 'invalid_run_listing'),
        ]
        for replies,code in cases:
            with self.subTest(code=code),self.assertRaises(w.InspectionError) as caught:
                w.read_workflow_runs('schedule-refresh.yml',Mock(side_effect=replies))
            self.assertEqual(caught.exception.reason_code,code)
            self.assertFalse(w.error_details(caught.exception)['inspection']['complete'])

    def test_api_failure_retains_only_completed_page_coverage(self):
        first={'total_count':101,'workflow_runs':[run(i) for i in range(1,101)]}
        error=w.GitHubAPIError('github_rate_limited',api_diagnostics={'httpStatus':429,'retryAfterSeconds':60})
        with self.assertRaises(w.GitHubAPIError) as caught:
            w.read_workflow_runs('schedule-refresh.yml',Mock(side_effect=[first,error]))
        details=w.error_details(caught.exception)
        self.assertEqual(details['reasonCode'],'github_rate_limited')
        self.assertEqual(details['inspection']['pagesRead'],1)
        self.assertEqual(details['inspection']['observedRuns'],100)
        self.assertEqual(details['inspection']['expectedRuns'],101)
        self.assertEqual(details['apiDiagnostics'],{'httpStatus':429,'retryAfterSeconds':60})

    def test_audit_report_preserves_inspection_reason_and_never_writes(self):
        inspection={'scope':'workflow','workflow':'schedule-refresh.yml','pageSize':100,'pageBudget':20,
                    'pagesRead':20,'expectedRuns':2282,'observedRuns':2000,'mainRuns':2000,'complete':False}
        error=w.InspectionError('run_history_budget_exceeded','not included in report',inspection=inspection)
        with tempfile.TemporaryDirectory() as folder, patch.object(w,'ROOT',Path(folder)), \
                patch.dict('os.environ',ENV,clear=True),patch.object(sys,'argv',['watchdog']), \
                patch.object(w,'recover_batch',side_effect=error),patch.object(w,'api') as api,redirect_stdout(io.StringIO()):
            self.assertEqual(w.main(),1)
            report=json.loads((Path(folder)/'batch-watchdog.json').read_text())
        api.assert_not_called()
        self.assertEqual(report['schemaVersion'],2)
        self.assertTrue(all(row['state']=='inspection_failed' for row in report['batches']))
        self.assertEqual(report['batches'][0]['reasonCode'],'run_history_budget_exceeded')
        self.assertNotIn('not included in report',json.dumps(report))


class SafeHTTPDiagnostics(unittest.TestCase):
    def test_json_and_empty_dispatch_body_keep_existing_return_contract(self):
        with patch.object(w.subprocess,'run',return_value=response(b'{"total_count":0}')) as cli:
            self.assertEqual(w.api('actions/workflows/schedule-refresh.yml/runs?per_page=100&page=1'),{'total_count':0})
        self.assertIn('--include',cli.call_args.args[0])
        with patch.object(w.subprocess,'run',return_value=response(b'',status=204)) as cli:
            self.assertEqual(w.api('actions/workflows/schedule-refresh.yml/dispatches','POST',{'ref':'main'}),{})
        cli.assert_called_once()
        self.assertEqual(json.loads(cli.call_args.kwargs['input']),{'ref':'main'})

    def test_zip_body_is_byte_exact_after_lf_or_redirect_headers(self):
        archive=b'PK\x03\x04\x00\xff\r\n\r\nopaque archive bytes'
        for prefix in (b'HTTP/2.0 200 OK\nContent-Type: application/zip\n\n',
                       b'HTTP/1.1 302 Found\r\nLocation: https://secret.invalid/?signed=DO-NOT-LOG\r\n\r\n'
                       b'HTTP/2.0 200 OK\r\nContent-Type: application/zip\r\n\r\n'):
            with self.subTest(prefix=prefix[:16]),patch.object(w.subprocess,'run',return_value=subprocess.CompletedProcess([],0,prefix+archive,b'')):
                self.assertEqual(w.api('actions/artifacts/123/zip',binary=True),archive)

    def test_http_failure_reports_only_safe_numeric_metadata(self):
        headers=(b'X-RateLimit-Limit: 1000\r\nX-RateLimit-Remaining: 0\r\n'
                 b'X-RateLimit-Reset: 1800000000\r\nRetry-After: 60\r\n'
                 b'Location: https://secret.invalid/?signed=DO-NOT-LOG\r\nSet-Cookie: DO-NOT-LOG\r\n')
        with patch.object(w.subprocess,'run',return_value=response(b'{"message":"DO-NOT-LOG"}',403,headers,1,b'DO-NOT-LOG')):
            with self.assertRaises(RuntimeError) as caught:w.api('actions/runs/1')
        self.assertEqual(w.error_details(caught.exception),{'error':'GitHubAPIError','reasonCode':'github_rate_limited',
            'apiDiagnostics':{'httpStatus':403,'rateLimitLimit':1000,'rateLimitRemaining':0,
                              'rateLimitReset':1800000000,'retryAfterSeconds':60}})
        self.assertNotIn('DO-NOT-LOG',str(caught.exception)+json.dumps(w.error_details(caught.exception)))

    def test_forbidden_without_rate_evidence_is_not_mislabelled_rate_limit(self):
        for status,headers,code in [(403,b'X-RateLimit-Remaining: 100\r\n','github_http_error'),
                                    (403,b'Retry-After: 30\r\n','github_rate_limited'),
                                    (429,b'','github_rate_limited'),(404,b'','github_http_error')]:
            with self.subTest(status=status,headers=headers),patch.object(w.subprocess,'run',return_value=response(b'{}',status,headers,1)):
                with self.assertRaises(w.GitHubAPIError) as caught:w.api('actions/runs/1')
            self.assertEqual(caught.exception.reason_code,code)

    def test_timeout_cli_failure_and_invalid_json_have_distinct_safe_reasons(self):
        cases=[(subprocess.TimeoutExpired(['DO-NOT-LOG'],70,output=b'DO-NOT-LOG'),'github_timeout'),
               (subprocess.CompletedProcess([],1,b'',b'DO-NOT-LOG'),'github_request_failed'),
               (response(b'DO-NOT-LOG'),'github_invalid_json')]
        for outcome,code in cases:
            kwargs={'side_effect':outcome} if isinstance(outcome,Exception) else {'return_value':outcome}
            with self.subTest(code=code),patch.object(w.subprocess,'run',**kwargs):
                with self.assertRaises((w.InspectionError,w.GitHubAPIError)) as caught:w.api('actions/runs/1')
            self.assertEqual(caught.exception.reason_code,code)
            self.assertNotIn('DO-NOT-LOG',str(caught.exception)+json.dumps(w.error_details(caught.exception)))

    def test_invalid_headers_and_oversized_archive_do_not_become_empty_success(self):
        for raw,code in [(b'{}','github_invalid_headers'),
                         (b'HTTP/2.0 200 OK\nX-Padding: '+b'x'*w.MAX_HTTP_HEADERS+b'\n\n{}','github_invalid_headers')]:
            with self.subTest(code=code),patch.object(w.subprocess,'run',return_value=subprocess.CompletedProcess([],0,raw,b'')):
                with self.assertRaises(w.InspectionError) as caught:w.api('actions/runs/1')
            self.assertEqual(caught.exception.reason_code,code)
        with patch.object(w,'MAX_ARCHIVE',4),patch.object(w.subprocess,'run',return_value=response(b'12345')):
            with self.assertRaises(ValueError) as caught:w.api('actions/artifacts/123/zip',binary=True)
        self.assertEqual(caught.exception.reason_code,'github_response_too_large')

    def test_unknown_exception_and_metadata_cannot_leak_text(self):
        self.assertEqual(w.error_details(ValueError('DO-NOT-LOG')),
                         {'error':'ValueError','reasonCode':'inspection_validation_failed'})
        error=w.GitHubAPIError('github_http_error',api_diagnostics={
            'httpStatus':403,'rateLimitRemaining':True,'retryAfterSeconds':'DO-NOT-LOG',
            'location':'DO-NOT-LOG','rateLimitReset':10**15})
        self.assertEqual(w.error_details(error)['apiDiagnostics'],{'httpStatus':403})


if __name__=='__main__':
    unittest.main()
