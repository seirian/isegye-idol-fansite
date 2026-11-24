"""Shadow transport comparisons use local fake responses and can never dispatch."""
from copy import deepcopy
from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import batch_watchdog as policy
import batch_watchdog_shadow as shadow
from test_batch_watchdog_reliability import AT, run


def controller(ident, created=None, **changes):
    created=created or AT-timedelta(hours=2)
    value=run(ident,created_at=created.isoformat(),run_started_at=created.isoformat(),
              path='.github/workflows/batch-watchdog.yml')
    value.update(changes)
    return value


def history(count):
    return [controller(i+1,AT-timedelta(seconds=count-i-1)) for i in range(count)]


class FakeAPI:
    def __init__(self, baseline, candidate=None, transform=None):
        self.baseline=baseline
        self.candidate=candidate if candidate is not None else baseline
        self.transform=transform
        self.calls=[]

    def __call__(self,path,method='GET',payload=None,binary=False):
        if method!='GET' or payload is not None or binary:
            raise AssertionError('Shadow attempted a mutation or archive request')
        self.calls.append(path)
        params=parse_qs(path.split('?',1)[1])
        page=int(params['page'][0])
        rows=self.baseline
        if 'created' in params:
            low,high=map(policy.clock,params['created'][0].split('..'))
            rows=[r for r in self.candidate if r.get('head_branch')=='main' and
                  low<=policy.clock(r['created_at'])<=high]
        rows=sorted(rows,key=lambda r:(policy.clock(r['created_at']),r['id']),reverse=True)
        doc={'total_count':len(rows),'workflow_runs':deepcopy(rows[(page-1)*100:page*100])}
        return self.transform(doc,params) if self.transform else doc


class Comparison(unittest.TestCase):
    def test_999_1000_1001_results_split_saturated_queries(self):
        for count in (999,1000,1001):
            api=FakeAPI(history(count))
            with self.subTest(count=count):
                result=shadow.compare_shadow(api,AT)
                self.assertEqual(result['state'],'matched',result)
                self.assertFalse(result['authorizesDispatch'])
                self.assertEqual(result['shadowInspection']['observedRuns'],count)
                self.assertTrue(result['shadowInspection']['complete'])
                self.assertEqual(result['shadowInspection']['saturatedPartitions'],int(count>=1000))
                self.assertLessEqual(result['shadowInspection']['calls'],20)
                self.assertLessEqual(result['totalCalls'],40)
                self.assertEqual(len(api.calls),result['totalCalls'])
                if count>=1000:self.assertGreater(result['shadowInspection']['boundaryDuplicates'],0)

    def test_old_completed_rerun_is_in_range_and_same_count_change_is_detected(self):
        old=controller(1,AT-timedelta(days=45),run_attempt=12,
                       run_started_at=(AT-timedelta(minutes=3)).isoformat())
        baseline=[old,controller(2)]
        matched=shadow.compare_shadow(FakeAPI(baseline),AT)
        self.assertEqual(matched['state'],'matched')
        self.assertEqual(matched['createdWindow']['from'],shadow.iso(shadow.utc_second(AT-timedelta(days=45))))
        changed=shadow.compare_shadow(FakeAPI(baseline,[{**old,'run_attempt':13},controller(2)]),AT)
        self.assertEqual(changed['state'],'changed')
        self.assertEqual(changed['differences']['changedIds'],[1])
        self.assertEqual(changed['differences']['missingCount'],0)
        self.assertEqual(changed['differences']['addedCount'],0)
        self.assertFalse(changed['authorizesDispatch'])

    def test_all_decision_fingerprint_fields_are_compared(self):
        before=controller(1)
        changes=[{'run_attempt':2},{'status':'waiting'},{'conclusion':'success'},
                 {'event':'push'},{'head_sha':'b'*40},
                 {'run_started_at':(AT-timedelta(minutes=30)).isoformat()}]
        for update in changes:
            with self.subTest(field=next(iter(update))):
                result=shadow.compare_shadow(FakeAPI([before],[{**before,**update}]),AT)
                self.assertEqual(result['state'],'changed')
                self.assertEqual(result['differences']['changedIds'],[1])
                self.assertFalse(result['authorizesDispatch'])

    def test_missing_and_added_ids_are_not_equal_even_when_count_is_same(self):
        result=shadow.compare_shadow(FakeAPI([controller(1)],[controller(2)]),AT)
        self.assertEqual(result['state'],'changed')
        self.assertEqual(result['differences']['missingIds'],[1])
        self.assertEqual(result['differences']['addedIds'],[2])

    def test_empty_comparison_never_authorizes_dispatch_or_hides_new_run(self):
        empty=shadow.compare_shadow(FakeAPI([]),AT)
        self.assertEqual(empty['state'],'matched')
        self.assertEqual(empty['createdWindow']['from'],'1970-01-01T00:00:00Z')
        self.assertEqual(empty['shadowInspection']['calls'],1)
        self.assertFalse(empty['authorizesDispatch'])
        added=shadow.compare_shadow(FakeAPI([],[controller(1)]),AT)
        self.assertEqual(added['state'],'changed')
        self.assertEqual(added['differences']['addedIds'],[1])

    def test_fixed_upper_bound_does_not_claim_observation_after_that_second(self):
        api=FakeAPI([controller(1)],[controller(1),controller(2,AT+timedelta(seconds=1))])
        result=shadow.compare_shadow(api,AT)
        self.assertEqual(result['state'],'matched')
        self.assertEqual(result['createdWindow']['through'],shadow.iso(shadow.utc_second(AT)))
        self.assertFalse(result['authorizesDispatch'])

    def test_equal_boundary_duplicate_is_allowed_but_new_attempt_is_not(self):
        rows=history(1001)
        middle=shadow.utc_second(AT-timedelta(seconds=500))
        def change_boundary(doc,params):
            if params.get('created',[None])[0] and params['created'][0].split('..')[0]==shadow.iso(middle):
                for value in doc['workflow_runs']:
                    if policy.clock(value['created_at'])==middle:
                        value['run_attempt']=2
                        value['run_started_at']=AT.isoformat()
            return doc
        result=shadow.compare_shadow(FakeAPI(rows,transform=change_boundary),AT)
        self.assertEqual(result['state'],'incomplete')
        self.assertEqual(result['reasonCode'],'shadow_boundary_run_changed')
        self.assertFalse(result['shadowInspection']['complete'])
        self.assertFalse(result['authorizesDispatch'])

    def test_same_second_saturation_stops_instead_of_guessing_missing_rows(self):
        rows=[controller(i,AT) for i in range(1,1001)]
        result=shadow.compare_shadow(FakeAPI(rows),AT)
        self.assertEqual(result['state'],'incomplete')
        self.assertEqual(result['reasonCode'],'shadow_same_second_saturated')
        self.assertEqual(result['shadowInspection']['calls'],1)

    def test_probe_and_leaf_calls_share_fixed_partition_budget(self):
        result=shadow.compare_shadow(FakeAPI(history(2000)),AT)
        self.assertEqual(result['state'],'incomplete')
        self.assertEqual(result['reasonCode'],'shadow_partition_budget_exceeded')
        self.assertEqual(result['baselineCalls'],20)
        self.assertEqual(result['shadowInspection']['calls'],20)
        self.assertEqual(result['totalCalls'],40)

    def test_depth_limit_stops_a_concentrated_partition(self):
        rows=[controller(1,datetime(1970,1,1,tzinfo=policy.UTC))]
        rows += [controller(i,AT) for i in range(2,1002)]
        with patch.object(shadow,'MAX_DEPTH',2):
            result=shadow.compare_shadow(FakeAPI(rows),AT)
        self.assertEqual(result['state'],'incomplete')
        self.assertEqual(result['reasonCode'],'shadow_depth_budget_exceeded')
        self.assertEqual(result['shadowInspection']['maxDepth'],2)

    def test_incomplete_baseline_prevents_candidate_queries(self):
        def short_baseline(doc,params):
            doc['total_count']=2
            return doc
        result=shadow.compare_shadow(FakeAPI([controller(1)],transform=short_baseline),AT)
        self.assertEqual(result['state'],'incomplete')
        self.assertEqual(result['reasonCode'],'run_history_incomplete')
        self.assertEqual(result['shadowInspection']['calls'],0)
        self.assertFalse(result['baselineInspection']['complete'])

    def test_leaf_duplicate_changed_count_and_truncation_are_not_deduplicated(self):
        def duplicate(doc,params):
            if 'created' in params and params['page']==['2']:
                doc['workflow_runs']=[controller(101,AT)]
            return doc
        def changed_count(doc,params):
            if 'created' in params and params['page']==['2']:doc['total_count']+=1
            return doc
        def truncated(doc,params):
            if 'created' in params:doc['workflow_runs']=[]
            return doc
        for transform,code in [(duplicate,'shadow_duplicate_run'),(changed_count,'shadow_listing_changed'),
                               (truncated,'shadow_incomplete_listing')]:
            with self.subTest(code=code):
                result=shadow.compare_shadow(FakeAPI(history(101),transform=transform),AT)
                self.assertEqual(result['state'],'incomplete')
                self.assertEqual(result['reasonCode'],code)
                self.assertFalse(result['authorizesDispatch'])

    def test_untrusted_candidate_provenance_and_missing_attempt_clock_fail(self):
        before=controller(1)
        for change in [{'head_repository':{'full_name':'other/fork'}},
                       {'path':'.github/workflows/production.yml'},
                       {'run_attempt':2,'run_started_at':None}]:
            with self.subTest(change=change):
                result=shadow.compare_shadow(FakeAPI([before],[{**before,**change}]),AT)
                self.assertEqual(result['state'],'incomplete')
                self.assertFalse(result['authorizesDispatch'])

    def test_supplied_complete_baseline_avoids_extra_baseline_calls(self):
        api=FakeAPI([controller(1)])
        baseline=policy.read_workflow_runs(shadow.WORKFLOW,api)
        api.calls.clear()
        result=shadow.compare_shadow(api,AT,baseline)
        self.assertEqual(result['state'],'matched')
        self.assertEqual(result['baselineCalls'],0)
        self.assertEqual(result['totalCalls'],1)
        baseline['inspection']['complete']=False
        api.calls.clear()
        result=shadow.compare_shadow(api,AT,baseline)
        self.assertEqual(result['state'],'incomplete')
        self.assertEqual(api.calls,[])


class ReadOnlyBoundary(unittest.TestCase):
    def test_mutations_archives_and_other_workflows_are_rejected_without_io(self):
        backend=Mock()
        client=shadow.ReadOnlyAPI(backend)
        cases=[(shadow.PREFIX,'POST',{'ref':'main'},False),
               (shadow.PREFIX,'DELETE',None,False),
               ('actions/artifacts/1/zip','GET',None,True),
               ('actions/workflows/production.yml/runs?per_page=100&page=1','GET',None,False)]
        for path,method,payload,binary in cases:
            with self.subTest(path=path,method=method),self.assertRaises(shadow.ShadowError):
                client(path,method,payload,binary)
        backend.assert_not_called()

    def test_partition_parameters_and_fixed_bounds_cannot_be_bypassed(self):
        backend=Mock()
        client=shadow.ReadOnlyAPI(backend)
        client.bounds=(shadow.utc_second(AT-timedelta(hours=1)),shadow.utc_second(AT))
        query='branch=main&created='+shadow.iso(client.bounds[0])+'..'+shadow.iso(client.bounds[1])+'&per_page=100&page=1'
        for invalid in [query+'&status=completed',query+'&page=1',query.replace('branch=main','branch=feature'),
                        query.replace('page=1','page=11'),query.replace(shadow.iso(client.bounds[0]),'1970-01-01T00:00:00Z')]:
            with self.subTest(query=invalid),self.assertRaises(shadow.ShadowError):
                client(shadow.PREFIX+'?'+invalid)
        backend.assert_not_called()


if __name__=='__main__':
    unittest.main()
