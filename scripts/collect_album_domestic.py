#!/usr/bin/env python3
"""Read-only domestic public catalog/chart adapters. Not a licensed partner API.
No login, cookies, bypass, lyrics, listening or download actions. Fail closed on
identity/schema/clock/rank coverage errors; persist only verifiable observations.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlparse, urlencode, urljoin
from bs4 import BeautifulSoup
import hashlib, io, json, re, time

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))
HOSTS = {'www.melon.com','www.genie.co.kr','music.bugs.co.kr','cdnimg.melon.co.kr',
 'image.genie.co.kr','image.bugsm.co.kr','file.bugsm.co.kr','www.music-flo.com',
 'open.spotifycdn.com','music.apple.com','www.youtube.com','music.youtube.com'}
ARTISTS = {'group': {'이세계아이돌isegyeidol','이세계아이돌','isegyeidol'}, 'gosegu': {'고세구','gosegu','고세구gosegu'}}
BRANDS = {
 'melon':'https://www.melon.com/favicon.ico?2',
 'genie':'https://www.genie.co.kr/resources/favicon_32.ico?v=202602091400',
 'bugs':'https://file.bugsm.co.kr/wbugs/common/faviconBugs.ico',
 'flo':'https://www.music-flo.com/favicon.ico',
 'spotify':'https://open.spotifycdn.com/cdn/images/favicon32.b64ecc03.png',
 'apple':'https://music.apple.com/assets/favicon/favicon-32.png',
 'youtube':'https://www.youtube.com/s/desktop/4e57be2c/img/favicon_48x48.png',
 'youtube_music':'https://music.youtube.com/img/favicon_48.png'}
ALBUM_URLS = {'melon':'https://www.melon.com/album/detail.htm?albumId=', 'genie':'https://www.genie.co.kr/detail/albumInfo?axnm=', 'bugs':'https://music.bugs.co.kr/album/'}
TRACK_URLS = {'melon':'https://www.melon.com/song/detail.htm?songId=', 'genie':'https://www.genie.co.kr/detail/songInfo?xgnm=', 'bugs':'https://music.bugs.co.kr/track/'}
SEARCH = {'melon':'https://www.melon.com/search/album/index.htm?q=', 'genie':'https://www.genie.co.kr/search/searchAlbum?query=', 'bugs':'https://music.bugs.co.kr/search/album?q='}
CHARTS = {'melon_hot100':('melon','https://www.melon.com/chart/hot100/index.htm?chartType=D100',100),
 'melon_top100':('melon','https://www.melon.com/chart/index.htm',100),
 'bugs':('bugs','https://music.bugs.co.kr/chart',100),
 'genie':('genie','https://www.genie.co.kr/chart/top200?ditc=D&rtm=Y&pg=',200)}

def norm(v):
    import unicodedata
    return re.sub(r'[^\w]','',unicodedata.normalize('NFKC',str(v)).casefold()).replace('_','')
def text(node): return node.get_text(' ',strip=True) if node else ''
def meta(soup,name):
    node=soup.find('meta',attrs={'property':name});return node.get('content','') if node else ''
def valid_url(url):
    u=urlparse(url)
    if u.scheme!='https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None,443):raise ValueError('Unapproved domestic URL')
    return url
class Redirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        valid_url(newurl);return super().redirect_request(req,fp,code,msg,headers,newurl)
CACHE={}
def fetch(url,binary=False):
    valid_url(url)
    if url not in CACHE:
        request=Request(url,headers={'User-Agent':'Mozilla/5.0 (compatible; ISEGYE-Archive-Review/1.1)','Accept':'*/*'})
        with build_opener(Redirect).open(request,timeout=22) as response:
            valid_url(response.url);raw=response.read(4*1024*1024+1)
            if len(raw)>4*1024*1024:raise ValueError('Oversize domestic response')
            charset=response.headers.get_content_charset() or ('cp949' if urlparse(url).hostname=='www.genie.co.kr' else 'utf-8')
            CACHE[url]=(raw,charset)
        time.sleep(.18)
    raw,charset=CACHE[url]
    return raw if binary else raw.decode(charset,errors='replace')

def search_albums(html,provider,artist):
    soup=BeautifulSoup(html,'html.parser');out=[]
    if provider=='melon':
        for row in soup.select('li.album11_li'):
            identity=row.select_one('.atistname a');link=row.select_one('a.thumb')
            match=re.search(r"goAlbumDetail\('(\d+)'\)",str(link))
            if match and norm(text(identity)) in ARTISTS[artist]:out.append(match[1])
    elif provider=='genie':
        for row in soup.select('li.list-album'):
            match=re.search(r"fnViewAlbumLayer\('(\d+)'\)",str(row.select_one('a.album-cover')))
            if match and norm(text(row.select_one('.album-artist'))) in ARTISTS[artist]:out.append(match[1])
    else:
        for row in soup.select('figure.albumInfo[albumid]'):
            if norm(text(row.select_one('.artist a'))) in ARTISTS[artist]:out.append(row['albumid'])
    return list(dict.fromkeys(out))[:25]

def parse_album(html,provider,album_id):
    soup=BeautifulSoup(html,'html.parser');rows=[]
    cover=meta(soup,'og:image:secure_url') or meta(soup,'og:image')
    if cover.startswith('//'):cover='https:'+cover
    if cover.startswith('http://'):cover='https://'+cover[7:]
    valid_url(cover)
    if provider=='melon':
        header=soup.select_one('.song_name')
        if header:
            for n in header.select('strong'):n.decompose()
        album=text(header)
        for row in soup.select('tr[data-group-items]'):
            check=row.select_one('input[name=input_check][value]');link=row.select_one('.wrap_song_info .ellipsis a');artist=row.select_one('.rank02 a')
            if check and link and artist:rows.append({'trackId':check['value'],'title':text(link),'artist':text(artist)})
    elif provider=='genie':
        album=text(soup.select_one('.info-zone h2.name'))
        for row in soup.select('tr[songid]'):
            title=row.select_one('a.title');artist=row.select_one('a.artist')
            if title:
                for n in title.select('span'):n.decompose()
            if title and artist:rows.append({'trackId':row['songid'].strip(),'title':text(title),'artist':text(artist)})
    else:
        album=meta(soup,'og:title').split(' / ')[0]
        for row in soup.select('tr[trackid]'):
            title=row.select_one('.title a');artist=row.select_one('.artist a')
            if title and artist:rows.append({'trackId':row['trackid'],'title':text(title),'artist':text(artist)})
    if not album or not rows or any(not r['trackId'].isdigit() for r in rows):raise ValueError('Album schema/identity missing')
    if len({r['trackId'] for r in rows})!=len(rows):raise ValueError('Duplicate album IDs')
    for row in rows:row.update(album=album,albumId=str(album_id),url=TRACK_URLS[provider]+row['trackId'],albumUrl=ALBUM_URLS[provider]+str(album_id),cover=cover)
    return rows

def match(song,rows):
    if song.get('dateKind')=='영상 공개일':return None
    artist='group' if len(song.get('members',[]))==6 else 'gosegu' if song.get('members')==['gosegu'] else None
    if not artist:return None
    titles={norm(v) for v in [song['title'],*song.get('aliases',[])]}
    candidates={r['trackId']:r for r in rows if norm(r['title']) in titles and norm(r['artist']) in ARTISTS[artist]}
    exact={k:r for k,r in candidates.items() if norm(r['album'])==norm(song.get('album',''))}
    candidates=exact or candidates
    return next(iter(candidates.values())) if len(candidates)==1 else None

def chart_rows(html,provider,now,expected=100):
    s=BeautifulSoup(html,'html.parser');values={}
    if provider=='melon':
        date=text(s.select_one('.calendar_prid .year'));hour=text(s.select_one('.calendar_prid .hour'))
        when=datetime.strptime(date+' '+hour,'%Y.%m.%d %H:%M').replace(tzinfo=KST)
        for row in s.select('tr[data-song-no]'):
            rank=text(row.select_one('span.rank'))
            if rank.isdigit():values[row['data-song-no']]=int(rank)
    elif provider=='genie':
        bits=[s.select_one('#str'+part)['value'] for part in ('YYYY','MM','DD','HH')]
        when=datetime.strptime(''.join(bits),'%Y%m%d%H').replace(tzinfo=KST)
        for row in s.select('tr.list[songid]'):
            cell=row.select_one('td.number');rank=''.join(cell.find_all(string=True,recursive=False)).strip() if cell else ''
            if rank.isdigit():values[row['songid']]=int(rank)
    else:
        node=s.select_one('time[datetime]');hour=text(node.select_one('em')) if node else ''
        date=(node.get('datetime','').split(' ')[0] if node else '')
        when=datetime.strptime(date+' '+hour,'%Y.%m.%d %H:%M').replace(tzinfo=KST)
        for row in s.select('tr[trackid]'):
            rank=text(row.select_one('.ranking strong'))
            if rank.isdigit():values[row['trackid']]=int(rank)
    if not now-timedelta(hours=8)<=when<=now+timedelta(minutes=10):raise ValueError('Stale/future chart')
    if len(values)!=expected or len(set(values.values()))!=expected:raise ValueError('Incomplete chart')
    if any(not k.isdigit() or not 1<=v<=(200 if provider=='genie' else 100) for k,v in values.items()):raise ValueError('Invalid chart rank')
    if provider!='genie' and set(values.values())!=set(range(1,expected+1)):raise ValueError('Missing chart ranks')
    return values,when.astimezone(timezone.utc).isoformat()

def merge(previous,point,now,identity,limit):
    out={}
    for p in list(previous)+[point]:
        try:
            t=datetime.fromisoformat(p['at']);rank=p.get('rank')
            if t.tzinfo is None or not now-timedelta(days=30)<=t<=now+timedelta(minutes=10) or p.get('trackId')!=identity:continue
            if p.get('status')=='ranked':
                if type(rank) is not int or not 1<=rank<=limit:continue
            elif p.get('status') not in ('error','out') or rank is not None:continue
            out[p['at']]={k:p.get(k) for k in ('at','trackId','rank','status')}
        except (ValueError,KeyError,TypeError):continue
    return sorted(out.values(),key=lambda p:p['at'])[-1440:]

def image_asset(url,key,size=400):
    from PIL import Image
    raw=fetch(url,True)
    with Image.open(io.BytesIO(raw)) as img:
        if img.width*img.height>16000000:raise ValueError('Image too large')
        img=img.convert('RGBA');img.thumbnail((size,size));buf=io.BytesIO();img.save(buf,format='WEBP',quality=86)
    data=buf.getvalue();digest=hashlib.sha256(data).hexdigest();directory=ROOT/'albums/asset-cache';directory.mkdir(parents=True,exist_ok=True)
    local=directory/(digest+'.webp');local.write_bytes(data)
    return {'key':key,'path':'albums/asset-cache/'+digest+'.webp','sha256':digest,'source':url}

def collect(result,previous):
    now=datetime.now(timezone.utc);stamp=now.isoformat();songs=json.loads((ROOT/'catalog/music.json').read_text())['songs']
    result['domesticCharts']={};result['assets']={'covers':{},'brands':{}};report={'checkedAt':stamp,'providers':{},'charts':{},'assets':{},'manual':[]}
    allrows={}
    for provider in SEARCH:
        rows=[];errors=[]
        for artist,term in [('group','이세계아이돌'),('gosegu','고세구')]:
            try:
                ids=search_albums(fetch(SEARCH[provider]+urlencode({'q':term})[2:]),provider,artist)
                if not ids:raise ValueError('No exact artist album results')
                for ident in ids:
                    try:rows.extend(parse_album(fetch(ALBUM_URLS[provider]+ident),provider,ident))
                    except Exception as exc:errors.append({'albumId':ident,'error':type(exc).__name__})
            except Exception as exc:errors.append({'artist':artist,'error':type(exc).__name__})
        allrows[provider]=rows;count=0
        for song in songs:
            row=match(song,rows);item=result['tracks'][song['id']]
            if row:
                count+=1;item[provider]={**row,'checkedAt':stamp,'state':'ok','sourceType':'public_catalog','matchBasis':'exact artist and title, album preferred, unique ID'}
                if 'artwork' not in item:
                    try:
                        asset=image_asset(row['cover'],song['id']);result['assets']['covers'][asset['sha256']]=asset
                        item['artwork']={'asset':asset['sha256'],'provider':provider,'source':row['albumUrl'],'imageUrl':row['cover'],'checkedAt':stamp}
                    except Exception as exc:report['assets'][song['id']]=type(exc).__name__
            else:item[provider]={'state':'unmatched' if song.get('dateKind')!='영상 공개일' else 'not_applicable'}
        result['providers'][provider]={'state':'partial' if errors and count else 'error' if not count else 'ok','checkedAt':stamp,'sourceType':'public_catalog','matched':count,'errors':errors}
        report['providers'][provider]=result['providers'][provider]
    # Public JSON endpoint actually used by Melon's album page. Never use HTML's 0 placeholder.
    ids=[t['melon']['trackId'] for t in result['tracks'].values() if t.get('melon',{}).get('trackId')]
    try:
        data=json.loads(fetch('https://www.melon.com/commonlike/getSongLike.json?'+urlencode({'contsIds':','.join(ids)})))
        likes={str(r['CONTSID']):int(r['SUMMCNT']) for r in data['contsLike'] if str(r.get('CONTSID','')).isdigit() and str(r.get('SUMMCNT','')).isdigit()}
        for item in result['tracks'].values():
            ident=item.get('melon',{}).get('trackId')
            if ident in likes:item['melon']['likes']=likes[ident];item['melon']['likesSource']='public_json'
        report['melonLikes']={'state':'ok','matched':len(likes)}
    except Exception as exc:report['melonLikes']={'state':'error','error':type(exc).__name__}
    for kind,(provider,url,limit) in CHARTS.items():
        ranks={};at=stamp;state='error'
        try:
            if provider=='genie':
                pages=[chart_rows(fetch(url+str(i)),provider,now,50) for i in range(1,5)]
                if len({at for _,at in pages})!=1:raise ValueError('Mixed chart times')
                for part,_ in pages:
                    if ranks.keys() & part.keys():raise ValueError('Duplicate chart page')
                    ranks.update(part)
                at=pages[0][1]
            else:ranks,at=chart_rows(fetch(url),provider,now)
            if set(ranks.values())!=set(range(1,limit+1)):raise ValueError('Missing ranks')
            state='ok'
        except Exception as exc:report['charts'][kind]={'error':type(exc).__name__}
        result['domesticCharts'][kind]={'state':state,'checkedAt':stamp,'updatedAt':at,'source':url+'1' if provider=='genie' else url,'limit':limit,'sourceType':'public_chart'}
        report['charts'][kind]={**result['domesticCharts'][kind],**report['charts'].get(kind,{})}
        for sid,item in result['tracks'].items():
            ident=item.get(provider,{}).get('trackId')
            if not ident:continue
            point={'at':at,'trackId':ident,'rank':ranks.get(ident) if state=='ok' else None,'status':('ranked' if ident in ranks else 'out') if state=='ok' else 'error'}
            prior=previous.get('tracks',{}).get(sid,{}).get('charts',{}).get(kind,[])
            item.setdefault('charts',{})[kind]=merge(prior,point,now,ident,limit)
            if kind.startswith('melon_'):item['melon'][kind.replace('melon_','')+'History']=item['charts'][kind]
    for name,url in BRANDS.items():
        try:result['assets']['brands'][name]=image_asset(url,name,64)
        except Exception as exc:
            report['assets'][name]=type(exc).__name__
            old=previous.get('assets',{}).get('brands',{}).get(name,{})
            local=(ROOT/old.get('path','invalid')).resolve()
            if local.is_relative_to((ROOT/'albums/asset-cache').resolve()) and local.is_file() and not local.is_symlink() and hashlib.sha256(local.read_bytes()).hexdigest()==old.get('sha256'):
                result['assets']['brands'][name]=old
    report['manual']=['FLO: approved chart/data endpoint or partner credentials required.', 'Spotify: server-side ISEGYE_SPOTIFY_CLIENT_ID and ISEGYE_SPOTIFY_CLIENT_SECRET for Web API metadata; Web API does not provide public stream counts.', 'Continuous review history: workflow push/manual collects only. No production scheduler modified.']
    path=ROOT/'test-results/albums-domestic';path.mkdir(parents=True,exist_ok=True);(path/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    return result
