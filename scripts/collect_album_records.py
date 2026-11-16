#!/usr/bin/env python3
"""Bounded, read-only record enrichment for the album review.
Official Melon album awards and original daily-chart achievements. Never copy lyrics, reference-site UI, or inferred peaks.
"""
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import hashlib, io, json, re, time
from collect_album_domestic import norm, text
from collect_album_melon_record import collect_original_records
ROOT=Path(__file__).resolve().parents[1]
HALL='https://m2.melon.com/melonhall/sector/album/millions.htm'
SPRITE='https://cdnimg.melon.co.kr/services/img/mhall/ico-mhall-240116@3x.png'
HOSTS={'m2.melon.com','cdnimg.melon.co.kr'}

def allowed(url):
    u=urlparse(url)
    from collect_album_peak_fallback import allowed_source
    if url == 'https://isegyechart.com/api/song-selector-list': return url
    if allowed_source(url): return url
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
    report['peaks']=collect_original_records(result,previous,fetch)
    from collect_album_peak_fallback import collect_reference_peaks
    report['fallbackPeaks']=collect_reference_peaks(result,previous,fetch)
    # Removed providers never survive restoration of the older feature cache.
    for name in ('flo','spotify'):result['providers'].pop(name,None);result['assets'].get('brands',{}).pop(name,None)
    for item in result['tracks'].values():
        item.pop('flo',None);item.pop('spotify',None)
    path=ROOT/'test-results/albums-records';path.mkdir(parents=True,exist_ok=True);(path/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return result
