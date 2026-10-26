#!/usr/bin/env python3
"""Temporary isolated PHP capability check. No routing, users or login changes."""
import base64, hashlib, json, os, socket, sys, urllib.request
from pathlib import Path
from datetime import datetime, timezone
import paramiko
import inour_sftp as d

def main():
    report = {'checkedAt': datetime.now(timezone.utc).isoformat(), 'status': 'failed',
              'googleClientIdConfigured': bool(os.environ.pop('GOOGLE_CLIENT_ID', '')),
              'googleClientSecretConfigured': bool(os.environ.pop('GOOGLE_CLIENT_SECRET', '')),
              'routingModified': False, 'accountsCreated': False}
    resources=[]; r=None; s=None; path=None; folder=None; content=None
    password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        d.require(os.environ.get('GITHUB_REF')=='refs/heads/feature/google-access','Wrong branch')
        d.require(password, 'SFTP secret missing')
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
        transport=paramiko.Transport(sock);resources.append(transport)
        transport.get_security_options().key_types=('ssh-ed25519',)
        transport.start_client(timeout=15)
        key=transport.get_remote_server_key()
        fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        d.require(key.get_name()=='ssh-ed25519' and fp==d.FINGERPRINT,'Host key mismatch')
        transport.auth_password(d.USER,password);password=None
        d.require(transport.is_authenticated(),'Authentication failed')
        s=paramiko.SFTPClient.from_transport(transport);resources.append(s);s.get_channel().settimeout(20)
        r=d.Remote(s);r.directory(d.ROOT)
        d.require(r.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Ownership mismatch')
        before=r.snapshot();router=r.read(d.ROOT+'/.htaccess')
        d.require(d.managed_router(router),'Unknown router; stopped')
        d.require(r.info(d.ROOT+'/.deploy-lock') is None,'Deployment in progress')
        folder=d.ROOT+'/_isegye_releases/r'+os.urandom(6).hex()
        r.mkdir(folder)
        token=os.urandom(32).hex()
        content=('<?php\nif (!hash_equals("'+token+'", $_SERVER["HTTP_X_ISEGYE_PROBE"] ?? "")) { http_response_code(404); exit; }\n'
                 'header("Content-Type: application/json"); header("Cache-Control: no-store");\n'
                 '$drivers=class_exists("PDO") ? PDO::getAvailableDrivers() : [];\n'
                 'echo json_encode(["phpVersion"=>PHP_VERSION,"pdoSqlite"=>in_array("sqlite",$drivers,true),'
                 '"pdoMysql"=>in_array("mysql",$drivers,true),"curl"=>extension_loaded("curl"),'
                 '"openssl"=>extension_loaded("openssl"),"hash"=>extension_loaded("hash"),'
                 '"randomBytes"=>function_exists("random_bytes"),"isolatedDirectoryWritable"=>is_writable(dirname(__DIR__,2))]);\n').encode()
        path=folder+'/runtime.php';r.new(path,content)
        url=d.ORIGIN+folder[len(d.ROOT):]+'/runtime.php'
        req=urllib.request.Request(url,headers={'X-Isegye-Probe':token,'Cache-Control':'no-cache'})
        with urllib.request.urlopen(req,timeout=20) as resp:
            body=resp.read(4096);d.require(resp.status==200,'Runtime probe failed')
        runtime=json.loads(body)
        d.require(isinstance(runtime,dict) and 'phpVersion' in runtime,'PHP not executable')
        report['runtime']=runtime
        d.require(r.snapshot()==before and r.read(d.ROOT+'/.htaccess')==router,'Protected settings changed')
        report.update(status='verified',protectedFilesUnchanged=True)
    except Exception as exc:
        report['errorType']=type(exc).__name__
        if isinstance(exc,d.Stop):report['reason']=str(exc)
    finally:
        password=None
        if r and path and content:
            try:r.remove_own(path,content);report['probeRemoved']=True
            except Exception:report['cleanupFailed']=True;report['status']='failed'
        if s and folder:
            try:s.rmdir(folder);report['directoryRemoved']=True
            except Exception:report['cleanupFailed']=True;report['status']='failed'
        for obj in reversed(resources):
            try:obj.close()
            except Exception:pass
        Path('auth-preflight.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))
    return 0 if report['status']=='verified' else 1
if __name__=='__main__':sys.exit(main())
