#!/usr/bin/env python3
"""Main-only, pinned-host, cumulative quiz data publication. Never touches site/account files."""
from pathlib import Path
from datetime import datetime,timezone
import base64,hashlib,json,os,socket,sys
import inour_sftp as d,auth_routing as routing,playground_bank as bank
from deploy_verified_albums import VerifiedTransferRemote
ROOT=Path(__file__).resolve().parents[1];WORK=ROOT/'playground-state';FOLDER=d.ROOT+'/.playground-bank';OWNER=b'isegye-playground-bank:v1\n'
NAMES={'.owner','.lock','current.json','previous.json','references.json'}
def path(n):
    d.require(n in NAMES,'Unexpected bank filename');return FOLDER+'/'+n

def guard():
    d.require(os.getenv('GITHUB_REPOSITORY')=='seirian/isegye-idol-fansite' and os.getenv('GITHUB_REF')=='refs/heads/main','Main only')
    d.require(os.getenv('PRODUCTION_PAUSED')!='true' and os.getenv('ISEGYE_PLAYGROUND_PAUSED')!='true','Playground publication paused')

def preflight(remote):
    remote.directory('/web');remote.directory(d.ROOT);d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Wrong site owner')
    router=remote.read(d.ROOT+'/.htaccess');rid,gated=routing.release_of(router);d.require(gated,'Existing gate required')
    meta=json.loads(remote.read(d.ROOT+'/_isegye_releases/'+rid+'/build-info.json') or b'{}');d.require(meta.get('playground',{}).get('schemaVersion')==1,'Playground production release not active')
    d.require(meta['playground'].get('seedVersion')==bank.seed()['version'],'Deployed question schema differs')
    if remote.info(FOLDER) is not None:
        remote.directory(FOLDER);d.require(remote.read(path('.owner'))==OWNER,'Unowned bank directory')
    return router,rid

def restore(remote):
    preflight(remote);WORK.mkdir(exist_ok=True)
    raw=remote.read(path('current.json'));refs=remote.read(path('references.json'));music=remote.read(d.ROOT+'/.music-feed/current.json')
    if raw:bank.validate_stored_feed(json.loads(raw));(WORK/'previous.json').write_bytes(raw)
    elif (WORK/'previous.json').exists():(WORK/'previous.json').unlink()
    if refs:(WORK/'references-before.json').write_bytes(refs)
    if music:(WORK/'music.json').write_bytes(music)
    return {'status':'restored','existingQuestions':len(json.loads(raw)['catalog']['questions']) if raw else len(bank.seed()['questions']),'musicFeedAvailable':bool(music)}

def publish(remote,candidate,discovery,references):
    now=datetime.now(timezone.utc);bank.validate_feed(candidate)
    d.require(0<=(now-bank.clock(candidate['generatedAt'])).total_seconds()<=7200 and discovery.get('status')=='checked','Stale or incomplete discovery')
    d.require(discovery.get('generatedAt')==candidate['generatedAt'],'Discovery mismatch')
    router,rid=preflight(remote)
    if remote.info(FOLDER) is None:
        remote.mkdir(FOLDER);remote.s.chmod(FOLDER,0o700);remote.new(path('.owner'),OWNER);remote.s.chmod(path('.owner'),0o600)
    token=os.urandom(24);d.require(remote.info(path('.lock')) is None,'Bank publisher already active');remote.new(path('.lock'),token)
    previous=remote.read(path('current.json'));previous_refs=remote.read(path('references.json'));activated=False;rraw=None
    try:
        old=bank.validate_stored_feed(json.loads(previous)) if previous else None
        d.require((old['sha256'] if old else None)==discovery.get('previousSha256'),'Bank changed after restore; rerun safely')
        if old:
            by={q['id']:q for q in candidate['catalog']['questions']}
            d.require(all(by.get(q['id'])==q for q in old['catalog']['questions']),'Existing question changed or removed')
            d.require(all(candidate['catalog']['sources'].get(k)==v for k,v in old['catalog']['sources'].items()),'Existing evidence changed')
        raw=bank.published_bytes(candidate);rraw=bank.encoded(references)
        d.require(len(raw)<=5000000 and len(rraw)<=400000,'Snapshot size')
        d.require(remote.read(d.ROOT+'/.htaccess')==router,'Concurrent production deployment')
        if previous:remote.replace(path('previous.json'),previous,remote.read(path('previous.json')));remote.s.chmod(path('previous.json'),0o600)
        remote.replace(path('references.json'),rraw,previous_refs);remote.s.chmod(path('references.json'),0o600)
        remote.replace(path('current.json'),raw,previous);activated=True;remote.s.chmod(path('current.json'),0o600)
        d.require(remote.read(path('current.json'))==raw and remote.read(path('references.json'))==rraw,'Bank readback failed')
        d.require(remote.read(d.ROOT+'/.htaccess')==router,'Production changed during bank publication')
        return {'status':'published','generatedAt':candidate['generatedAt'],'publishedAt':now.isoformat(),'verifiedReadback':True,'readbackAt':datetime.now(timezone.utc).isoformat(),'bankVerified':True,'sha256':candidate['sha256'],'questionCount':len(candidate['catalog']['questions']),'added':discovery.get('totalAdded',discovery['automaticAdded']),'automaticAdded':discovery['automaticAdded'],'reserveAdded':discovery.get('reserveAdded',0),'growth':candidate.get('growth',{}),'editorialRevision':candidate.get('editorialRevision'),'reviewedAdded':candidate.get('reviewedAdded',0),'referenceCandidates':len(references),'referenceWarnings':discovery['referenceWarnings'],'release':rid,'siteUIChanged':False,'accountStoreAccessed':False,'communityAutoPublished':False}
    except Exception:
        if activated and remote.read(path('current.json'))==raw:
            if previous is None:remote.remove_own(path('current.json'),raw)
            else:remote.replace(path('current.json'),previous,raw);remote.s.chmod(path('current.json'),0o600)
        if rraw is not None and remote.read(path('references.json'))==rraw:
            if previous_refs is None:remote.remove_own(path('references.json'),rraw)
            else:remote.replace(path('references.json'),previous_refs,rraw);remote.s.chmod(path('references.json'),0o600)
        raise
    finally:remote.remove_own(path('.lock'),token)

def main(mode):
    resources=[];result={'status':'failed'};password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        guard();d.require(mode in ('restore','publish') and bool(password),'Explicit mode and existing hosting credential required')
        import paramiko
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock);t=paramiko.Transport(sock);resources.append(t);t.banner_timeout=15;t.auth_timeout=20;t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
        key=t.get_remote_server_key();finger='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=');d.require(key.get_name()=='ssh-ed25519' and finger==d.FINGERPRINT,'Host key mismatch; credential not sent')
        t.auth_password(d.USER,password);password=None;d.require(t.is_authenticated(),'SFTP authentication failed');c=paramiko.SFTPClient.from_transport(t);resources.append(c);c.get_channel().settimeout(30);remote=VerifiedTransferRemote(c)
        result=restore(remote) if mode=='restore' else publish(remote,json.loads((WORK/'candidate.json').read_text()),json.loads((ROOT/'playground-discovery.json').read_text()),json.loads((WORK/'references.json').read_text()))
    except Exception as e:
        result['errorType']=type(e).__name__
        if isinstance(e,d.Stop):result['reason']=str(e)
    finally:
        password=None
        for r in reversed(resources):
            try:r.close()
            except Exception:pass
        (ROOT/('playground-restore.json' if mode=='restore' else 'playground-publication.json')).write_bytes(bank.encoded(result));print(json.dumps(result,ensure_ascii=False))
    return 0 if result['status'] in ('published','restored') else 1
if __name__=='__main__':sys.exit(main(sys.argv[1] if len(sys.argv)>1 else ''))
