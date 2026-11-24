#!/usr/bin/env python3
"""Hourly, data-only publication. Fixed private folder; never writes auth/routing.

The official Search API is discovery only. Bounded browser-reviewed metadata is supplied by a separate credential-free step; direct Cafe/internal API requests remain forbidden.
Existing Google access gate serves this feed only to authorized visitors.
"""
from pathlib import Path
from datetime import datetime, timezone
import base64,hashlib,json,os,socket,sys,traceback
import inour_sftp as d
import schedule_feed as feed
import auth_routing
import notice_policy
import schedule_health
from collections import Counter
FOLDER=d.ROOT+'/.schedule-feed'
MARKER=b'isegye-schedule-feed:v1\n'
ALLOWED={'current.json','previous.json','.owner','.lock'}
def path(name):
    d.require(name in ALLOWED,'Unknown feed file')
    return FOLDER+'/'+name

def failure_report(err, stage):
    """Report bounded context, never arbitrary exception text or source titles."""
    result={'status':'failed','errorType':type(err).__name__,'stage':stage}
    import cafe_runtime
    if isinstance(err,cafe_runtime.CafeEvidenceError):
        result['errorCode']=err.code
        result['field']=err.field
        if err.articleId is not None:result['articleId']=err.articleId
        if err.sourceId is not None:result['sourceId']=err.sourceId
    elif isinstance(err,(d.Stop,feed.FeedError)):
        # These application exceptions already contain fixed, credential-free reasons.
        result['reason']=str(err)
    # A source location is useful even for unexpected exceptions whose message
    # could contain a remote response, user text or a credential.
    root=Path(__file__).resolve().parents[1]
    for frame in reversed(traceback.extract_tb(err.__traceback__)):
        try:relative=Path(frame.filename).resolve().relative_to(root)
        except ValueError:continue
        if relative.parts[0]=='scripts':
            result['location']={'file':relative.as_posix(),'line':frame.lineno,'function':frame.name}
            break
    return result

def publish(remote,collect=feed.collect,progress=None):
    progress=progress if progress is not None else {}
    progress['stage']='remote_preflight'
    remote.directory('/web');remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Wrong site owner')
    router=remote.read(d.ROOT+'/.htaccess') or b''
    release,gated=auth_routing.release_of(router)
    d.require(gated,'Authentication router required')
    meta=json.loads(remote.read(d.ROOT+'/_isegye_releases/'+release+'/build-info.json') or b'{}')
    d.require(meta.get('scheduleFeed',{}).get('schemaVersion')==1,'Schedule-enabled release not deployed')
    protected=remote.snapshot()
    if remote.info(FOLDER) is None:
        remote.mkdir(FOLDER);remote.s.chmod(FOLDER,0o700)
        remote.new(path('.owner'),MARKER);remote.s.chmod(path('.owner'),0o600)
    remote.directory(FOLDER)
    d.require(remote.read(path('.owner'))==MARKER,'Unowned feed directory')
    lock=('schedule:'+os.urandom(16).hex()).encode()
    d.require(remote.info(path('.lock')) is None,'Existing feed lock; no overwrite')
    remote.new(path('.lock'),lock);remote.s.chmod(path('.lock'),0o600)
    try:
        progress['stage']='previous_snapshot_validation'
        old=remote.read(path('current.json'))
        old_value=feed.validate(json.loads(old)) if old else None
        previous=feed.validate(notice_policy.clean_snapshot(old_value)) if old_value else None
        removed={k:len(old_value[k])-len(previous[k]) if old_value else 0 for k in ('news','events','forecasts')}
        progress['stage']='source_collection'
        collected=collect(previous=previous)
        progress['stage']='snapshot_validation'
        value=feed.validate(notice_policy.clean_snapshot(collected))
        value['collectionHealth']=schedule_health.assess(value)
        progress['stage']='publication_guard'
        raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
        d.require(remote.read(d.ROOT+'/.htaccess')==router,'Router changed during collection')
        d.require(remote.snapshot()==protected,'Protected file changed during collection')
        if old:
            progress['stage']='backup'
            backup=remote.read(path('previous.json'))
            # The rollback snapshot must not resurrect deleted general-user posts.
            clean_backup=(json.dumps(previous,ensure_ascii=False,indent=2)+'\n').encode()
            if backup is None:remote.new(path('previous.json'),clean_backup)
            else:remote.replace(path('previous.json'),clean_backup,backup)
            d.require(remote.read(path('previous.json'))==clean_backup,'Backup cleanup differs')
            remote.s.chmod(path('previous.json'),0o600)
        progress['stage']='publication_write'
        remote.replace(path('current.json'),raw,old)
        published_at=datetime.now(timezone.utc).isoformat()
        remote.s.chmod(path('current.json'),0o600)
        progress['stage']='publication_readback'
        d.require(remote.read(path('current.json'))==raw,'Feed bytes differ')
        progress['stage']='publication_report'
        return {'status':'published','generatedAt':value['generatedAt'],'sha256':d.digest(raw),
                'publishedAt':published_at,'readbackAt':datetime.now(timezone.utc).isoformat(),
                'verifiedReadback':True,'evidenceVersion':2,
                'counts':{k:len(value[k]) for k in ('events','news','forecasts')},
                'collectionHealth':value['collectionHealth'],
                'cafeNewsByKstDay':dict(Counter(feed.iso(r['publishedAt']).astimezone(feed.KST).date().isoformat() for r in value['news'] if r['sourceId']=='cafe-members' and r.get('publishedAt'))),
                'runtimeEvidenceCounts':{k:len(value.get('cafeEvidence',{}).get(k,[])) for k in ('notices','fanSeries')},
                'sources':{s['id']:s['state'] for s in value['sources']},
                'newsCountsBySource':{s['id']:sum(n['sourceId']==s['id'] for n in value['news']) for s in value['sources']},
                'cafeBatchCoverage':{s['id']:s.get('coverage') for s in value['sources'] if s['id'] in ('cafe-members','cafe-agency','fan-roundup')},
                'naverSearchProvider':'NAVER API HUB',
                'berrizCounts':{s:sum(r['sourceId']==s for k in ('news','events') for r in value[k]) for s in ('berriz-notice','berriz-calendar')},
                'berrizCoverage':{s['id']:s.get('coverage') for s in value['sources'] if s['id'].startswith('berriz-')},
                'publicationPolicy':'approved-authors-only-v1',
                'removedUnapprovedRows':removed,
                'previousSnapshotSanitized':bool(old),
                'unverifiedSearchRowsPublished':sum(r['sourceId']=='naver-search' for r in value['news']),
                'explicitlyExcludedUrlsAbsent':not any(r['sourceUrl'] in notice_policy.EXCLUDED_URLS for k in ('news','events','forecasts') for r in value[k]),
                'protectedFilesUnchanged':True,'accountStoreReadOrWritten':False}
    finally:remote.remove_own(path('.lock'),lock)

def main():
    result={'status':'failed'};resources=[];password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    progress={'stage':'preflight'}
    try:
        d.require(os.getenv('GITHUB_REPOSITORY')=='seirian/isegye-idol-fansite' and os.getenv('GITHUB_REF')=='refs/heads/main','Main only')
        d.require(os.getenv('PRODUCTION_PAUSED')!='true' and os.getenv('ISEGYE_SCHEDULE_PAUSED')!='true','Collection paused')
        d.require(bool(password),'SFTP credential missing')
        review_path=os.getenv('ISEGYE_CAFE_REVIEW_PATH')
        packet=None
        if review_path:
            progress['stage']='review_validation'
            import cafe_runtime
            packet=cafe_runtime.validate_packet(json.loads(Path(review_path).read_text()),feed.stamp())
        progress['stage']='sftp_connection'
        import paramiko
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
        t=paramiko.Transport(sock);resources.append(t);t.banner_timeout=15;t.auth_timeout=20
        t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
        k=t.get_remote_server_key();fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(k.asbytes()).digest()).decode().rstrip('=')
        d.require(k.get_name()=='ssh-ed25519' and fingerprint==d.FINGERPRINT,'Host key mismatch; password not sent')
        t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'SFTP authentication incomplete')
        c=paramiko.SFTPClient.from_transport(t);resources.append(c);c.get_channel().settimeout(30)
        result=publish(d.Remote(c),lambda **kw:feed.collect(**kw,cafe_review=packet),progress)
    except Exception as err:
        result=failure_report(err,progress['stage'])
    finally:
        password=None
        for r in reversed(resources):
            try:r.close()
            except Exception:pass
        Path('schedule-publication.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False))
    return 0 if result['status']=='published' else 1
if __name__=='__main__':sys.exit(main())
