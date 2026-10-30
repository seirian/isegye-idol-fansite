#!/usr/bin/env python3
"""Hourly, data-only publication. Fixed private folder; never writes auth/routing.

The official Cafe Search API is optional. Cafe/internal API crawling is forbidden.
Existing Google access gate serves this feed only to authorized visitors.
"""
from pathlib import Path
import base64,hashlib,json,os,socket,sys
import inour_sftp as d
import schedule_feed as feed
import auth_routing
FOLDER=d.ROOT+'/.schedule-feed'
MARKER=b'isegye-schedule-feed:v1\n'
ALLOWED={'current.json','previous.json','.owner','.lock'}
def path(name):
    d.require(name in ALLOWED,'Unknown feed file')
    return FOLDER+'/'+name

def publish(remote,collect=feed.collect):
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
        old=remote.read(path('current.json'))
        previous=feed.validate(json.loads(old)) if old else None
        value=feed.validate(collect(previous=previous))
        raw=(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
        d.require(remote.read(d.ROOT+'/.htaccess')==router,'Router changed during collection')
        d.require(remote.snapshot()==protected,'Protected file changed during collection')
        if old:
            backup=remote.read(path('previous.json'))
            if backup is None:remote.new(path('previous.json'),old)
            else:remote.replace(path('previous.json'),old,backup)
            remote.s.chmod(path('previous.json'),0o600)
        remote.replace(path('current.json'),raw,old)
        remote.s.chmod(path('current.json'),0o600)
        d.require(remote.read(path('current.json'))==raw,'Feed bytes differ')
        return {'status':'published','generatedAt':value['generatedAt'],'sha256':d.digest(raw),
                'counts':{k:len(value[k]) for k in ('events','news','forecasts')},
                'sources':{s['id']:s['state'] for s in value['sources']},
                'newsCountsBySource':{s['id']:sum(n['sourceId']==s['id'] for n in value['news']) for s in value['sources']},
                'naverSearchProvider':'NAVER API HUB',
                'protectedFilesUnchanged':True,'accountStoreReadOrWritten':False}
    finally:remote.remove_own(path('.lock'),lock)

def main():
    result={'status':'failed'};resources=[];password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        d.require(os.getenv('GITHUB_REPOSITORY')=='seirian/isegye-idol-fansite' and os.getenv('GITHUB_REF')=='refs/heads/main','Main only')
        d.require(os.getenv('PRODUCTION_PAUSED')!='true' and os.getenv('ISEGYE_SCHEDULE_PAUSED')!='true','Collection paused')
        d.require(bool(password),'SFTP credential missing')
        import paramiko
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
        t=paramiko.Transport(sock);resources.append(t);t.banner_timeout=15;t.auth_timeout=20
        t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
        k=t.get_remote_server_key();fingerprint='SHA256:'+base64.b64encode(hashlib.sha256(k.asbytes()).digest()).decode().rstrip('=')
        d.require(k.get_name()=='ssh-ed25519' and fingerprint==d.FINGERPRINT,'Host key mismatch; password not sent')
        t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'SFTP authentication incomplete')
        c=paramiko.SFTPClient.from_transport(t);resources.append(c);c.get_channel().settimeout(30)
        result=publish(d.Remote(c))
    except Exception as err:
        result={'status':'failed','errorType':type(err).__name__}
        if isinstance(err,(d.Stop,feed.FeedError)):result['reason']=str(err)
    finally:
        password=None
        for r in reversed(resources):
            try:r.close()
            except Exception:pass
        Path('schedule-publication.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(result,ensure_ascii=False))
    return 0 if result['status']=='published' else 1
if __name__=='__main__':sys.exit(main())
