"""Daily additions from existing official artist uploaders; fixed public metadata only."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib import request, parse, error
import hashlib, io, json, re, time, unicodedata
import xml.etree.ElementTree as ET
from music_video_sources import selections
from enhance_catalog import load_music
from refresh_catalog_videos import NS, NoRedirect
ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9)); VID=re.compile(r'[A-Za-z0-9_-]{11}'); CID=re.compile(r'UC[A-Za-z0-9_-]{22}')
# Fixed account IDs, paired with the already reviewed channel handle for independent oEmbed verification.
CHANNELS={'c1':('UCzh4yY8rl38knH33XpNqXbQ',None),'c2':('UCmblbE_WxTaFWcMEGFJ_97w',None),'c4':('UCEx_jGvD7ejBxeTsLvc62yQ','gosegu'),'c12':('UCV9WL7sW6_KjanYkUUaIDfQ','gosegu'),'c13':('UCHE7GBQVtdh-c1m3tjFdevQ','jingburger'),'c14':('UC-oCJP9t47v7-DmsnmXV38Q','lilpa'),'c15':('UCs6EwgxKLY9GG4QNUrP5hoQ','viichan'),'c17':('UCroM00J2ahCN6k-0-oAiDxg','ine'),'c27':('UCTifMx1ONpElK5x6B4ng8eg','jururu')}
NAMES={'ine':'아이네','jingburger':'징버거','lilpa':'릴파','jururu':'주르르','gosegu':'고세구','viichan':'비챤'}
GROUP=re.compile(r'이세계\s*아이돌|이세돌|\bISEGYE\s*IDOL\b',re.I)
BLOCK=re.compile(r'티저|예고|트레일러|비하인드|리액션|챌린지|연습|안무|다시보기|노래방|메들리|하이라이트|쇼츠|모음|플레이리스트|직캠|실황|패러디|불러보게|만들기|제작기|dance\s*(?:practice|challenge)|shorts?|teaser|trailer|behind|reaction|highlight|challenge|making|playlist|medley|karaoke|fancam|\bAI\b|sped\s*up|slowed|instrumental|cover\s*dance|dance\s*cover|댄스\s*커버|춤\s*커버|cover\s*art|unboxing|live\s*(?:clip|performance)|리믹스|remix',re.I)
MARK=re.compile(r'(official\s*(?:music\s*video|performance\s*(?:m/?v|video)|m/?v|audio)|original\s*song|오리지널\s*곡|자작곡|리메이크|\bremake\b|\bcover(?:ed)?\b|커버(?:곡)?)',re.I)
QUOTE=re.compile(r"[‘'“\"「『]([^’'”\"」』]{1,130})[’'”\"」』]")
FIELDS={'videoId','channelKey','title','members','type','kind','publishedAt','checkedAt'}

def clock(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None: raise ValueError('timezone required')
    return d

def norm(s): return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
def keys(title,members):
    # Source titles may carry a translated title in brackets; reserve both aliases for this performer set.
    pieces=[title,re.sub(r'\([^()]*\)',' ',title)]+re.findall(r'\(([^()]*)\)',title)
    return {(norm(t),tuple(sorted(members))) for t in pieces if norm(t)}

def baseline():
    m=load_music(); vids={v for r in m['songs'] for v in (r.get('videoId'),r.get('originalVideoId')) if v}
    titles=set().union(*(keys(r['title'],r['members']) for r in m['songs']))
    return vids,titles

def clean_text(s): return ' '.join(unicodedata.normalize('NFKC',s).split())
def performers(credits):
    return [m for m,k in NAMES.items() if k in credits or re.search(r'(?<![a-z])'+m+r'(?![a-z])',credits,re.I)]

def classify(k,title):
    title=clean_text(title)
    if BLOCK.search(title) or re.search(r'[<>\x00-\x1f]',title) or '#' in title: return None
    marks=MARK.findall(title)
    if not marks: return None
    tags=' '.join(marks).casefold(); quote=QUOTE.search(title)
    work=MARK.sub(' ',title); work=re.sub(r'\[\s*\]|\(\s*\)',' ',work).strip(' |:-[]')
    if quote:
        name=quote[1];credits=title[:quote.start()]+' '+title[quote.end():]
    else:
        # Explicit performer prefix/suffix or 'song | cover by artist'. Do not silently use a third-party artist as performer.
        by=re.search(r'(?i)\s*(?:[|｜]\s*)?(?:cover(?:ed)?\s+by|sung\s+by)\s+(.+)$',title)
        if by: name=MARK.sub(' ',title[:by.start()]).strip(' |:-[]()');credits=by[1]
        else:
            parts=re.split(r'\s+[–—-]\s+|\s*[|｜]\s*',work)
            if len(parts)==2 and (performers(parts[0]) or GROUP.search(parts[0])):credits,name=parts
            elif len(parts)==2 and (performers(parts[1]) or GROUP.search(parts[1])):name,credits=parts
            elif len(parts)==1 and CHANNELS[k][1] and ('cover' in tags or '커버' in tags):name,credits=work,''
            else:return None
    name=clean_text(name).strip(' |:-[]'); mids=performers(credits);owner=CHANNELS[k][1]
    if not name or not norm(name) or len(name)>140:return None
    if not mids:
        if GROUP.search(credits):mids=list(NAMES)
        elif owner:mids=[owner]
        else:return None
    if owner and owner not in mids:return None
    if k=='c1' and not (GROUP.search(credits) or performers(credits)):return None
    if re.search(r'feat\.?|featuring|\bwith\b|피처링',credits,re.I):return None
    kind='official_mv' if re.search(r'm/?v|music\s*video',tags) else 'official_audio' if 'audio' in tags else 'official_video'
    typ='cover' if re.search('cover|커버',tags) else 'remake' if re.search('remake|리메이크',tags) else 'original' if re.search('original|오리지널|자작곡',tags) else 'official_track'
    return {'title':name,'members':mids,'type':typ,'kind':kind}

def read(url,limit):
    for attempt in range(3):
        try:
            req=request.Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; IsegyeFanArchive/1.0)','Accept-Language':'ko-KR,ko;q=0.9'})
            with request.build_opener(NoRedirect).open(req,timeout=15) as res: b=res.read(limit+1)
            if len(b)>limit:raise ValueError('response limit')
            return b
        except (OSError,error.URLError):
            if attempt==2:raise
            time.sleep(1+attempt)

def feed_entries(raw,cid,now):
    if len(raw)>1048576 or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('unsafe XML')
    root=ET.fromstring(raw)
    if root.tag!='{'+NS['a']+'}feed' or root.findtext('yt:channelId',namespaces=NS) not in (cid,cid[2:]):raise ValueError('feed identity')
    ans=[]
    for e in root.findall('a:entry',NS):
        v=e.findtext('yt:videoId',namespaces=NS); title=e.findtext('a:title',namespaces=NS); dt=clock(e.findtext('a:published',namespaces=NS));
        if not VID.fullmatch(v or '') or e.findtext('yt:channelId',namespaces=NS)!=cid or not title:raise ValueError('entry identity')
        if now-timedelta(days=30)<=dt<=now:ans.append((v,title,dt.astimezone(timezone.utc).isoformat()))
    return ans

def verify_video(vid,expected,title):
    from PIL import Image
    url='https://www.youtube.com/watch?v='+vid
    d=json.loads(read('https://www.youtube.com/oembed?'+parse.urlencode({'url':url,'format':'json'}),128000))
    if parse.unquote(d.get('author_url','')).casefold().rstrip('/')!=parse.unquote(expected).casefold().rstrip('/') or clean_text(d.get('title',''))!=clean_text(title):raise ValueError('oembed identity/title mismatch')
    with Image.open(io.BytesIO(read('https://i.ytimg.com/vi/'+vid+'/hqdefault.jpg',1500000))) as im:
        if im.format!='JPEG' or im.width<320 or im.height<180:raise ValueError('thumbnail unavailable')
        im.verify()

def validate(rows):
    ids=set();names=set()
    if not isinstance(rows,list) or len(rows)>2000:raise ValueError('invalid list')
    for r in rows:
        if set(r)!=FIELDS or not VID.fullmatch(r['videoId']) or r['channelKey'] not in CHANNELS or r['type'] not in ('cover','remake','original','official_track') or r['kind'] not in ('official_mv','official_audio','official_video'):raise ValueError('invalid record')
        if not isinstance(r['title'],str) or not 0<len(r['title'])<=140 or re.search(r'[<>\x00-\x1f]',r['title']) or not norm(r['title']):raise ValueError('invalid title')
        if not isinstance(r['members'],list) or not r['members'] or not set(r['members'])<=NAMES.keys() or len(set(r['members']))!=len(r['members']):raise ValueError('invalid credits')
        if clock(r['publishedAt'])>clock(r['checkedAt']):raise ValueError('future release')
        aliases=keys(r['title'],r['members']);v=r['videoId']
        if v in ids or aliases & names:raise ValueError('duplicate music')
        ids.add(v);names.update(aliases)
    return rows

def merge(old,new,base=None):
    vids,titles=base if base is not None else baseline(); vids=set(vids);titles=set(titles);rows=[]
    rank={'official_mv':0,'official_audio':1,'official_video':2}
    for r in [*validate(old),*sorted(new,key=lambda r:(rank[r['kind']],r['videoId']))]:
        validate([r]);aliases=keys(r['title'],r['members']);v=r['videoId']
        if v in vids or titles & aliases:continue
        vids.add(v);titles.update(aliases);rows.append(r)
    return validate(rows)

def discover(now=None):
    now=now or datetime.now(timezone.utc); channels=selections()[0]['channels'];ids,names=baseline()
    def run(k):
        cid,_=CHANNELS[k]; report={'state':'ok','recent':0,'candidates':0,'review':[],'verificationErrors':0};rows=[]
        try:
            if channels[k]['role']!='official' or not CID.fullmatch(cid):raise ValueError('invalid source')
            try:
                entries=feed_entries(read('https://www.youtube.com/feeds/videos.xml?channel_id='+cid,1048576),cid,now);report['transport']='atom'
            except (OSError,ValueError,ET.ParseError):
                from daily_music_listing import public_rows
                entries=public_rows(cid,k,now,report,ids)
            report['recent']=len(entries)
            for v,t,p in entries:
                if v in ids:continue
                parsed=classify(k,t)
                if not parsed:
                    if MARK.search(t) and not BLOCK.search(t):report['review'].append(v)
                    continue
                if keys(parsed['title'],parsed['members']) & names:continue
                report['candidates']+=1
                try:verify_video(v,channels[k]['url'],t)
                except Exception:report['verificationErrors']+=1;report['review'].append(v);continue
                rows.append(dict(parsed,videoId=v,channelKey=k,publishedAt=p,checkedAt=now.isoformat()))
            if report['verificationErrors']:report['state']='partial'
        except Exception as ex:report.update(state='error',reason=type(ex).__name__)
        return k,rows,report
    with ThreadPoolExecutor(max_workers=3) as ex: results=list(ex.map(run,CHANNELS))
    return {'schemaVersion':1,'generatedAt':now.isoformat(),'sources':{k:s for k,_,s in results},'rows':merge([], [r for _,rs,_ in results for r in rs])}

if __name__=='__main__':
    data=discover();Path('music-discovery.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:{a:b for a,b in s.items() if a!='review'} for k,s in data['sources'].items()}));print('verified candidates',len(data['rows']))
    if not any(s['state']!='error' for s in data['sources'].values()):raise SystemExit('No source could be checked; keeping previous publication')
