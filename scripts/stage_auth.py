#!/usr/bin/env python3
"""Stage verified auth runtime and EMPTY private storage; never change live routing.

No administrator is pre-created. Missing Google configuration is reported, never
replaced with a fake client or test user. No credentials/private files enter artifacts.
"""
import base64,hashlib,hmac,json,os,re,socket,stat,sys,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import paramiko
import inour_sftp as d
ADMIN_EMAIL_SHA256='085d03d99bc76950a59556ad8de6b26d8f20a48f7fce98c8a1fdae8fa8e03916'

def main():
    report={'checkedAt':datetime.now(timezone.utc).isoformat(),'status':'failed','routingModified':False,'administratorPrecreated':False,'productionLoginEnabled':False}
    resources=[];r=None;s=None;probe=None;folder=None;body=None;lock=None
    password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    client=os.environ.pop('ISEGYE_GOOGLE_CLIENT_ID','').strip()
    try:
        d.require(os.getenv('GITHUB_REF')=='refs/heads/feature/google-access','Wrong branch')
        d.require(password,'SFTP secret missing')
        d.require(not client or re.fullmatch(r'[0-9]+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com',client),'Malformed Google client ID')
        bundle=Path('auth-bundle');manifest=json.loads((bundle/'manifest.json').read_text())
        runtime=manifest['runtime'];d.require(re.fullmatch(r'g[0-9a-f]{12}',runtime),'Invalid runtime ID')
        files={}
        for name,digest in manifest['files'].items():
            p=bundle/name;d.write_path(d.ROOT+'/.auth-runtime/'+runtime+'/'+name)
            d.require(p.is_file() and not p.is_symlink() and hashlib.sha256(p.read_bytes()).hexdigest()==digest,'Bundle hash mismatch')
            files[name]=p.read_bytes()
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
        t=paramiko.Transport(sock);resources.append(t);t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
        key=t.get_remote_server_key();fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name()=='ssh-ed25519' and fp==d.FINGERPRINT,'Host key mismatch')
        t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'Authentication failed')
        s=paramiko.SFTPClient.from_transport(t);resources.append(s);s.get_channel().settimeout(30);r=d.Remote(s)
        r.directory(d.ROOT);d.require(r.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Ownership mismatch')
        d.require(r.info(d.ROOT+'/.deploy-lock') is None,'Another deployment is running')
        wanted_lock=d.ROOT+'/.auth-stage-lock'
        d.require(r.info(wanted_lock) is None,'Another auth staging operation is running')
        r.mkdir(wanted_lock);lock=wanted_lock
        before=r.snapshot();router=r.read(d.ROOT+'/.htaccess');d.require(d.managed_router(router),'Active routing is not the audited public router')
        baseline=d.http(d.ORIGIN+'/');d.require(baseline[0]==200,'Public home not healthy')
        parent=d.ROOT+'/.auth-runtime'
        if r.info(parent) is None:r.mkdir(parent);s.chmod(parent,0o700)
        r.directory(parent);target=parent+'/'+runtime
        if r.info(target) is None:r.mkdir(target);s.chmod(target,0o700)
        for name,data in files.items():
            current=target
            for piece in name.split('/')[:-1]:
                current+='/'+piece
                if r.info(current) is None:r.mkdir(current);s.chmod(current,0o700)
            path=target+'/'+name
            existing=r.read(path)
            if existing is None:r.new(path,data);s.chmod(path,0o600)
            else:d.require(existing==data,'Immutable runtime content mismatch')
        private=d.ROOT+'/.auth-private';owner=b'isegye-google-access:private-store:v1\n'
        if r.info(private) is None:
            r.mkdir(private);s.chmod(private,0o700)
            r.new(private+'/.owner',owner);s.chmod(private+'/.owner',0o600)
        r.directory(private);d.require(r.read(private+'/.owner')==owner,'Unrecognized private directory')
        d.require(stat.S_IMODE(r.info(private).st_mode)==0o700,'Private permissions unsafe')
        config_path=private+'/config.json'
        if r.info(config_path) is None:
            d.require(r.info(private+'/accounts.json') is None,'Accounts exist without identity key; refused reset')
            site_key=os.urandom(32)
            config={'origin':d.ORIGIN,'clientId':client,'siteKey':base64.b64encode(site_key).decode(),
                    'adminEmailDigest':hmac.new(site_key,b'admin-email\0'+ADMIN_EMAIL_SHA256.encode(),hashlib.sha256).hexdigest()}
            r.new(config_path,json.dumps(config).encode());s.chmod(config_path,0o600);site_key=None
            initial=b'{"schema":1,"administrator":null,"accounts":{}}\n'
            r.new(private+'/accounts.json',initial);s.chmod(private+'/accounts.json',0o600)
            r.new(private+'/accounts.lock',b'');s.chmod(private+'/accounts.lock',0o600)
        else:
            config=json.loads(r.read(config_path))
            # Staging must never reset accounts, change identity keys or silently replace OAuth configuration.
            d.require(not client or config.get('clientId') in ('',client),'Client ID changed; explicit review required')
        if r.info(private+'/.htaccess') is None:r.new(private+'/.htaccess',b'Require all denied\n');s.chmod(private+'/.htaccess',0o600)
        if r.info(private+'/sessions') is None:r.mkdir(private+'/sessions');s.chmod(private+'/sessions',0o700)
        state=json.loads(r.read(private+'/accounts.json'))
        report.update(storagePrepared=True,accountCount=len(state['accounts']),administratorRegistered=state['administrator'] is not None,
                      maintenanceActive=state['administrator'] is not None,googleClientIdConfigured=bool(config.get('clientId')),runtime=runtime)
        # Verify the hosting PHP can read private modules/store, without creating any account.
        wanted_folder=d.ROOT+'/_isegye_releases/r'+os.urandom(6).hex()
        r.mkdir(wanted_folder);folder=wanted_folder
        token=os.urandom(32).hex()
        body=('<?php\nif(!hash_equals("'+token+'",$_SERVER["HTTP_X_ISEGYE_PROBE"]??"")){http_response_code(404);exit;}\n'
              'ini_set("display_errors","0");header("Content-Type: application/json");header("Cache-Control:no-store");'
              '$root=dirname(__DIR__,2);require $root."/.auth-runtime/'+runtime+'/vendor/autoload.php";')
        body+=('require_once $root."/.auth-runtime/'+runtime+'/Store.php";'
               '$c=json_decode(file_get_contents($root."/.auth-private/config.json"),true);'
               '$s=new Isegye\\Access\\Store($root."/.auth-private",base64_decode($c["siteKey"]),$c["adminEmailDigest"]);'
               '$a=$s->access(null);$p=$root."/.auth-private/.runtime-write-'+os.urandom(8).hex()+'";'
               '$written=file_put_contents($p,"check");if(is_file($p))unlink($p);'
               'echo json_encode(["storeReadable"=>true,"storeWritable"=>$written===5,"publicBeforeAdministrator"=>$a["allowed"],'
               '"maintenance"=>$a["maintenance"],"httpsFlag"=>($_SERVER["HTTPS"]??"")==="on","serverPort"=>(string)($_SERVER["SERVER_PORT"]??"")]);')
        body=body.encode();probe=folder+'/ready.php';r.new(probe,body)
        req=urllib.request.Request(d.ORIGIN+folder[len(d.ROOT):]+'/ready.php',headers={'X-Isegye-Probe':token})
        with urllib.request.urlopen(req,timeout=20) as response:ready=json.loads(response.read(4096))
        d.require(ready.get('storeReadable') and ready.get('storeWritable'),'PHP private-store access failed')
        report['runtimeCheck']=ready
        for suffix in ('/.auth-private/config.json','/.auth-private/accounts.json','/.auth-runtime/'+runtime+'/Store.php'):
            d.require(d.http(d.ORIGIN+suffix)[0] in (403,404),'Private auth file publicly exposed')
        d.require(r.snapshot()==before and r.read(d.ROOT+'/.htaccess')==router,'Protected settings changed')
        d.require(d.http(d.ORIGIN+'/')==baseline,'Public home changed during staging')
        report.update(status='staged_inactive',publicSiteUnchanged=True,protectedFilesUnchanged=True,privatePathsBlocked=True)
    except Exception as exc:
        report['errorType']=type(exc).__name__
        if isinstance(exc,d.Stop):report['reason']=str(exc)
    finally:
        password=None
        if r and probe and body:
            try:r.remove_own(probe,body);report['probeRemoved']=True
            except Exception:report['status']='failed';report['cleanupFailed']=True
        if s and folder:
            try:s.rmdir(folder)
            except Exception:report['status']='failed';report['cleanupFailed']=True
        if s and lock:
            try:s.rmdir(lock)
            except Exception:report['status']='failed';report['cleanupFailed']=True
        for obj in reversed(resources):
            try:obj.close()
            except Exception:pass
        Path('auth-stage.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
    return 0 if report['status']=='staged_inactive' else 1
if __name__=='__main__':sys.exit(main())
