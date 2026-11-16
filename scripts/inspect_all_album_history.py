"""One-time user-directed public review; never used by production schedules.
No deployment credentials, cookies, private endpoints, retries or bot impersonation.
Null trend cells remain unknown. Only complete dated charts prove chart-out.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError
from io import BytesIO
import hashlib, json, os, re, time, zipfile
from bs4 import BeautifulSoup
from album_releases import load_catalog
from album_observation_archive import request, API

BASE='https://xn--o39an51b2re.com'
KST=timezone(timedelta(hours=9))
CUTOFF=datetime(2026,11,16,10,tzinfo=KST)
OUT=Path('all-albums-evidence');OUT.mkdir(exist_ok=True)
KINDS={'melon_top100':('top100','MELON_TOP100_CHART'),'melon_hot100':('hot100-d100','MELON_HOT100_D100_CHART')}
NEW={'love-cells':'603813507','rebels':'603813508','back-2-the-future':'603813509','anti-hero':'603813510','dream-residue':'603813511'}
requests=0
class StopReview(RuntimeError): pass
class Redirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if urlparse(newurl).netloc!=urlparse(BASE).netloc or urlparse(newurl).scheme!='https':raise ValueError('Off-site redirect refused')
        return super().redirect_request(req,fp,code,msg,headers,newurl)
def fetch(url):
    global requests
    if not url.startswith(BASE+'/') or requests>=650:raise StopReview('Fixed public request budget')
    requests+=1
    try:
        with build_opener(Redirect).open(Request(url,headers={'User-Agent':'ISEGYE-Archive-Review/1.2 (one-time historical verification)','Accept':'text/html,application/json'}),timeout=20) as response:
            raw=response.read(4000001);final=response.url
        if len(raw)>4000000:raise ValueError('Oversized source')
        if final!=url:raise ValueError('Source route changed')
        return raw
    except HTTPError as exc:
        if exc.code in (401,403,429):raise StopReview('Access/rate restriction; no workaround') from None
        raise
    finally:time.sleep(1)
def props(raw):
    node=BeautifulSoup(raw,'html.parser').select_one('script#__NEXT_DATA__')
    if not node:raise ValueError('Missing rendered page data')
    return json.loads(node.string)['props']['pageProps']
def localclock(value):
    stamp=datetime.fromisoformat(value)
    if stamp.tzinfo is not None:raise ValueError('Expected documented local source clock')
    if stamp.minute or stamp.second or stamp.microsecond:raise ValueError('Non-hourly source clock')
    return stamp.replace(tzinfo=KST)
def norm(value):return re.sub(r'[^\w]','',str(value).casefold()).replace('_','')
def identity(song,expected,ident,album):
    artists={norm(v['name']) for v in song.get('artists',[])}
    wanted={'고세구','gosegu','고세구gosegu'} if expected['members']==['gosegu'] else {'이세계아이돌','이세계아이돌isegyeidol','isegyeidol'}
    if (str(song.get('id'))!=ident or str(song.get('album',{}).get('id'))!=album or song.get('platform')!='melon'
        or norm(song.get('name')) not in {norm(expected['title']),*map(norm,expected.get('aliases',[]))} or not artists.intersection(wanted)):
        raise ValueError('Song/album/title/artist identity mismatch')
    released=localclock(song['releasedAt'])
    if released.date().isoformat()!=expected['date']:raise ValueError('Release date mismatch')
    return released

def archive(ident,digest,token):
    raw=request(API+'/actions/artifacts/'+str(ident)+'/zip',token,binary=True)
    if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Evidence archive digest mismatch')
    return zipfile.ZipFile(BytesIO(raw))
def hour(stamp):return int(stamp.timestamp()//3600)
def save(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n')

def main():
    token=os.environ.pop('GH_TOKEN','')
    identities=archive(14191289345,'651755db9500470b312474223cb6e5b515818dfee534fc9f570185b33c7da87f',token)
    dated=archive(14188916741,'0670d300c8115aa4148b48bf677b5ccfa2d86b62ab3e61b5c5bca1ddfd17076e',token)
    token=None
    catalog=load_catalog()['songs']; seed=json.loads(Path('albums/release-seed/snapshot.json').read_text())
    result={'schemaVersion':1,'cutoffAt':CUTOFF.isoformat(),'sourceType':'guyso_public_historical','tracks':{},'excluded':[], 'searches':{},'errors':[], 'fullCharts':[]}
    evidence={r.get('file'):r for r in json.loads(identities.read('report.json')) if r.get('file')}
    try:
        for s in catalog:
            sid=s['id'];ident=NEW.get(sid) or seed['tracks'].get(sid,{}).get('melon',{}).get('trackId')
            search_rows=[];search_evidence=[]
            queries=[s['title']]
            # First the actual title. A bounded artist-qualified query may disambiguate common names.
            if ident:queries.append(s['title']+' '+('고세구' if s['members']==['gosegu'] else '이세계아이돌'))
            for query in queries:
                url=BASE+'/api/v3/song/search?'+urlencode({'platform':'melon','query':query,'page':0})
                try:
                    raw=fetch(url);rows=json.loads(raw)
                    if not isinstance(rows,list) or len(rows)>1000:raise ValueError('Search schema changed')
                    matches=[r for r in rows if str(r.get('id'))==ident] if ident else []
                    search_evidence.append({'url':url,'query':query,'responseSha256':hashlib.sha256(raw).hexdigest(),'resultCount':len(rows),'exactIdFound':bool(matches)})
                    search_rows+=matches
                    if matches or not ident:break
                except StopReview:raise
                except Exception as exc:search_evidence.append({'url':url,'error':type(exc).__name__})
            result['searches'][sid]=search_evidence
            if not ident:
                result['excluded'].append({'sid':sid,'title':s['title'],'album':s['album'],'reason':'registered_video_only_no_melon_identity'});continue
            album='15120216' if sid in NEW else seed['tracks'][sid]['melon']['albumId']
            try:
                raw=identities.read(sid+'.html');page=props(raw);released=identity(page['song'],s,ident,album)
                if hashlib.sha256(raw).hexdigest()!=evidence[sid+'.html']['sha256']:raise ValueError('Song evidence mismatch')
                item={'trackId':ident,'albumId':album,'title':s['title'],'album':s['album'],'releaseAt':released.isoformat(),
                      'identitySource':BASE+'/song/melon/'+ident,'identitySha256':hashlib.sha256(raw).hexdigest(),'charts':{}}
                result['tracks'][sid]=item
                for kind,(slug,chartid) in KINDS.items():
                    # HOT100 covers the first 100 days; inspect one extra boundary day conservatively.
                    end=min(CUTOFF,released+timedelta(days=101)) if kind=='melon_hot100' else CUTOFF
                    root=BASE+'/chart/melon/'+slug+'/trend/ranking/'+ident
                    chart={'source':root,'scannedFrom':released.isoformat(),'scannedThrough':end.isoformat(),'points':[], 'pages':[]}
                    item['charts'][kind]=chart;until=min(released.date()+timedelta(days=30),end.date());seen={}
                    while True:
                        url=root+'?end='+until.isoformat()
                        try:
                            raw=fetch(url);p=props(raw);identity(p['song'],s,ident,album);data=p['data']
                            if data.get('chart')!=chartid or str(data.get('songId'))!=ident or data.get('timeUnit')!='HOURS':raise ValueError('Chart identity mismatch')
                            rows=data.get('data');
                            if not isinstance(rows,list) or len(rows)>744 or data.get('size')!=len(rows):raise ValueError('Trend coverage size mismatch')
                            pageinfo={'url':url,'responseSha256':hashlib.sha256(raw).hexdigest(),'endDate':until.isoformat(),'rows':len(rows),'ranked':0,'nullCells':0}
                            times=[];accepted=[]
                            for row in rows:
                                at=localclock(row['time']);times.append(at)
                                if not until-timedelta(days=30)<=at.date()<=until:raise ValueError('Requested historical period ignored')
                                if not released<=at<=end:continue
                                rank=row.get('ranking')
                                if rank is None:pageinfo['nullCells']+=1;continue
                                if type(rank)!=int or not 1<=rank<=100:raise ValueError('Invalid chart rank')
                                key=hour(at)
                                if key in seen and seen[key]!=rank:raise ValueError('Conflicting historical pages')
                                accepted.append([key,rank]);pageinfo['ranked']+=1
                            if len(times)!=len(set(times)):raise ValueError('Duplicate source hours')
                            if times and max(t.date() for t in times)!=until:raise ValueError('Requested period incomplete or ignored')
                            for key,rank in accepted:seen[key]=rank
                            chart['pages'].append(pageinfo)
                        except StopReview:raise
                        except Exception as exc:
                            chart['pages'].append({'url':url,'endDate':until.isoformat(),'error':type(exc).__name__})
                        if until==end.date():break
                        until=min(until+timedelta(days=31),end.date())
                    chart['points']=[[t,r] for t,r in sorted(seen.items())]
                    print(sid,kind,'pages',len(chart['pages']),'ranked',len(chart['points']),flush=True)
                    save('review.json',result)
            except StopReview:raise
            except Exception as exc:result['errors'].append({'sid':sid,'error':type(exc).__name__})
        # Previously verified complete source pages can be reused for all matching songs.
        full=[]
        for info in json.loads(dated.read('index.json')):
            if info.get('file') and info.get('sha256'):
                raw=dated.read(info['file'])
                if hashlib.sha256(raw).hexdigest()!=info['sha256']:raise ValueError('Dated evidence changed')
                full.append((info['url'],raw))
        wanted=set()
        for item in result['tracks'].values():
            at=datetime.fromisoformat(item['releaseAt'])
            for kind,(slug,_) in KINDS.items():wanted.add(BASE+'/chart/melon/'+slug+'/'+at.strftime('%Y%m%d')+'/'+str(at.hour))
        for i in range(48):
            at=CUTOFF-timedelta(hours=i)
            for kind,(slug,_) in KINDS.items():
                if kind=='melon_hot100' and 2<=at.hour<=6:continue
                wanted.add(BASE+'/chart/melon/'+slug+'/'+at.strftime('%Y%m%d')+'/'+str(at.hour))
        known={u for u,r in full}
        for url in sorted(wanted-known):
            try:full.append((url,fetch(url)))
            except StopReview:raise
            except Exception as exc:result['errors'].append({'url':url,'error':type(exc).__name__})
        for url,raw in full:
            try:
                m=re.fullmatch(re.escape(BASE)+r'/chart/melon/(top100|hot100-d100)/(\d{8})/(\d{1,2})',url)
                if not m:raise ValueError('Unknown dated route')
                slug,day,hh=m.groups();at=datetime.strptime(day+hh.zfill(2),'%Y%m%d%H').replace(tzinfo=KST)
                kind=next(k for k,v in KINDS.items() if v[0]==slug);d=props(raw)['data'];rows=d['data']
                if d.get('chart')!=KINDS[kind][1] or localclock(d['time'])!=at or d.get('size')!=100 or len(rows)!=100:raise ValueError('Incomplete or wrong-clock chart')
                ids={str(r['song']['id']) for r in rows};ranks={r['ranking'] for r in rows}
                if len(ids)!=100 or ranks!=set(range(1,101)):raise ValueError('Incomplete or duplicate chart')
                idx={str(r['song']['id']):r['ranking'] for r in rows};matched={}
                for sid,item in result['tracks'].items():
                    release=datetime.fromisoformat(item['releaseAt'])
                    end=datetime.fromisoformat(item['charts'][kind]['scannedThrough'])
                    if release<=at<=end:matched[sid]=idx.get(item['trackId'])
                result['fullCharts'].append({'url':url,'responseSha256':hashlib.sha256(raw).hexdigest(),'chart':kind,'hour':hour(at),'verifiedFullChartSize':100,'observations':matched})
            except Exception as exc:result['errors'].append({'url':url,'error':type(exc).__name__,'state':'unverified_complete_chart'})
    except StopReview as exc:result['stopped']=str(exc)
    finally:
        result['publicRequests']=requests;result['checkedAt']=datetime.now(timezone.utc).isoformat();save('review.json',result)
        print('DONE',requests,'requests',len(result['tracks']),'songs',len(result['errors']),'reported exceptions',flush=True)
if __name__=='__main__':main()
