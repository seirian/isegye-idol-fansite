"""Read-only comparison of created-time partitions with the complete run reader.

This is diagnostic shadow traffic, never dispatch evidence. A matching result
describes two observations, not an atomic snapshot or an incremental index.
The baseline keeps its existing 20-page bound; partition probes and pages share
another 20-call budget. Thus an unsupplied baseline costs at most 40 GETs total.
"""
from datetime import datetime, timedelta
import re
from urllib.parse import parse_qs, urlencode

import batch_watchdog as policy

WORKFLOW = 'batch-watchdog.yml'
PREFIX = 'actions/workflows/'+WORKFLOW+'/runs'
MAX_CALLS = 20
MAX_DEPTH = 16
FILTER_LIMIT = 1000
EVENTS = {'push','schedule','workflow_dispatch','workflow_run'}


class ShadowError(ValueError):
    def __init__(self, code):
        super().__init__('Read-only shadow comparison incomplete')
        self.code = code


def utc_second(value):
    return value.astimezone(policy.UTC).replace(microsecond=0)


def iso(value):
    return value.isoformat(timespec='seconds').replace('+00:00','Z')


class ReadOnlyAPI:
    """Only the fixed controller's complete or bounded partition GETs exist."""
    def __init__(self, getter=None):
        self.getter = getter or policy.api
        self.baseline_calls = 0
        self.partition_calls = 0
        self.bounds = None

    def __call__(self, path, method='GET', payload=None, binary=False):
        if method != 'GET' or payload is not None or binary:
            raise ShadowError('shadow_read_only')
        endpoint, separator, query = path.partition('?')
        if endpoint != PREFIX or not separator:
            raise ShadowError('shadow_query_not_allowed')
        try:
            params = parse_qs(query, keep_blank_values=True, strict_parsing=True)
        except ValueError:
            raise ShadowError('shadow_query_not_allowed') from None
        if any(len(values) != 1 for values in params.values()):
            raise ShadowError('shadow_query_not_allowed')
        params = {key:values[0] for key,values in params.items()}
        if params.get('per_page') != '100' or not re.fullmatch(r'[1-9][0-9]*', params.get('page','')):
            raise ShadowError('shadow_query_not_allowed')
        page = int(params['page'])
        if set(params) == {'per_page','page'}:
            if page > policy.MAX_RUN_PAGES or self.baseline_calls >= policy.MAX_RUN_PAGES:
                raise ShadowError('shadow_baseline_budget_exceeded')
            self.baseline_calls += 1
        elif set(params) == {'branch','created','per_page','page'}:
            if params['branch'] != 'main' or page > 10 or self.bounds is None:
                raise ShadowError('shadow_query_not_allowed')
            match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\.\.(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)',params['created'])
            if not match:
                raise ShadowError('shadow_query_not_allowed')
            try:
                lower, upper = map(policy.clock,match.groups())
            except (ValueError,TypeError,AttributeError):
                raise ShadowError('shadow_query_not_allowed') from None
            if not self.bounds[0] <= lower <= upper <= self.bounds[1]:
                raise ShadowError('shadow_query_outside_bounds')
            if self.partition_calls >= MAX_CALLS:
                raise ShadowError('shadow_partition_budget_exceeded')
            self.partition_calls += 1
        else:
            raise ShadowError('shadow_query_not_allowed')
        return self.getter(path,method='GET',payload=None,binary=False)


def fingerprint(run):
    """Compare the fields that matter to attempt-aware decisions, plus creation."""
    if (not isinstance(run,dict) or type(run.get('id')) is not int or run['id'] <= 0 or
            run.get('head_branch') != 'main' or run.get('path') != '.github/workflows/'+WORKFLOW or
            not isinstance(run.get('repository'),dict) or run['repository'].get('full_name') != policy.REPO or
            not isinstance(run.get('head_repository'),dict) or run['head_repository'].get('full_name') != policy.REPO or
            type(run.get('run_attempt')) is not int or run['run_attempt'] < 1 or
            not isinstance(run.get('status'),str) or run['status'] not in policy.ACTIVE | {'completed'} or
            not isinstance(run.get('event'),str) or run['event'] not in EVENTS or
            not isinstance(run.get('head_sha'),str) or not re.fullmatch(r'[0-9a-f]{40}',run['head_sha']) or
            (run.get('conclusion') is not None and not isinstance(run['conclusion'],str))):
        raise ShadowError('shadow_invalid_run')
    try:
        started = policy.started(run).isoformat()
        created = policy.clock(run['created_at']).isoformat()
    except (KeyError,ValueError,TypeError,AttributeError):
        raise ShadowError('shadow_invalid_run_clock') from None
    return (run['id'],run['run_attempt'],run['status'],run.get('conclusion'),
            run['event'],run['head_sha'],started,created)


def read_page(client, lower, upper, page):
    query = urlencode({'branch':'main','created':iso(lower)+'..'+iso(upper),'per_page':100,'page':page})
    doc = client(PREFIX+'?'+query)
    if not isinstance(doc,dict):
        raise ShadowError('shadow_invalid_listing')
    rows, count = doc.get('workflow_runs'), doc.get('total_count')
    if (not isinstance(rows,list) or len(rows)>100 or type(count) is not int or count<0 or
            len(rows)>count or (len(rows)<100 and len(rows)<count and page==1)):
        raise ShadowError('shadow_incomplete_listing')
    entries = {}
    for row in rows:
        value = fingerprint(row)
        if value[0] in entries:
            raise ShadowError('shadow_duplicate_run')
        if not lower <= policy.clock(value[-1]) <= upper:
            raise ShadowError('shadow_run_outside_query')
        entries[value[0]] = value
    return entries, count


def compare_shadow(getter=None, at=None, baseline=None):
    """Always report authorizesDispatch=False, including complete matches."""
    result = {'schemaVersion':1,'kind':'watchdog_partition_shadow','workflow':WORKFLOW,
              'state':'incomplete','authorizesDispatch':False}
    client = ReadOnlyAPI(getter)
    stats = {'complete':False,'callBudget':MAX_CALLS,'calls':0,'depthBudget':MAX_DEPTH,
             'maxDepth':0,'completedPartitions':0,'saturatedPartitions':0,
             'boundaryDuplicates':0,'observedRuns':0}
    result['shadowInspection'] = stats
    try:
        at = at or datetime.now(policy.UTC)
        if not isinstance(at,datetime) or at.tzinfo is None:
            raise ShadowError('shadow_invalid_clock')
        upper = utc_second(at)
        result['checkedAt'] = at.astimezone(policy.UTC).isoformat()
        if baseline is None:
            baseline = policy.read_workflow_runs(WORKFLOW,client)
        if not isinstance(baseline,dict) or not isinstance(baseline.get('inspection'),dict):
            raise ShadowError('shadow_baseline_incomplete')
        coverage = baseline['inspection']
        result['baselineInspection'] = policy.error_details(policy.InspectionError(
            'inspection_validation_failed','',inspection=coverage)).get('inspection',{})
        rows = baseline.get('runs')
        if (coverage.get('scope') != 'workflow' or coverage.get('workflow') != WORKFLOW or
                coverage.get('complete') is not True or not isinstance(rows,list) or
                coverage.get('pageSize') != policy.RUN_PAGE_SIZE or
                type(coverage.get('pageBudget')) is not int or not 1<=coverage['pageBudget']<=policy.MAX_RUN_PAGES or
                type(coverage.get('pagesRead')) is not int or not 1<=coverage['pagesRead']<=coverage['pageBudget'] or
                any(type(coverage.get(key)) is not int or coverage[key]<0
                    for key in ('expectedRuns','observedRuns','mainRuns')) or
                coverage.get('observedRuns') != coverage['expectedRuns'] or
                coverage.get('mainRuns') != len(rows) or len(rows)>coverage['expectedRuns'] or
                coverage['expectedRuns']>policy.RUN_PAGE_SIZE*policy.MAX_RUN_PAGES):
            raise ShadowError('shadow_baseline_incomplete')
        original = {}
        for row in rows:
            value = fingerprint(row)
            if value[0] in original:
                raise ShadowError('shadow_duplicate_baseline_run')
            original[value[0]] = value
        lower = min((utc_second(policy.clock(value[-1])) for value in original.values()),
                    default=datetime(1970,1,1,tzinfo=policy.UTC))
        if lower>upper:
            raise ShadowError('shadow_baseline_outside_fixed_window')
        client.bounds = (lower,upper)
        result['createdWindow'] = {'from':iso(lower),'through':iso(upper),'inclusive':True}
        observed, windows = {}, {}

        def partition(start, end, depth):
            stats['maxDepth'] = max(stats['maxDepth'],depth)
            entries, total = read_page(client,start,end,1)
            if total >= FILTER_LIMIT:
                stats['saturatedPartitions'] += 1
                if start == end:
                    raise ShadowError('shadow_same_second_saturated')
                if depth >= MAX_DEPTH:
                    raise ShadowError('shadow_depth_budget_exceeded')
                seconds = int((end-start).total_seconds())
                if seconds == 1:
                    children = ((start,start),(end,end))
                else:
                    middle = start+timedelta(seconds=seconds//2)
                    children = ((start,middle),(middle,end))
                for left,right in children:
                    partition(left,right,depth+1)
                return
            page = 1
            while len(entries)<total:
                page += 1
                more, count = read_page(client,start,end,page)
                if count != total:
                    raise ShadowError('shadow_listing_changed')
                if entries.keys() & more.keys():
                    raise ShadowError('shadow_duplicate_run')
                entries.update(more)
                if len(more)<100 and len(entries)<total:
                    raise ShadowError('shadow_incomplete_listing')
            if len(entries) != total:
                raise ShadowError('shadow_incomplete_listing')
            for ident,value in entries.items():
                if ident in observed:
                    previous = windows[ident]
                    boundary = max(start,previous[0])
                    if (boundary != min(end,previous[1]) or policy.clock(value[-1]) != boundary or
                            observed[ident] != value):
                        raise ShadowError('shadow_boundary_run_changed')
                    stats['boundaryDuplicates'] += 1
                else:
                    observed[ident] = value
                    windows[ident] = (start,end)
            stats['observedRuns'] = len(observed)
            stats['completedPartitions'] += 1

        partition(lower,upper,0)
        stats['complete'] = True
        missing = sorted(original.keys()-observed.keys())
        added = sorted(observed.keys()-original.keys())
        changed = sorted(ident for ident in original.keys() & observed.keys() if original[ident] != observed[ident])
        result['differences'] = {
            'missingCount':len(missing),'addedCount':len(added),'changedCount':len(changed),
            'missingIds':missing[:20],'addedIds':added[:20],'changedIds':changed[:20]}
        result['state'] = 'changed' if missing or added or changed else 'matched'
    except Exception as exc:
        details = policy.error_details(exc)
        result.update(details)
        if 'baselineInspection' not in result and 'inspection' in details:
            result['baselineInspection'] = details['inspection']
        if isinstance(exc,ShadowError):
            result['reasonCode'] = exc.code
    result['baselineCalls'] = client.baseline_calls
    stats['calls'] = client.partition_calls
    result['totalCalls'] = client.baseline_calls+client.partition_calls
    return result
