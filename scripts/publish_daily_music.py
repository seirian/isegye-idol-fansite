"""Main-only, host-key-pinned, data-only music publication. Never changes a release or accounts."""
from pathlib import Path
from datetime import datetime,timezone
import base64,hashlib,json,os,socket,sys
import inour_sftp as d,auth_routing as routing,daily_music as music
DIR=d.ROOT+'/.music-feed';OWNER=b'isegye-daily-music:v1\n';NAMES={'.owner','.lock','current.json','previous.json'}
def path(name):
    d.require(name in NAMES,'Unexpected music path');return DIR+'/'+name

def parse_old(raw):
    if raw is None:return []
    doc=json.loads(raw);d.require(doc['schemaVersion']==1 and doc['feed']=='daily-music','Invalid previous music snapshot')
    return music.validate(doc['rows'])

def publish(remote,review):
    now=datetime.now(timezone.utc);when=music.clock(review['generatedAt'])
    d.require(0<=(now-when).total_seconds()<=7200 and review['schemaVersion']==1,'Stale discovery run')
    d.require(set(review['sources'])==set(music.CHANNELS) and all(v['state'] in ('ok','partial','error') for v in review['sources'].values()) and any(v['state']!='error' for v in review['sources'].values()),'No verified channel results')
    fresh=music.validate(review['rows']);d.require(all(r['checkedAt']==review['generatedAt'] and review['sources'][r['channelKey']]['state']!='error' for r in fresh),'Unverified row')
    remote.directory('/web');remote.directory(d.ROOT);d.require(remote.read(d.ROOT+'/.isegye-owner')==d.OWNER,'Wrong owner')
    router=remote.read(d.ROOT+'/.htaccess');rid,gated=routing.release_of(router);d.require(gated,'Access gate required')
    meta=json.loads(remote.read(d.ROOT+'/_isegye_releases/'+rid+'/build-info.json') or b'{}');d.require(meta.get('dailyMusic',{}).get('schemaVersion')==1,'Music-enabled release not active')
    if any(r['type'] in music.PERFORMANCE_TYPES or set(r)&music.OPTIONAL_FIELDS for r in fresh):d.require(meta['dailyMusic'].get('waktaverseFormats')==1,'Waktaverse music renderer not active')
    if any(r['type'] in music.EXTRAS for r in fresh):d.require(meta['dailyMusic'].get('officialFormats')==1,'Official format renderer not active')
    if remote.info(DIR) is None:
        remote.mkdir(DIR);remote.s.chmod(DIR,0o700);remote.new(path('.owner'),OWNER);remote.s.chmod(path('.owner'),0o600)
    remote.directory(DIR);d.require(remote.read(path('.owner'))==OWNER,'Unowned music folder')
    lock=os.urandom(24);d.require(remote.info(path('.lock')) is None,'Existing music lock');remote.new(path('.lock'),lock)
    try:
        old=remote.read(path('current.json'));prev=parse_old(old);rows=music.merge(prev,fresh)
        before={r['videoId'] for r in prev}; added=[r for r in rows if r['videoId'] not in before]
        value={'schemaVersion':1,'feed':'daily-music','generatedAt':review['generatedAt'],'rows':rows}
        raw=(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n').encode();d.require(len(raw)<=1500000,'Music snapshot too large')
        d.require(remote.read(d.ROOT+'/.htaccess')==router,'Active release changed')
        if old and raw!=old:
            backup=remote.read(path('previous.json'));remote.replace(path('previous.json'),old,backup);remote.s.chmod(path('previous.json'),0o600)
        if raw!=old:remote.replace(path('current.json'),raw,old);remote.s.chmod(path('current.json'),0o600)
        d.require(remote.read(path('current.json'))==raw,'Publication read-back mismatch')
        return {'status':'published','release':rid,'generatedAt':value['generatedAt'],'added':len(added),'totalAuto':len(rows),'newItems':added,'waktaverseIds':[r['videoId'] for r in rows if r['channelKey']=='c1'],'waktaverseHistory':review['sources']['c1'].get('historical'),'sha256':d.digest(raw),'sourceStates':{k:v['state'] for k,v in review['sources'].items()},'verifiedReadback':True}
    finally:remote.remove_own(path('.lock'),lock)

def main():
    result={'status':'failed'};resources=[];pw=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
    try:
        d.require(os.getenv('GITHUB_REF')=='refs/heads/main' and os.getenv('GITHUB_REPOSITORY')=='seirian/isegye-idol-fansite','Main only')
        d.require(os.getenv('PRODUCTION_PAUSED')!='true' and os.getenv('ISEGYE_MUSIC_PAUSED')!='true' and bool(pw),'Paused or missing credential')
        import paramiko
        sock=socket.create_connection((d.HOST,d.PORT),timeout=15);resources.append(sock);t=paramiko.Transport(sock);resources.append(t);t.banner_timeout=15;t.auth_timeout=20;t.get_security_options().key_types=('ssh-ed25519',);t.start_client(timeout=15)
        key=t.get_remote_server_key();fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=');d.require(key.get_name()=='ssh-ed25519' and fp==d.FINGERPRINT,'Host key mismatch')
        t.auth_password(d.USER,pw);pw=None;d.require(t.is_authenticated(),'SFTP auth failed');c=paramiko.SFTPClient.from_transport(t);resources.append(c);c.get_channel().settimeout(30)
        result=publish(d.Remote(c),json.loads(Path('music-discovery.json').read_text()))
    except Exception as e:
        result={'status':'failed','error':str(e) if isinstance(e,d.Stop) else type(e).__name__}
    finally:
        pw=None
        for r in reversed(resources):
            try:r.close()
            except Exception:pass
        Path('music-publication.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
    return int(result['status']!='published')
if __name__=='__main__':sys.exit(main())
