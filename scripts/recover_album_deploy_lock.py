#!/usr/bin/env python3
"""Remove only the empty lock left by the identified cancelled album deployment.
No release, router, gateway, credential, account or shared file is changed.
"""
import base64,hashlib,json,os,socket,stat,urllib.request
from pathlib import Path
import paramiko
import inour_sftp as d
import auth_routing as a
r={'status':'failed','accountStoreRead':False,'remoteWrites':0};resources=[]
try:
 req=urllib.request.Request('https://api.github.com/repos/seirian/isegye-idol-fansite/actions/runs/42647684665',headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(req,timeout=15) as f:run=json.load(f)
 d.require(run['status']=='completed' and run['conclusion']=='cancelled' and run['head_sha']=='a97822e7d324afd5268407e8ee1179b874d0577a','Failed run identity changed')
 password=os.environ.pop('ISEGYE_SFTP_PASSWORD','');d.require(bool(password),'Missing credential')
 sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock);t=paramiko.Transport(sock);resources.append(t);t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
 key=t.get_remote_server_key();fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=');d.require(key.get_name()=='ssh-ed25519' and fp==d.FINGERPRINT,'Host key mismatch')
 t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'SFTP auth failure');s=paramiko.SFTPClient.from_transport(t);resources.append(s);s.get_channel().settimeout(20);remote=d.Remote(s)
 remote.directory('/web');remote.directory(d.ROOT);d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Owner mismatch')
 router=remote.read(d.ROOT+'/.htaccess');entry=remote.read(d.ROOT+'/access.php');d.require(d.digest(router)=='dab7f571fe011b27d2f88e4513f501edde89c88090029744a6852831b48668ff' and d.digest(entry)=='52aac4898ab5bf86d262287aed5669ca7b1fdeb2e77df4e543ecaef149c67ee3','Active route changed; do not remove lock')
 d.require(a.release_of(router)==('rf933430dd28f',True),'Active release differs')
 lock=d.ROOT+'/.deploy-lock';info=remote.info(lock)
 if info is not None:
  remote.directory(lock);d.require(info.st_mtime==1794239700 and stat.S_IMODE(info.st_mode)==0o755 and not s.listdir(lock),'Lock not the diagnosed empty lock')
  remote.parents(lock);s.rmdir(lock);r['remoteWrites']=1
 d.require(remote.info(lock) is None,'Lock remains')
 d.require(remote.read(d.ROOT+'/.htaccess')==router and remote.read(d.ROOT+'/access.php')==entry,'Active files changed')
 r.update(status='known_cancelled_lock_removed',lockRemoved=True,activeRouterUnchanged=True,activeGatewayUnchanged=True,previousRelease='rf933430dd28f',cancelledRun=42647684665,partialInactiveReleasePreserved=True)
except Exception as e:r['errorType']=type(e).__name__
finally:
 for x in reversed(resources):
  try:x.close()
  except Exception:pass
 Path('albums-lock-recovery.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
if r['status']!='known_cancelled_lock_removed':raise SystemExit(1)
