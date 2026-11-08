"""Optional official Spotify Web API adapter; secrets stay on the CI runner."""
from datetime import datetime,timezone
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlencode,urlparse
import base64,json,os,time
from collect_album_domestic import norm,ARTISTS
class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Spotify redirect refused')
def request(url,headers,data=None):
    u=urlparse(url)
    if u.scheme!='https' or u.hostname not in ('accounts.spotify.com','api.spotify.com') or u.username or u.password:raise ValueError('Spotify URL refused')
    with build_opener(NoRedirect).open(Request(url,data=data,headers=headers),timeout=20) as r:
        raw=r.read(2000001)
        if len(raw)>2000000:raise ValueError('Spotify response too large')
        return json.loads(raw)
def collect(result,songs):
    client=os.environ.get('ISEGYE_SPOTIFY_CLIENT_ID','');secret=os.environ.get('ISEGYE_SPOTIFY_CLIENT_SECRET','')
    stamp=datetime.now(timezone.utc).isoformat()
    if not client or not secret:
        result['providers']['spotify']={'state':'not_configured','reason':'ISEGYE_SPOTIFY_CLIENT_ID and ISEGYE_SPOTIFY_CLIENT_SECRET required'}
        return result
    try:
        token=request('https://accounts.spotify.com/api/token',{'Authorization':'Basic '+base64.b64encode((client+':'+secret).encode()).decode(),'Content-Type':'application/x-www-form-urlencoded'},b'grant_type=client_credentials')['access_token']
    except Exception as exc:
        result['providers']['spotify']={'state':'error','checkedAt':stamp,'error':type(exc).__name__};return result
    matched=0;errors=0
    for song in songs:
        artist='group' if len(song.get('members',[]))==6 else 'gosegu' if song.get('members')==['gosegu'] else None
        if not artist or song.get('dateKind')=='영상 공개일':continue
        item=result['tracks'][song['id']]
        try:
            query={'q':'track:'+song['title']+' artist:'+('ISEGYE IDOL' if artist=='group' else 'GOSEGU'),'type':'track','market':'KR','limit':10}
            rows=request('https://api.spotify.com/v1/search?'+urlencode(query),{'Authorization':'Bearer '+token})['tracks']['items']
            titles={norm(t) for t in [song['title'],*song.get('aliases',[])]}
            candidates={r['id']:r for r in rows if norm(r.get('name','')) in titles and any(norm(a.get('name','')) in ARTISTS[artist] for a in r.get('artists',[]))}
            exact={k:r for k,r in candidates.items() if norm(r.get('album',{}).get('name',''))==norm(song.get('album',''))};candidates=exact or candidates
            if len(candidates)==1:
                row=next(iter(candidates.values()));url=row.get('external_urls',{}).get('spotify','')
                if urlparse(url).scheme!='https' or urlparse(url).hostname!='open.spotify.com':raise ValueError('Invalid Spotify track URL')
                item['spotify']={'state':'ok','trackId':row['id'],'title':row['name'],'url':url,'checkedAt':stamp,'sourceType':'official_api'};matched+=1
            else:item['spotify']={'state':'unmatched','checkedAt':stamp}
        except Exception as exc:item['spotify']={'state':'error','error':type(exc).__name__};errors+=1
        time.sleep(.2)
    result['providers']['spotify']={'state':'partial' if errors and matched else 'error' if errors else 'ok','matched':matched,'checkedAt':stamp,'sourceType':'official_api'}
    return result
