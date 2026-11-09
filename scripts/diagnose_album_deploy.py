#!/usr/bin/env python3
"""Bounded read-only own-site diagnosis after a cancelled deployment."""
import base64,hashlib,json,os,re,socket,stat,time,urllib.request
from pathlib import Path
import paramiko
import inour_sftp as d
import auth_routing as a
r={'remoteWrites':0,'accountStoreRead':False,'status':'started'};start=time.monotonic();resources=[]
def save(stage):
 r['stage']=stage;r['elapsedSeconds']=round(time.monotonic()-start,2);Path('albums-deploy-diagnosis.json').write_text(json.dumps(r,indent=2)+'\n');print(stage,flush=True)
def get(path):
 req=urllib.request.Request('https://api.github.com/repos/seirian/isegye-idol-fansite/'+path,headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(req,timeout=15) as f:return json.load(f)
try:
 run=get('actions/runs/42647684665');r['previousRun']={k:run.get(k) for k in ('id','status','conclusion','head_sha','updated_at')};d.require(run['status']=='completed','Previous deploy still running');save('previous-run-completed')
 password=os.environ.pop('ISEGYE_SFTP_PASSWORD','');d.require(bool(password),'Missing existing credential')
 sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock)
 t=paramiko.Transport(sock);resources.append(t);t.banner_timeout=15;t.auth_timeout=20;t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
 key=t.get_remote_server_key();fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=');d.require(key.get_name()=='ssh-ed25519' and fp==d.FINGERPRINT,'Host key mismatch')
 t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'Not authenticated');s=paramiko.SFTPClient.from_transport(t);resources.append(s);s.get_channel().settimeout(20);remote=d.Remote(s);save('sftp-connected')
 remote.directory('/web');remote.directory(d.ROOT);d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Owner mismatch')
 router=remote.read(d.ROOT+'/.htaccess');release,gated=a.release_of(router);r['activeRelease']=release;r['gated']=gated;r['routerSha256']=d.digest(router);save('active-router-read')
 entry=remote.read(d.ROOT+'/access.php');r['entrySha256']=d.digest(entry);m=re.search(rb'/\.auth-runtime/(g[0-9a-f]{12})',entry);r['activeRuntime']=m[1].decode() if m else None
 raw=remote.read(d.ROOT+'/_isegye_releases/'+release+'/build-info.json');meta=json.loads(raw);r['activeBuild']={k:meta.get(k) for k in ('commit','mode','albumPromotion')};save('active-build-read')
 lock=d.ROOT+'/.deploy-lock';info=remote.info(lock);r['lock']={'exists':info is not None}
 if info:
  remote.directory(lock);r['lock'].update(empty=not s.listdir(lock),modified=info.st_mtime,mode=oct(stat.S_IMODE(info.st_mode)))
 target='r'+hashlib.sha256(b'a97822e7d324afd5268407e8ee1179b874d0577a:42647684665:1').hexdigest()[:12];r['attemptedRelease']=target;r['attemptedReleaseExists']=remote.info(d.ROOT+'/_isegye_releases/'+target) is not None
 r['runtimeDirectories']=sorted(s.listdir(d.ROOT+'/.auth-runtime'))[-15:];save('staging-state-read')
 for path in ('/auth/status','/'):
  code,data=d.http(d.ORIGIN+path);r.setdefault('public',{})[path]={'status':code,'sha256':d.digest(data)}
  if path=='/auth/status':r['public'][path]['state']=json.loads(data)
 r['status']='read_only_complete';save('complete')
except Exception as e:r['status']='failed';r['errorType']=type(e).__name__;save('error')
finally:
 for res in reversed(resources):
  try:res.close()
  except Exception:pass
 save(r.get('stage','finished'))
if r['status']!='read_only_complete':raise SystemExit(1)
