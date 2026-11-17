"""Main-only monitoring storage. No account/session access, no arbitrary deletions.

Only this owned monitor's content-addressed snapshot releases are pruned. The
active and rollback snapshots plus 22 recent snapshots are retained. The 90-day
observation summaries live in every current snapshot, not in per-refresh files.
"""
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib, json, re, stat
import inour_sftp as d

FOLDER = d.ROOT+'/.batch-monitoring'
MARKER = b'isegye-batch-monitoring:v1\n'
KEEP_RELEASES = 24
MAX_RELEASES = 250
FILES = {'index.html','monitor.css','monitor.js','data.json','manifest.json'}
ROUTES = ('/ops/batches','/ops/batches/','/ops/batches/data.json','/ops/batches/monitor.css','/ops/batches/monitor.js')


def validate_snapshot(doc, commit, at=None):
    from batch_monitor_snapshot import META, stamp
    at=at or datetime.now(timezone.utc)
    d.require(isinstance(doc,dict) and doc.get('schemaVersion')==1 and doc.get('readOnly') is True,
              'Invalid monitor snapshot schema')
    d.require(doc.get('mode')=='production' and doc.get('repository')=='seirian/isegye-idol-fansite'
              and doc.get('collectorCommit')==commit and doc.get('mainCommit')==commit,
              'Snapshot does not match current main')
    d.require(doc.get('scheduledRefreshEnabled') is True and doc.get('refreshEverySeconds')==600,
              'Missing production refresh policy')
    d.require(at-timedelta(minutes=15)<=stamp(doc.get('checkedAt'))<=at+timedelta(minutes=2),
              'Collector snapshot expired before publication')
    rows=doc.get('batches')
    d.require(isinstance(rows,list) and len(rows)==len(META) and {r.get('key') for r in rows}==set(META),
              'Incomplete monitor categories')
    states={'healthy','attention','running','paused','unknown'}
    d.require(all(r.get('state') in states and r.get('dataState') in states for r in rows),
              'Unknown monitor state')


def verify_anonymous():
    for path in ROUTES:
        code,body=d.http(d.ORIGIN+path)
        d.require(code==401 and body==b'Administrator access required', 'Monitor anonymous access boundary failed')


def current_runtime(remote, root):
    # No read of .auth-private, identities, cookies, credentials, or sessions.
    from build_batch_monitor_host import patched
    from auth_routing import entry
    remote.directory(d.ROOT+'/.auth-runtime')
    raw=remote.read(d.ROOT+'/access.php')
    match=re.search(rb"/\.auth-runtime/(g[0-9a-f]{12})'",raw or b'')
    d.require(match is not None,'Managed monitor runtime missing')
    runtime=match[1].decode(); folder=d.ROOT+'/.auth-runtime/'+runtime
    remote.directory(folder)
    d.require(raw==entry(remote.read(folder+'/access.php.template'),runtime),'Managed entry mismatch')
    d.require(remote.read(folder+'/Gateway.php')==patched((root/'auth/Gateway.php').read_text()).encode(),
              'Permanent monitor route not deployed for this main revision')
    d.require(remote.read(folder+'/BatchMonitor.php')==(root/'monitoring/BatchMonitor.php').read_bytes(),
              'Active monitor handler differs')
    return runtime, raw


def owned_folder(remote):
    remote.directory('/web');remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Wrong isolated owner')
    remote.directory(FOLDER)
    d.require(remote.read(FOLDER+'/.owner')==MARKER and remote.read(FOLDER+'/.htaccess')==b'Require all denied\n',
              'Unowned monitoring folder')
    remote.directory(FOLDER+'/releases')


def prune_candidates(entries, active, previous):
    """Pure bounded policy. Every actual deletion is revalidated separately."""
    d.require(len(entries)<=MAX_RELEASES,'Monitor storage inspection budget exceeded')
    valid=[]
    for info in entries:
        name=info.filename
        d.require(re.fullmatch('m[0-9a-f]{12}',name) is not None and stat.S_ISDIR(info.st_mode)
                  and info.st_uid==d.UID,'Unknown object in monitoring releases')
        valid.append((info.st_mtime,name))
    ordered=[name for _,name in sorted(valid,reverse=True)]
    keep={name for name in (active,previous) if name is not None}
    for name in ordered:
        if len(keep)>=KEEP_RELEASES:break
        keep.add(name)
    return [name for name in ordered if name not in keep]


def prune(remote, active, previous):
    owned_folder(remote)
    entries=remote.s.listdir_attr(FOLDER+'/releases')
    doomed=prune_candidates(entries,active,previous)
    # Validate ALL candidates before removing any. Unknown/symlink files halt cleanup.
    verified=[]
    for name in doomed:
        folder=FOLDER+'/releases/'+name;remote.directory(folder)
        children=remote.s.listdir_attr(folder)
        d.require({x.filename for x in children}==FILES and len(children)==len(FILES),'Unknown release files')
        d.require(all(stat.S_ISREG(x.st_mode) and x.st_uid==d.UID and 0<=x.st_size<=4_000_000 for x in children),
                  'Unsafe cleanup file')
        raw=remote.read(folder+'/manifest.json');manifest=json.loads(raw)
        d.require('m'+d.digest(raw)[:12]==name and manifest.get('schemaVersion')==1
                  and set(manifest.get('files',{}))==FILES-{'manifest.json'},'Cleanup manifest differs')
        payload={'manifest.json':raw}
        for file,digest in manifest['files'].items():
            payload[file]=remote.read(folder+'/'+file)
            d.require(payload[file] is not None and d.digest(payload[file])==digest,'Cleanup file hash mismatch')
        verified.append((folder,payload))
    for folder,payload in verified:
        # Protect a concurrent pointer change even if external writers ignore the lock.
        point=json.loads(remote.read(FOLDER+'/active.json'))
        d.require(point.get('release')==active,'Active snapshot changed during cleanup')
        for name,raw in payload.items():remote.remove_own(folder+'/'+name,raw)
        remote.directory(folder);remote.s.rmdir(folder)
    return len(verified)


def refresh(remote, doc, commit, report, root):
    from deploy_batch_monitor import old_snapshot, release_payload, private_replace
    from deploy_google_access import upload_tree
    from batch_monitor_snapshot import merge_observations
    from auth_routing import release_of
    validate_snapshot(doc,commit)
    remote.directory('/web');remote.directory(d.ROOT)
    for path in ('/web/.yeop-migration-lock',d.ROOT+'/.auth-stage-lock'):
        d.require(remote.info(path) is None,'Other maintenance in progress')
    lock=d.ROOT+'/.deploy-lock';remote.mkdir(lock)
    previous=pointer=None;changed=False
    try:
        owned_folder(remote)
        runtime, entry=current_runtime(remote,root)
        router=remote.read(d.ROOT+'/.htaccess');_,gated=release_of(router)
        d.require(gated,'Authentication router required')
        verify_anonymous()
        previous=remote.read(FOLDER+'/active.json')
        old=old_snapshot(remote,previous)
        d.require(not old or old.get('checkedAt','')<=doc['checkedAt'],'New snapshot older than active snapshot')
        entries=remote.s.listdir_attr(FOLDER+'/releases')
        d.require(len(entries)<MAX_RELEASES,'Monitor storage hard limit reached; cleanup required')
        doc=merge_observations(old,doc)
        name,files,pointer=release_payload(doc)
        upload_tree(remote,FOLDER+'/releases/'+name,files,private=True)
        # Constant-size rollback pointer; no per-refresh unbounded backup directories.
        if previous is not None:
            private_replace(remote,FOLDER+'/previous.json',previous,remote.read(FOLDER+'/previous.json'))
        d.require(remote.read(d.ROOT+'/access.php')==entry and remote.read(d.ROOT+'/.htaccess')==router,
                  'Authentication routing changed before snapshot activation')
        changed=True;private_replace(remote,FOLDER+'/active.json',pointer,previous)
        for file,raw in files.items():
            d.require(remote.read(FOLDER+'/releases/'+name+'/'+file)==raw,'Published snapshot readback mismatch')
        verify_anonymous()
        code,body=d.http(d.ORIGIN+'/.batch-monitoring/releases/'+name+'/data.json')
        d.require(code in (403,404,503) and body!=files['data.json'],'Private monitoring data exposed')
        d.require(remote.read(d.ROOT+'/access.php')==entry and remote.read(d.ROOT+'/.htaccess')==router,
                  'Authentication runtime or router changed')
        report.update(status='monitor_snapshot_verified',url=d.ORIGIN+'/ops/batches/',commit=commit,
            runtime=runtime,release=name,sourceCheckedAt=doc['checkedAt'],verifiedAt=datetime.now(timezone.utc).isoformat(),
            snapshotSha256=d.digest(files['data.json']),readOnly=True,scheduledRefreshEnabled=True,
            refreshEverySeconds=600,anonymousUIAndAPIDenied=True,privatePathsBlocked=True,
            requiresExistingAdministrator=True,authenticationRuntimeUnchanged=True,accountConfigOrSessionAccessed=False,
            observationCount=len(doc['observations']),realGoogleLoginPerformed=False,
            authorizedRenderingVerification='local TLS role tests and exact deployed code/data byte checks')
    except Exception:
        if changed:
            current=remote.read(FOLDER+'/active.json')
            d.require(current in (previous,pointer),'Concurrent snapshot change; rollback stopped')
            if current==pointer:
                if previous is None:remote.remove_own(FOLDER+'/active.json',pointer)
                else:private_replace(remote,FOLDER+'/active.json',previous,pointer)
            report['previousPointerRestored']=True
        raise
    else:
        # Cleanup errors do not mislabel a verified publication as rolled back.
        try:
            prior=json.loads(previous)['release'] if previous else None
            report['prunedReleases']=prune(remote,name,prior)
            report['retainedReleaseLimit']=KEEP_RELEASES
        except Exception as exc:
            report['retentionError']=type(exc).__name__
    finally:
        remote.parents(lock);remote.s.rmdir(lock)
