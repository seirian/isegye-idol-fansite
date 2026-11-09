#!/usr/bin/env python3
"""Bounded, read-only record enrichment for the album review.
Official Melon album awards and separately attributed third-party historical
chart observations. Never copy lyrics, reference-site UI, or inferred peaks.
"""
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import hashlib, io, json, re, time
from collect_album_domestic import norm, text
ROOT=Path(__file__).resolve().parents[1]
HALL='https://m2.melon.com/melonhall/sector/album/millions.htm'
SPRITE='https://cdnimg.melon.co.kr/services/img/mhall/ico-mhall-240116@3x.png'
HOSTS={'m2.melon.com','cdnimg.melon.co.kr','isegyechart.com'}

def allowed(url):
    u=urlparse(url)
    if u.scheme!='https' or u.hostname not in HOSTS or u.port not in (None,443) or u.username or u.password: raise ValueError('Unapproved record URL')
    return url
class Redirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        allowed(newurl)
        if urlparse(newurl).hostname!=urlparse(req.full_url).hostname:raise ValueError('Cross-origin record redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch(url):
    allowed(url)
    with build_opener(Redirect).open(Request(url,headers={'User-Agent':'ISEGYE-Archive-Review/1.2'}),timeout=20) as response:
        raw=response.read(4*1024*1024+1)
        if len(raw)>4*1024*1024:raise ValueError('Oversized record')
    time.sleep(.3)
    return raw

def clean_label(node):
    if not node:return ''
    clone=BeautifulSoup(str(node),'html.parser')
    for el in clone.select('.screen-out'):el.decompose()
    return text(clone)

def parse_hall(html, expected):
    """Require actual membership, exact album/artist and official badge markup."""
    soup=BeautifulSoup(html,'html.parser'); result={}
    issue_dates=dict(re.findall(r"goLink\('album_detail(?:_click)?',\s*'(\d+)',\s*'(\d{12})'",html))
    for card in soup.select('.mhall-album'):
        ids=set(re.findall(r"goAlbumDetail\('(\d+)'",str(card)))
        if len(ids)!=1:continue
        ident=ids.pop()
        if ident not in expected:continue
        title=clean_label(card.select_one('.txt-title'));artist=clean_label(card.select_one('.txt-description'))
        match=expected[ident]
        if norm(title)!=norm(match['album']) or norm(artist)!=norm(match['artist']):raise ValueError('Hall album identity mismatch')
        label=text(card.select_one('.txt-badge'));icon=card.select_one('[class*=ico-badge-]')
        if not re.fullmatch(r'[1-9]\d?M',label) or not icon or ident not in issue_dates:raise ValueError('Hall badge/issue-time missing')
        classes=icon.get('class',[]);tiers=[int(m.group(1)) for c in classes if (m:=re.fullmatch(r'ico-badge-(1|3|5|10)m-big',c))]
        if len(tiers)!=1:raise ValueError('Unexpected official badge class')
        amount=int(label[:-1]);tier=tiers[0]
        if tier!=max(v for v in (1,3,5,10) if v<=amount):raise ValueError('Badge tier mismatch')
        row={'albumId':ident,'album':title,'artist':artist,'label':label,'spriteTier':tier,'scope':'album_first_24h','source':f'https://m2.melon.com/melonhall/sector/album/report.htm?albumId={ident}&issueDate={issue_dates[ident]}','membershipSource':HALL,'state':'verified'}
        if ident in result and result[ident]!=row:raise ValueError('Conflicting official award')
        result[ident]=row
    if not soup.select('.mhall-album'):raise ValueError('Missing Hall catalog')
    return result

def badge_asset(raw,tier):
    """Lossless crop at the official CSS sprite coordinates; no redrawing."""
    from PIL import Image
    offsets={1:0,3:70,5:140,10:210}
    if tier not in offsets:raise ValueError('Unknown sprite tier')
    with Image.open(io.BytesIO(raw)) as image:
        if image.size!=(900,1200):raise ValueError('Official sprite geometry changed')
        x=offsets[tier]*3;y=90*3
        crop=image.convert('RGBA').crop((x,y,x+180,y+180));buf=io.BytesIO();crop.save(buf,format='WEBP',lossless=True)
    data=buf.getvalue();sha=hashlib.sha256(data).hexdigest();path=ROOT/'albums/asset-cache'/f'{sha}.webp';path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    return sha,{'path':str(path.relative_to(ROOT)),'sha256':sha,'source':SPRITE,'spriteSha256':hashlib.sha256(raw).hexdigest(),'crop':[x,y,180,180],'officialCssClass':f'ico-badge-{tier}m-big'}

def unastro(value):
    if isinstance(value,list) and len(value)==2 and type(value[0]) is int:return unastro(value[1])
    if isinstance(value,list):return [unastro(v) for v in value]
    if isinstance(value,dict):return {k:unastro(v) for k,v in value.items() if k!='lyrics'}
    return value

def parse_peaks(html, melon, source_id):
    soup=BeautifulSoup(html,'html.parser');info=None
    for island in soup.select('astro-island[props]'):
        if 'FeaturedSongSelector' in island.get('component-url',''):
            info=unastro(json.loads(island['props'])).get('songInfo');break
    if not isinstance(info,dict) or str(info.get('id'))!=str(source_id):raise ValueError('Record page identity missing')
    if str(info.get('idMap',{}).get('melonId'))!=melon['trackId'] or str(info.get('albumIdMap',{}).get('melonId'))!=melon['albumId']:raise ValueError('Wrong Melon song or album ID')
    if norm(info.get('name'))!=norm(melon['title']):raise ValueError('Record title mismatch')
    # ID equality is mandatory; normalized artist supports official English suffix.
    artist=norm(info.get('artistName'));expected=norm(melon['artist'])
    if artist!=expected and not ({artist,expected}<={'이세계아이돌','이세계아이돌isegyeidol'}):raise ValueError('Record artist mismatch')
    labels={'TOP100':'top100','HOT100 (100일)':'hot100','실시간차트':'realtime'};ranks={k:None for k in labels.values()};dates={};seen=set()
    if '멜론 최고 성적' not in soup.get_text(' ',strip=True):raise ValueError('Missing peak section')
    for heading in soup.select('h3'):
        label=text(heading)
        if label not in labels:continue
        key=labels[label]
        if key in seen:raise ValueError('Duplicate peak label')
        seen.add(key);cell=heading.parent
        content=text(cell);values=re.findall(r'(?<!\d)(\d+)위',content)
        if len(values)>1:raise ValueError('Ambiguous peak value')
        if values:
            rank=int(values[0])
            if not 1<=rank<=100:raise ValueError('Invalid peak rank')
            ranks[key]=rank
        date=re.search(r'(?<!\d)(\d{2})\.(\d{1,2})\.(\d{1,2})(?!\d)',content)
        if date:
            y,m,d=map(int,date.groups());dates[key]=datetime(2000+y,m,d,tzinfo=timezone.utc).date().isoformat()
    if not seen:raise ValueError('No peak headings')
    return {'state':'verified','trackId':melon['trackId'],'albumId':melon['albumId'],'ranks':ranks,'dates':dates,'source':f'https://isegyechart.com/song/{source_id}','sourceType':'third_party_observed_records','hot100WindowDays':100,'coverage':'provider-observed historical peak; not certified all-time by Melon'}

def collect(result,previous):
    stamp=datetime.now(timezone.utc).isoformat();expected={t['melon']['albumId']:t['melon'] for t in result['tracks'].values() if t.get('melon',{}).get('state')=='ok'}
    report={'checkedAt':stamp,'awards':{},'peaks':{}};result.setdefault('assets',{})['badges']={}
    try:
        raw=fetch(HALL);awards=parse_hall(raw.decode('utf-8'),expected);sprite=fetch(SPRITE) if awards else b'';by_tier={}
        for tier in {v['spriteTier'] for v in awards.values()}:
            sha,asset=badge_asset(sprite,tier);result['assets']['badges'][sha]=asset;by_tier[tier]=sha
        for item in result['tracks'].values():
            award=awards.get(item.get('melon',{}).get('albumId'))
            if award:item['melonHonor']={**award,'asset':by_tier[award['spriteTier']],'checkedAt':stamp}
        report['awards']={'state':'ok','albums':len(awards),'source':HALL,'responseSha256':hashlib.sha256(raw).hexdigest()}
    except Exception as exc: report['awards']={'state':'error','error':type(exc).__name__}
    mappings=json.loads((ROOT/'albums/record-sources.json').read_text())['tracks']
    for sid,entry in mappings.items():
        item=result['tracks'].get(sid,{});m=item.get('melon',{})
        if not m.get('trackId') or m['trackId']!=entry['melonId']:continue
        url=f"https://isegyechart.com/song/{entry['recordId']}"
        try:
            raw=fetch(url);peaks=parse_peaks(raw.decode('utf-8'),m,entry['recordId']);item['melonPeaks']={**peaks,'checkedAt':stamp,'responseSha256':hashlib.sha256(raw).hexdigest()}
            report['peaks'][sid]={'state':'verified','ranks':peaks['ranks'],'source':url}
        except Exception as exc:report['peaks'][sid]={'state':'error','error':type(exc).__name__}
    # Removed providers never survive restoration of the older feature cache.
    for name in ('flo','spotify'):result['providers'].pop(name,None);result['assets'].get('brands',{}).pop(name,None)
    for item in result['tracks'].values():
        item.pop('flo',None);item.pop('spotify',None)
    path=ROOT/'test-results/albums-records';path.mkdir(parents=True,exist_ok=True);(path/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return result
