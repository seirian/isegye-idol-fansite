#!/usr/bin/env python3
"""Feature-only preview publication behind existing Google/admin authorization.

No account/config/session access; no production UI, router or batch writes.
Only private preview files, immutable auth runtime and its managed entry change.
"""
from pathlib import Path
from datetime import datetime,timezone
import base64,hashlib,json,os,re,socket,stat,sys
import inour_sftp as d
import auth_routing as a
from build_review_2nd_host import HOOK,patched
from build_review_host import patched as first_patched
from deploy_google_access import upload_tree
from production_release import EXISTING

ROOT=Path(__file__).resolve().parents[1]
FOLDER=d.ROOT+'/.review-2nd'
MARKER=b'isegye-second-review:v1\n'

def payload(directory,commit):
    folder=Path(directory)
    d.require(bool(re.fullmatch('[0-9a-f]{40}',commit)), 'Full review commit required')
    for name in ('review.html','build-info.json'):
        p=folder/name;d.require(p.is_file() and not p.is_symlink(),'Review artifact missing')
    html=(folder/'review.html').read_bytes();meta=json.loads((folder/'build-info.json').read_text())
    d.require(10000<len(html)<9*1024*1024,'Unexpected review HTML size')
    d.require(meta.get('branch')=='feature/review-2nd' and meta.get('commit')==commit and meta.get('mode')=='isolated-preview','Review identity mismatch')
    text=html.decode();d.require('noindex,nofollow' in text and '2차 검토' in text and "'unsafe-inline'" not in text and "'unsafe-eval'" not in text,'Review HTML policy mismatch')
    for tag in ('script','style'):
        blocks=re.findall('<'+tag+'>([\\s\\S]*?)</'+tag+'>',text)
        d.require(len(blocks)==1,'Unexpected inline payload count')
        digest=base64.b64encode(hashlib.sha256(blocks[0].encode()).digest()).decode()
        d.require('sha256-'+digest in text,'Review CSP hash mismatch')
    public={k:meta[k] for k in ('review','branch','baseCommit','commit','builtAt','mode','snapshotAt','counts')}
    public.update(hosting='existing-admin-gate',url=d.ORIGIN+'/review-2nd/',productionUIReplaced=False)
    metadata=(json.dumps(public,ensure_ascii=False,indent=2)+'\n').encode()
    release='p'+d.digest(html+metadata)[:12]
    pointer=(json.dumps({'release':release,'sha256':d.digest(html),'metadataSha256':d.digest(metadata),'commit':commit},sort_keys=True)+'\n').encode()
    return release,html,metadata,pointer

def private_replace(remote,path,data,old):
    remote.replace(path,data,old);remote.s.chmod(path,0o600)
    d.require(stat.S_IMODE(remote.info(path).st_mode)==0o600,'Unsafe private permissions')

def anonymous_status():
    code,raw=d.http(d.ORIGIN+'/auth/status');d.require(code==200,'Access status unavailable')
    v=json.loads(raw);d.require(set(v)=={'authenticated','administrator','maintenance','allowed'} and not v['authenticated'] and not v['administrator'],'Unexpected anonymous privilege')
    return v

def publish(remote,commit,report):
    release,html,metadata,pointer=payload(ROOT/'review-2nd-dist',commit)
    runtime,files=a.bundle(ROOT/'auth-bundle')
    d.require(files['Gateway.php']==patched((ROOT/'auth/Gateway.php').read_text()).encode(),'Generated gateway differs')
    d.require(files['Review2Preview.php']==(ROOT/'review-2nd/hosting/Review2Preview.php').read_bytes(),'Preview handler differs')
    remote.directory('/web');remote.directory(d.ROOT)
    d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Wrong isolated site owner')
    for lock in ('/web/.yeop-migration-lock',d.ROOT+'/.auth-stage-lock'):
        d.require(remote.info(lock) is None,'Other maintenance in progress')
    lock=d.ROOT+'/.deploy-lock';remote.mkdir(lock)
    old_entry=new_entry=old_pointer=None;entry_changed=pointer_changed=False
    try:
        router=remote.read(d.ROOT+'/.htaccess');production,gated=a.release_of(router)
        d.require(gated,'Existing access gate required')
        protected=remote.snapshot()
        production_paths=[d.ROOT+'/_isegye_releases/'+production+'/'+n for n in ('index.html','build-info.json','src/app.js')]
        production_hashes={p:d.digest(remote.read(p)) for p in production_paths}
        before=anonymous_status()
        baseline={p:d.http(d.ORIGIN+p) for p in ('/','/auth/terms','/auth/privacy','/src/app.js','/build-info.json')}
        other_sites={u:d.http(u) for u in EXISTING}
        d.require(all(v[0]==200 for v in other_sites.values()),'Existing site unavailable before preview')
        entry_path=d.ROOT+'/access.php';old_entry=remote.read(entry_path)
        match=re.search(rb"/\.auth-runtime/(g[0-9a-f]{12})'",old_entry or b'')
        d.require(match is not None,'Unrecognized existing entry')
        old_runtime=match[1].decode();parent=d.ROOT+'/.auth-runtime';remote.directory(parent)
        old_folder=parent+'/'+old_runtime;remote.directory(old_folder)
        d.require(old_entry==a.entry(remote.read(old_folder+'/access.php.template'),old_runtime),'Existing entry changed')
        # Preserve the current identity/authorization/visual runtime byte-for-byte.
        for name in ('Store.php','Session.php','GoogleVerifier.php','View.php','access.php.template','terms.html','privacy.html','legal.css','client.js','google-client.js','account.css','style.css'):
            d.require(remote.read(old_folder+'/'+name)==files[name],'Current auth source changed: '+name)
        first_folder=d.ROOT+'/.review-1st'
        first_pointer=remote.read(first_folder+'/active.json')
        d.require(first_pointer is not None,'First review must already be installed')
        first_release=json.loads(first_pointer)['release']
        d.require(bool(re.fullmatch('p[0-9a-f]{12}',first_release)),'First review pointer invalid')
        first_html_path=first_folder+'/releases/'+first_release+'/review.html'
        first_html_hash=d.digest(remote.read(first_html_path))
        d.require(remote.read(old_folder+'/ReviewPreview.php')==files['ReviewPreview.php'],'First review handler changed')
        old_gateway=remote.read(old_folder+'/Gateway.php')
        d.require(old_gateway in (first_patched((ROOT/'auth/Gateway.php').read_text()).encode(),files['Gateway.php']),'Unknown gateway modification')
        upload_tree(remote,parent+'/'+runtime,files,private=True)
        if remote.info(FOLDER) is None:
            remote.mkdir(FOLDER);remote.s.chmod(FOLDER,0o700)
            remote.new(FOLDER+'/.owner',MARKER);remote.s.chmod(FOLDER+'/.owner',0o600)
            remote.new(FOLDER+'/.htaccess',b'Require all denied\n');remote.s.chmod(FOLDER+'/.htaccess',0o600)
        remote.directory(FOLDER)
        d.require(remote.read(FOLDER+'/.owner')==MARKER and remote.read(FOLDER+'/.htaccess')==b'Require all denied\n','Unowned review folder')
        for sub in ('releases','backups'):
            if remote.info(FOLDER+'/'+sub) is None:remote.mkdir(FOLDER+'/'+sub);remote.s.chmod(FOLDER+'/'+sub,0o700)
            remote.directory(FOLDER+'/'+sub)
        upload_tree(remote,FOLDER+'/releases/'+release,{'review.html':html,'build-info.json':metadata},private=True)
        old_pointer=remote.read(FOLDER+'/active.json')
        backup=FOLDER+'/backups/'+os.urandom(12).hex()
        upload_tree(remote,backup,{'entry.before':old_entry,**({'pointer.before':old_pointer} if old_pointer else {})},private=True)
        d.require(remote.read(d.ROOT+'/.htaccess')==router and remote.read(entry_path)==old_entry,'Concurrent gateway change')
        pointer_changed=True
        private_replace(remote,FOLDER+'/active.json',pointer,old_pointer)
        new_entry=a.entry(files['access.php.template'],runtime)
        entry_changed=True
        remote.replace(entry_path,new_entry,old_entry)
        d.require(remote.read(entry_path)==new_entry and remote.read(FOLDER+'/active.json')==pointer,'Activation readback mismatch')
        d.require(remote.read(FOLDER+'/releases/'+release+'/review.html')==html,'Published preview byte mismatch')
        now=anonymous_status();d.require(now==before,'Access policy changed')
        d.require(remote.read(first_folder+'/active.json')==first_pointer and d.digest(remote.read(first_html_path))==first_html_hash,'First review changed')
        first_code,first_body=d.http(d.ORIGIN+'/review-1st/')
        d.require(first_code==(503 if before['maintenance'] else 403) and b'const REVIEW_DATA=' not in first_body,'First review gate changed')
        for p,v in baseline.items():d.require(d.http(d.ORIGIN+p)==v,'Existing route changed: '+p)
        for p in ('/review-2nd/','/review-2nd/index.html','/review-2nd/build-info.json'):
            code,body=d.http(d.ORIGIN+p)
            d.require(code==(503 if before['maintenance'] else 403) and b'const REVIEW_DATA=' not in body,'Preview gate exposed content')
        for p in ('/.review-2nd/active.json','/.review-2nd/releases/'+release+'/review.html','/.auth-runtime/'+runtime+'/Review2Preview.php'):
            code,body=d.http(d.ORIGIN+p);d.require(code in (403,404,503) and body!=html and b'const REVIEW_DATA=' not in body,'Private preview path exposed')
        d.require(remote.snapshot()==protected and remote.read(d.ROOT+'/.htaccess')==router,'Shared routing changed')
        d.require(all(d.digest(remote.read(p))==value for p,value in production_hashes.items()),'Production UI files changed')
        d.require(all(d.http(u)==value for u,value in other_sites.items()),'Existing other site response changed')
        report.update(status='gated_preview_published_and_verified',commit=commit,url=d.ORIGIN+'/review-2nd/',release=release,runtime=runtime,htmlSha256=d.digest(html),productionRelease=production,productionUIUnchanged=True,firstReviewUnchanged=True,sharedRouterUnchanged=True,accountStoreReadOrWritten=False,privatePathsBlocked=True,anonymousPreviewBlocked=True,requiresExistingAdministrator=True,realGoogleLoginPerformed=False,authorizedRenderingVerification='local TLS synthetic accounts; live file bytes verified by SFTP readback')
    except Exception:
        try:
            if entry_changed:
                current=remote.read(d.ROOT+'/access.php')
                d.require(current in (old_entry,new_entry),'Concurrent entry change; rollback stopped')
                if current==new_entry:remote.replace(d.ROOT+'/access.php',old_entry,new_entry)
            if pointer_changed:
                current=remote.read(FOLDER+'/active.json')
                d.require(current in (old_pointer,pointer),'Concurrent preview change; rollback stopped')
                if current==pointer:
                    if old_pointer is None:remote.remove_own(FOLDER+'/active.json',pointer)
                    else:private_replace(remote,FOLDER+'/active.json',old_pointer,pointer)
            report['rollbackRestoredPreviousEntry']=True
        except Exception:report['manualRecoveryRequired']=True
        raise
    finally:remote.parents(lock);remote.s.rmdir(lock)

def main():
    report={'status':'failed','checkedAt':datetime.now(timezone.utc).isoformat()};resources=[]
    password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        d.require(os.getenv('GITHUB_REPOSITORY')=='seirian/isegye-idol-fansite' and os.getenv('GITHUB_REF')=='refs/heads/feature/review-2nd','Review branch only')
        d.require(os.getenv('REVIEW_DEPLOY_ENABLED')=='true' and os.getenv('PRODUCTION_PAUSED')!='true','Review publication paused')
        d.require(bool(password),'Existing SFTP credential missing')
        commit=os.getenv('REVIEW_COMMIT','');payload(ROOT/'review-2nd-dist',commit)
        import paramiko
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
        t=paramiko.Transport(sock);resources.append(t);t.banner_timeout=15;t.auth_timeout=20
        t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
        key=t.get_remote_server_key();fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name()=='ssh-ed25519' and fp==d.FINGERPRINT,'Host key mismatch; credential not sent')
        t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'SFTP authentication incomplete')
        client=paramiko.SFTPClient.from_transport(t);resources.append(client);client.get_channel().settimeout(30)
        publish(d.Remote(client),commit,report)
    except Exception as exc:
        report['errorType']=type(exc).__name__
        if isinstance(exc,d.Stop):report['reason']=str(exc)
    finally:
        password=None
        for r in reversed(resources):
            try:r.close()
            except Exception:pass
        (ROOT/'review-2nd-deployment.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(report,ensure_ascii=False))
    return 0 if report['status']=='gated_preview_published_and_verified' else 1
if __name__=='__main__':sys.exit(main())
