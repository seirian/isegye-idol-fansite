#!/usr/bin/env python3
"""Consume only administrator-approved private requests. Never receives a user session.

GitHub credentials stay in Actions. A short-lived, hashed server capability only
claims/settles existing requests; it cannot create users, requests, or read feeds.
Each request permits ONE dispatch attempt. Ambiguous POST results are not retried.
"""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
from pathlib import Path
import base64, hashlib, json, os, re, secrets, socket, subprocess, sys
import urllib.error, urllib.parse, urllib.request
import inour_sftp as d
import batch_watchdog as policy
from deploy_verified_albums import VerifiedTransferRemote

ROOT=Path(__file__).resolve().parents[1]
REPO=policy.REPO
# Independent capture is a read-only monitor row with guarded internal recovery;
# adding it to watchdog inspection must not create a ninth manual capability.
TARGETS={k:v[0] for k,v in policy.SPECS.items() if k != 'capture'} | {'watchdog':'batch-watchdog.yml'}
PAUSES={k:v[2] for k,v in policy.SPECS.items() if k != 'capture'} | {'watchdog':'PRODUCTION_PAUSED'}
ACTIVE=('queued','pending','in_progress','waiting','requested')
FOLDER=d.ROOT+'/.batch-monitoring/control'
MARKER=b'isegye-batch-manual:v1\n'
API_VERSION='2026-03-10'

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

class GitHub:
    def __init__(self):self.calls=0
    def __call__(self,path,method='GET',payload=None):
        files='(?:'+'|'.join(re.escape(v) for v in TARGETS.values())+')'
        allowed=bool(method=='GET' and (path=='git/ref/heads/main' or
            re.fullmatch(r'actions/runs/[1-9][0-9]*',path) or
            re.fullmatch(r'actions/workflows/'+files+r'(?:/runs\?[^\s]+)?',path)))
        allowed|=(method=='POST' and re.fullmatch(r'actions/workflows/'+files+r'/dispatches',path) is not None and payload=={'ref':'main'})
        if not allowed:raise ValueError('Endpoint not allowed')
        self.calls+=1
        if self.calls>180:raise ValueError('API budget exceeded')
        token=os.environ.get('GH_TOKEN','')
        if not token:raise ValueError('Actions credential missing')
        request=urllib.request.Request('https://api.github.com/repos/'+REPO+'/'+path,
            data=json.dumps(payload).encode() if payload is not None else None,method=method,
            headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','Content-Type':'application/json',
                     'X-GitHub-Api-Version':API_VERSION,'User-Agent':'IsegyeAdminManual/1.0'})
        # No redirects/retries, especially after an ambiguous mutation.
        with urllib.request.build_opener(NoRedirect).open(request,timeout=30) as response:
            raw=response.read(4_000_001)
            if len(raw)>4_000_000:raise ValueError('Oversized API response')
            return json.loads(raw) if raw else {}


def trusted_run(run,filename):
    if (type(run.get('id')) is not int or run['id']<=0 or run.get('head_branch')!='main' or
        run.get('path')!='.github/workflows/'+filename or run.get('repository',{}).get('full_name')!=REPO or
        run.get('head_repository',{}).get('full_name')!=REPO or run.get('status') not in (*ACTIVE,'completed')):
        raise ValueError('Untrusted run')
    return run


def runs(api,filename,filters):
    values=[];seen=set();total=None
    for page in range(1,11):
        query=urllib.parse.urlencode({'branch':'main','per_page':100,'page':page,**filters})
        result=api('actions/workflows/'+filename+'/runs?'+query)
        entries=result.get('workflow_runs');count=result.get('total_count')
        if not isinstance(entries,list) or len(entries)>100 or type(count) is not int or count<0 or (total is not None and total!=count):raise ValueError('Incomplete run history')
        total=count
        for run in entries:
            trusted_run(run,filename)
            if run['id'] in seen:raise ValueError('Duplicate history')
            seen.add(run['id']);values.append(run)
        if len(seen)==total:return values
        if len(entries)<100:raise ValueError('Truncated history')
    raise ValueError('History budget exceeded')


def decision(api,batch,at,environment):
    if batch not in TARGETS:raise ValueError('Unknown batch')
    if any(environment.get(k)=='true' for k in ('PRODUCTION_PAUSED','ISEGYE_MANUAL_PAUSED',PAUSES[batch])):return 'paused'
    if batch=='albums' and 1<=at.astimezone(policy.KST).hour<7:return 'night_pause'
    filename=TARGETS[batch]
    workflow=api('actions/workflows/'+filename)
    if workflow.get('path')!='.github/workflows/'+filename or workflow.get('state')!='active':raise ValueError('Workflow unavailable')
    for status in ACTIVE:
        if runs(api,filename,{'status':status}):return 'existing_run'
    history=runs(api,filename,{'created':'>='+(at-timedelta(hours=1)).isoformat()})
    if any(r.get('status') in ACTIVE for r in history):return 'existing_run'
    dispatches=[r for r in history if r.get('event')=='workflow_dispatch']
    times=[policy.clock(r['created_at']) for r in dispatches]
    if any(t>at+timedelta(minutes=2) for t in times):raise ValueError('Future clock')
    if any(t>at-timedelta(minutes=15) for t in times):return 'cooldown'
    if len(times)>=2:return 'hourly_limit'
    return 'allowed'


def process(api,agent,commit,environment,now=lambda:datetime.now(timezone.utc)):
    claimed=agent({'action':'claim'})
    if claimed.get('version')!=1 or not isinstance(claimed.get('pending'),list) or len(claimed['pending'])>8 or len(claimed.get('tracking',[]))>8:raise ValueError('Invalid outbox')
    result={'claimed':len(claimed['pending']),'accepted':0,'blocked':0,'unconfirmed':0,'tracked':0,'trackingErrors':0}
    for item in claimed['tracking']:
        try:
            run=trusted_run(api('actions/runs/'+str(item['runId'])),TARGETS[item['batch']])
            conclusion=run.get('conclusion') if run['status']=='completed' else 'running'
            agent({'action':'status','id':item['id'],'runId':item['runId'],'conclusion':conclusion});result['tracked']+=1
        except Exception:result['trackingErrors']+=1
    for item in claimed['pending']:
        ident=item['id'];batch=item['batch']
        if not re.fullmatch('[a-f0-9]{32}',ident) or batch not in TARGETS:raise ValueError('Invalid request identity')
        try:
            if api('git/ref/heads/main')['object']['sha']!=commit:raise ValueError('Main changed')
            reason=decision(api,batch,now(),environment)
            # A second active/rate inspection immediately before the single attempt.
            if reason=='allowed':reason=decision(api,batch,now(),environment)
            if reason=='allowed' and api('git/ref/heads/main')['object']['sha']!=commit:raise ValueError('Main changed')
        except Exception:reason='inspection_failed'
        if reason!='allowed':
            agent({'action':'settle','id':ident,'state':'blocked','reason':reason});result['blocked']+=1;continue
        if agent({'action':'begin','id':ident}).get('allowed') is not True:
            result['blocked']+=1;continue
        # A server-side irreversible marker precedes the POST. Never auto-retry it.
        try:
            reply=api('actions/workflows/'+TARGETS[batch]+'/dispatches',method='POST',payload={'ref':'main'})
            rid=reply.get('workflow_run_id')
            if type(rid) is not int or rid<=0:raise ValueError('Dispatch identity unavailable')
            run=trusted_run(api('actions/runs/'+str(rid)),TARGETS[batch])
            if run['id']!=rid or run.get('event')!='workflow_dispatch':raise ValueError('Dispatch identity mismatch')
            agent({'action':'settle','id':ident,'state':'accepted','reason':'accepted','runId':rid});result['accepted']+=1
        except Exception:
            # Includes network ambiguity and legacy 204 responses, not proof of failure.
            agent({'action':'settle','id':ident,'state':'unknown','reason':'dispatch_unconfirmed'});result['unconfirmed']+=1
    return result


def initialize(remote):
    from deploy_google_access import upload_tree
    remote.directory(d.ROOT+'/.batch-monitoring')
    d.require(remote.read(d.ROOT+'/.batch-monitoring/.owner')==b'isegye-batch-monitoring:v1\n','Unowned monitor')
    if remote.info(FOLDER) is None:
        upload_tree(remote,FOLDER,{'.owner':MARKER,'.htaccess':b'Require all denied\n'},private=True)
    remote.directory(FOLDER)
    d.require(remote.read(FOLDER+'/.owner')==MARKER and remote.read(FOLDER+'/.htaccess')==b'Require all denied\n','Unowned control folder')


def verify_boundary():
    for path in ('/ops/batches/control','/ops/batches/manual.js','/ops/batches/manual.css'):
        code,body=d.http(d.ORIGIN+path)
        d.require(code==401 and b'csrf' not in body and b'actor' not in body,'Anonymous manual resource exposed')
    code,body=d.http(d.ORIGIN+'/ops/batches/_agent')
    d.require(code==404,'Worker capability boundary failed')
    for path in ('/.batch-monitoring/control/agent.json','/.batch-monitoring/control/queue.json'):
        code,body=d.http(d.ORIGIN+path)
        d.require(code in (403,404,503) and b'tokenHash' not in body and b'"actor"' not in body,'Private queue exposed')


def main():
    report={'status':'failed','checkedAt':datetime.now(timezone.utc).isoformat(),'realUserRequestCreated':False}
    resources=[];remote=None;grant=None;token=None
    password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        if os.getenv('GITHUB_REPOSITORY')!=REPO or os.getenv('GITHUB_REF')!='refs/heads/main':raise ValueError('Main required')
        # Completed workflows are not administrator requests; only explicit/scheduled wake-ups are allowed.
        if os.getenv('GITHUB_EVENT_NAME') not in ('schedule','workflow_dispatch','push'):raise ValueError('Unsupported worker event')
        api=GitHub();commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
        if not re.fullmatch('[0-9a-f]{40}',commit):raise ValueError('Invalid checkout commit')
        current=api('git/ref/heads/main')['object']['sha']
        event_sha=os.getenv('GITHUB_SHA','')
        if not re.fullmatch('[0-9a-f]{40}',current) or (event_sha and not re.fullmatch('[0-9a-f]{40}',event_sha)):
            raise ValueError('Invalid main or event identity')
        if current!=commit or (event_sha and event_sha!=commit):
            # A new main commit superseded this queued wake-up. Never claim requests,
            # open the server's control queue, or use a dispatch credential.
            report.update(status='superseded',reason='main_changed_before_processing')
            return 0
        if not password:raise ValueError('Transport credential missing')
        import paramiko
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
        transport=paramiko.Transport(sock);resources.append(transport)
        transport.banner_timeout=15;transport.auth_timeout=20;transport.get_security_options().key_types=('ssh-ed25519',)
        transport.start_client(timeout=15);key=transport.get_remote_server_key()
        fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name()=='ssh-ed25519' and fingerprint==d.FINGERPRINT,'Host key mismatch')
        transport.auth_password(d.USER,password);password=None
        client=paramiko.SFTPClient.from_transport(transport);resources.append(client);client.get_channel().settimeout(30)
        remote=VerifiedTransferRemote(client)
        from batch_monitor_storage import current_runtime,owned_folder
        owned_folder(remote);runtime,_=current_runtime(remote,ROOT)
        for name in ('BatchManual.php','manual.js','manual.css'):
            d.require(remote.read(d.ROOT+'/.auth-runtime/'+runtime+'/'+name)==(ROOT/'monitoring'/name).read_bytes(),'Manual runtime differs')
        initialize(remote);verify_boundary()
        # Only a hash is written; the random credential exists in runner memory for this job.
        token=secrets.token_hex(32);worker=os.environ['GITHUB_RUN_ID']
        if not re.fullmatch('[1-9][0-9]*',worker):raise ValueError('Worker identity missing')
        grant=(json.dumps({'tokenHash':hashlib.sha256(token.encode()).hexdigest(),'expires':int(datetime.now(timezone.utc).timestamp())+600,'worker':worker},sort_keys=True)+'\n').encode()
        from deploy_batch_monitor import private_replace
        private_replace(remote,FOLDER+'/agent.json',grant,remote.read(FOLDER+'/agent.json'))
        def agent(payload):
            req=urllib.request.Request(d.ORIGIN+'/ops/batches/_agent',data=json.dumps(payload).encode(),method='POST',
                headers={'Content-Type':'application/json','X-Isegye-Agent':token,'User-Agent':'IsegyeAdminWorker/1.0'})
            with urllib.request.build_opener(NoRedirect).open(req,timeout=25) as r:
                raw=r.read(65537)
                if len(raw)>65536:raise ValueError('Agent response oversized')
                return json.loads(raw)
        result=process(api,agent,commit,dict(os.environ))
        report.update(result,status='manual_worker_verified',commit=commit,runtime=runtime,
            administratorRecheckedAtClaim=True,oneDispatchAttemptPerRequest=True,
            privatePathsBlocked=True,anonymousControlDenied=True,githubTokenExported=False)
    except Exception as exc:
        report['errorCode']=type(exc).__name__
        # Do not leak signed URLs, credentials, request contents or account identifiers.
    finally:
        password=token=None
        if remote is not None and grant is not None:
            try:remote.remove_own(FOLDER+'/agent.json',grant)
            except Exception:report['credentialCleanupFailed']=True
        for resource in reversed(resources):
            try:resource.close()
            except Exception:pass
        (ROOT/'batch-manual-worker.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
    return 0 if report['status']=='manual_worker_verified' and not report.get('unconfirmed') and not report.get('trackingErrors') and not report.get('credentialCleanupFailed') else 1

if __name__=='__main__':sys.exit(main())
