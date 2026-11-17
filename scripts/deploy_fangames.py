#!/usr/bin/env python3
"""Replace only the existing admin-gated Playground preview, never the live app.

No gateway/runtime, routing, account, session, bank or other preview writes.
An immutable release and rollback pointer remain under .review-playground.
"""
from pathlib import Path
from datetime import datetime,timezone
import base64,hashlib,json,os,re,socket,stat,sys
import inour_sftp as d
import auth_routing as a
from deploy_verified_albums import VerifiedTransferRemote
from deploy_google_access import upload_tree
ROOT=Path(__file__).resolve().parents[1]
FOLDER=d.ROOT+'/.review-playground'
MARKER=b'isegye-playground:v1\n'

def payload(directory,commit):
    folder=Path(directory);d.require(bool(re.fullmatch('[0-9a-f]{40}',commit)),'Full commit required')
    for name in ('review.html','build-info.json'):
        p=folder/name;d.require(p.is_file() and not p.is_symlink(),'Missing artifact')
    html=(folder/'review.html').read_bytes();meta=json.loads((folder/'build-info.json').read_text())
    d.require(30000<len(html)<500000,'Artifact size')
    d.require(meta.get('branch')=='feature/isegye-fangames' and meta.get('commit')==commit and meta.get('mode')=='fangames-preview','Artifact identity')
    d.require(meta.get('counts',{}).get('games')==3 and meta['counts'].get('missions')==12 and meta['counts'].get('characters')==6 and meta['counts'].get('puzzles')==8,'Three complete games required')
    d.require(meta.get('productionWrites') is False and meta.get('liveFeedsConnected') is False and meta.get('externalMediaUsed') is False,'Preview isolation')
    d.require(meta.get('storageKey')=='isegye:review:fangames:v1','Storage namespace')
    text=html.decode();d.require('이세돌 팬게임' in text and 'noindex,nofollow,noarchive' in text and "connect-src 'none'" in text and "media-src 'none'" in text and "'unsafe-inline'" not in text and "'unsafe-eval'" not in text,'CSP policy')
    for tag in ('script','style'):
        blocks=re.findall('<'+tag+'>([\s\S]*?)</'+tag+'>',text);d.require(len(blocks)==1,'Unexpected inline block')
        digest=base64.b64encode(hashlib.sha256(blocks[0].encode()).digest()).decode();d.require('sha256-'+digest in text,'CSP hash differs')
    d.require(meta.get('htmlSha256')==d.digest(html) and meta.get('htmlBytes')==len(html),'Artifact checksum')
    expected=os.getenv('VERIFIED_HTML_SHA256','');d.require(not expected or expected==d.digest(html),'Browser-tested artifact differs')
    public=dict(meta,hosting='existing-admin-gate',url=d.ORIGIN+'/review-playground/',productionUIReplaced=False)
    metadata=(json.dumps(public,ensure_ascii=False,indent=2)+'\n').encode();d.require(len(metadata)<=8192,'Metadata size')
    release='p'+d.digest(html+metadata)[:12]
    pointer=(json.dumps({'release':release,'sha256':d.digest(html),'metadataSha256':d.digest(metadata),'commit':commit},sort_keys=True)+'\n').encode()
    return release,html,metadata,pointer

def allowed_write(path):
    d.write_path(path)
    d.require(path==d.ROOT+'/.deploy-lock' or path.startswith(FOLDER+'/'),'Only existing review folder is writable')
    return path

class PreviewRemote(VerifiedTransferRemote):
    def new(self,path,data):allowed_write(path);return super().new(path,data)
    def replace(self,path,data,expected):allowed_write(path);return super().replace(path,data,expected)
    def mkdir(self,path):allowed_write(path);return super().mkdir(path)
    def remove_own(self,path,expected):allowed_write(path);return super().remove_own(path,expected)

def replace_private(remote,path,data,old):
    allowed_write(path);remote.replace(path,data,old);remote.s.chmod(path,0o600)
    d.require(stat.S_IMODE(remote.info(path).st_mode)==0o600,'Private permissions')

def status():
    code,raw=d.http(d.ORIGIN+'/auth/status');d.require(code==200,'Access status unavailable')
    v=json.loads(raw);d.require(set(v)=={'authenticated','administrator','maintenance','allowed'} and all(type(x)is bool for x in v.values()) and not v['authenticated'] and not v['administrator'],'Unexpected anonymous role')
    return v

def publish(remote,commit,report):
    release,html,metadata,pointer=payload(ROOT/'fangames-dist',commit)
    remote.directory('/web');remote.directory(d.ROOT);remote.directory(FOLDER)
    d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Wrong site owner')
    d.require(remote.read(FOLDER+'/.owner')==MARKER and remote.read(FOLDER+'/.htaccess')==b'Require all denied\n','Existing owned preview required')
    for lock in ('/web/.yeop-migration-lock',d.ROOT+'/.auth-stage-lock'):d.require(remote.info(lock) is None,'Other maintenance active')
    lock=d.ROOT+'/.deploy-lock';remote.mkdir(lock);changed=False;old_pointer=None
    try:
        router=remote.read(d.ROOT+'/.htaccess');production,gated=a.release_of(router);d.require(gated,'Existing authorization required')
        entry=remote.read(d.ROOT+'/access.php');match=re.search(rb"/\.auth-runtime/(g[0-9a-f]{12})'",entry or b'');d.require(match is not None,'Unknown active runtime')
        runtime=match[1].decode();runtime_dir=d.ROOT+'/.auth-runtime/'+runtime;remote.directory(runtime_dir)
        handler=remote.read(runtime_dir+'/PlaygroundPreview.php');d.require(handler==(ROOT/'playground/hosting/PlaygroundPreview.php').read_bytes(),'Preview authorization handler changed')
        gateway=remote.read(runtime_dir+'/Gateway.php');gate=b"if (!$access['allowed'])";hook=b'// ISEGYE-PLAYGROUND:'
        d.require(gate in gateway and hook in gateway and gateway.index(gate)<gateway.index(hook),'Preview must remain after access gate')
        protected=remote.snapshot()
        ui_files=[d.ROOT+'/_isegye_releases/'+production+'/'+n for n in ('index.html','src/app.js','build-info.json')]
        ui_hashes={p:d.digest(remote.read(p)) for p in ui_files}
        previews={}
        for name in ('review-1st','review-2nd','review-albums','review-fanmade'):
            value=remote.read(d.ROOT+'/.'+name+'/active.json')
            if value is not None:previews[name]=value
        before=status();baseline={p:d.http(d.ORIGIN+p) for p in ('/','/src/app.js','/auth/terms','/auth/privacy')}
        old_pointer=remote.read(FOLDER+'/active.json');d.require(old_pointer is not None,'Previous review pointer required')
        old=json.loads(old_pointer);d.require(bool(re.fullmatch('p[0-9a-f]{12}',old.get('release',''))),'Previous pointer identity')
        previous_html=remote.read(FOLDER+'/releases/'+old['release']+'/review.html')
        d.require(d.digest(previous_html)==old['sha256'],'Previous preview integrity')
        upload_tree(remote,FOLDER+'/releases/'+release,{'review.html':html,'build-info.json':metadata},private=True)
        backup=FOLDER+'/backups/fangames-'+os.urandom(10).hex()
        upload_tree(remote,backup,{'pointer.before':old_pointer},private=True)
        d.require(remote.read(d.ROOT+'/.htaccess')==router and remote.read(d.ROOT+'/access.php')==entry,'Concurrent production change')
        changed=True;replace_private(remote,FOLDER+'/active.json',pointer,old_pointer)
        d.require(remote.read(FOLDER+'/active.json')==pointer and remote.read(FOLDER+'/releases/'+release+'/review.html')==html and remote.read(FOLDER+'/releases/'+release+'/build-info.json')==metadata,'Published readback mismatch')
        d.require(status()==before,'Access policy changed')
        for p in ('/review-playground/','/review-playground/index.html','/review-playground/build-info.json'):
            code,body=d.http(d.ORIGIN+p);d.require(code==(503 if before['maintenance'] else 403) and b'const F=(()=>{' not in body,'Anonymous preview exposed')
        for p in ('/.review-playground/active.json','/.review-playground/releases/'+release+'/review.html'):
            code,body=d.http(d.ORIGIN+p);d.require(code in (403,404,503) and b'const F=(()=>{' not in body,'Private preview exposed')
        for p,value in baseline.items():d.require(d.http(d.ORIGIN+p)==value,'Operating response changed: '+p)
        d.require(remote.read(d.ROOT+'/.htaccess')==router and remote.read(d.ROOT+'/access.php')==entry and remote.read(runtime_dir+'/Gateway.php')==gateway and remote.read(runtime_dir+'/PlaygroundPreview.php')==handler,'Routing or runtime changed')
        d.require(remote.snapshot()==protected,'Shared files changed')
        d.require(all(d.digest(remote.read(p))==h for p,h in ui_hashes.items()),'Operating UI changed')
        d.require(all(remote.read(d.ROOT+'/.'+n+'/active.json')==v for n,v in previews.items()),'Other preview changed')
        d.require(remote.read(FOLDER+'/releases/'+old['release']+'/review.html')==previous_html,'Previous preview lost')
        report.update(status='gated_preview_published_and_verified',commit=commit,url=d.ORIGIN+'/review-playground/',release=release,previousRelease=old['release'],backup=backup.removeprefix(d.ROOT+'/'),htmlSha256=d.digest(html),counts=json.loads(metadata)['counts'],productionRelease=production,productionUIUnchanged=True,otherPreviewsUnchanged=True,sharedRouterUnchanged=True,authRuntimeUnchanged=True,accountStoreReadOrWritten=False,questionBankChanged=False,privatePathsBlocked=True,anonymousPreviewBlocked=True,requiresExistingAdministrator=True,realGoogleLoginPerformed=False,authorizedRenderingVerification='existing unchanged handler role tests and HTTP browser tests; live SFTP byte readback')
    except Exception:
        if changed:
            try:
                current=remote.read(FOLDER+'/active.json');d.require(current in (old_pointer,pointer),'Concurrent pointer change; rollback stopped')
                if current==pointer:replace_private(remote,FOLDER+'/active.json',old_pointer,pointer)
                report['rollbackRestoredPreviousPreview']=True
            except Exception:report['manualRecoveryRequired']=True
        raise
    finally:remote.parents(lock);remote.s.rmdir(lock)

def main():
    report={'status':'failed','checkedAt':datetime.now(timezone.utc).isoformat()};resources=[];password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        d.require(os.getenv('GITHUB_REPOSITORY')=='seirian/isegye-idol-fansite' and os.getenv('GITHUB_REF')=='refs/heads/feature/isegye-fangames','Feature branch only')
        d.require(os.getenv('REVIEW_DEPLOY_ENABLED')=='true' and os.getenv('PRODUCTION_PAUSED')!='true','Preview publication paused')
        d.require(bool(password),'Existing SFTP credential missing');commit=os.getenv('REVIEW_COMMIT','');payload(ROOT/'fangames-dist',commit)
        import paramiko
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock);t=paramiko.Transport(sock);resources.append(t);t.banner_timeout=15;t.auth_timeout=20;t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
        key=t.get_remote_server_key();fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name()=='ssh-ed25519' and fp==d.FINGERPRINT,'Host key mismatch; credential not sent')
        t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'Authentication incomplete');client=paramiko.SFTPClient.from_transport(t);resources.append(client);client.get_channel().settimeout(30)
        publish(PreviewRemote(client),commit,report)
    except Exception as exc:
        report['errorType']=type(exc).__name__
        if isinstance(exc,d.Stop):report['reason']=str(exc)
    finally:
        password=None
        for r in reversed(resources):
            try:r.close()
            except Exception:pass
        (ROOT/'review-fangames-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='gated_preview_published_and_verified' else 1
if __name__=='__main__':sys.exit(main())
