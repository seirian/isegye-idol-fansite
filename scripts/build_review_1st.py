#!/usr/bin/env python3
"""Build an isolated, source-backed first-review application. No remote writes.

Input: already verified preview bundle; output: review-1st-dist only.
The self-contained review.html is an offline review, not a public mirror.
"""
from __future__ import annotations
import argparse,base64,hashlib,json,os,re,shutil,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9))
BASE='1ec11cd8b6cc730fa6fc136c39e019fce6fcfe09'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def extract(text,name):
    m=re.search(r'^(?:const|let) '+re.escape(name)+r'\s*=\s*([^\n]+)',text,re.M)
    if not m:raise ValueError('Missing baseline data: '+name)
    return json.loads(m[1].rstrip(';'))
def day(s):
    if not s:return ''
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',s):return s
    return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(KST).date().isoformat()
def script_json(obj):return json.dumps(obj,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')

def build(baseline, snapshot_path=None, output_path=None):
    if os.getenv('DEPLOY_ENV')=='production' or os.getenv('GITHUB_REF') in ('refs/heads/main','refs/heads/develop'):
        raise RuntimeError('First review is feature-branch/local only; production is untouched')
    if not (baseline/'build-info.json').is_file():raise ValueError('Build approved baseline with npm run build first')
    meta=json.loads((baseline/'build-info.json').read_text())
    if meta.get('mode')!='preview':raise ValueError('Input must be a noindex review bundle')
    text=(baseline/'src/app.js').read_text()
    catalog=extract(text,'CATALOG'); history=extract(text,'HISTORY');archive=extract(text,'NOTICE_ARCHIVE');gallery=extract(text,'HOME_GROUP_GALLERY')
    snapshot=json.loads((Path(snapshot_path) if snapshot_path else ROOT/'review-1st/fixtures/schedule-observed.json').read_text())
    sys.path.insert(0,str(ROOT/'scripts'))
    import schedule_feed,notice_policy
    schedule_feed.validate(snapshot)
    snapshot=notice_policy.clean_snapshot(snapshot)
    names={m['id']:m['name'] for m in catalog['members']};allids=list(names)
    videos={};channels={}
    for person in catalog['members']:
        for ch in person['channels']:
            feed=next((r for r in catalog['videos']['channels'] if r['key']==ch['key']),{})
            channels[ch['key']]={**ch,'member':person['id'],'checkedAt':feed.get('checkedAt'),'status':feed.get('status')}
            for row in feed.get('videos',[]):
                vid=row['id'];videos[vid]={**row,'key':'video:'+vid,'kind':'video','date':day(row['publishedAt']),'url':'https://www.youtube.com/watch?v='+vid,'members':[person['id']],'memberBasis':'channel_owner','channelName':ch['name'],'channelKey':ch['key'],'channelUrl':ch['url'],'category':'replay' if ch['kind']=='다시보기' else 'member','format':ch['kind'],'checkedAt':feed.get('checkedAt'),'type':ch['kind'],'summary':'채널에 공개된 영상 목록입니다. 업로드일을 표시하며 실제 방송일·전체 출연진은 별도로 확인하지 않았습니다.','tags':[ch['kind'],person['en']]}
    # Metadata already independently observed by the production music collector.
    from official_channel_music import OBSERVED_ATOM
    for (cid,vid,title),at in OBSERVED_ATOM.items():
        videos[vid]={'id':vid,'key':'video:'+vid,'kind':'video','title':title,'date':day(at),'publishedAt':at,'url':'https://www.youtube.com/watch?v='+vid,'members':allids,'memberBasis':'explicit_group','channelName':'ISEGYE IDOL','channelKey':'c2','channelUrl':'https://www.youtube.com/@isegyeidol_ofcl','category':'group','format':'앨범 메들리','checkedAt':None,'type':'album_medley','summary':'공식 채널의 앨범 하이라이트 메들리. 영상 공개일과 앨범 발매일은 서로 다릅니다.','tags':['Across Dimensions','단체 공식','메들리']}
    wh=json.loads((ROOT/'catalog/waktaverse-history.json').read_text())
    # Existing reviewed explicit credits only; never infer all six from an unknown title.
    for row in wh['videos']:
        vid=row['videoId'];title=row['sourceTitle'];mids=[i for i,n in names.items() if n in title]
        if re.search(r'이세계\s*아이돌|이세돌',title):mids=allids
        videos.setdefault(vid,{'id':vid,'key':'video:'+vid,'kind':'video','title':title,'date':row['publishedDate'],'url':'https://www.youtube.com/watch?v='+vid,'members':mids,'memberBasis':'reviewed_title_credit','channelName':'왁타버스 WAKTAVERSE','channelKey':'c1','channelUrl':'https://www.youtube.com/@waktaverse','category':'group','format':'공식 음악·무대','checkedAt':wh['reviewedAt'],'type':'performance','summary':'검토된 왁타버스 공개 영상입니다. 원문 공개 날짜 기준이며 방송일을 추정하지 않습니다.','tags':['왁타버스','무대','음악']})
    songs=[];albums={}
    for row in catalog['music']['songs']:
        s={**row,'kind':'song','key':'song:'+row['id'],'summary':row.get('album') or row.get('format',''),'tags':row.get('aliases',[])+row.get('albumTracks',[]),'checkedAt':row.get('videoSource',{}).get('checkedAt',catalog['music']['checkedAt'])}
        s['sourceLinks']=[catalog['music']['sources'][x] for x in row.get('sources',[]) if x in catalog['music']['sources']]
        if s.get('album'):
            key=hashlib.sha256((s['album']+'|'+','.join(sorted(s['members']))).encode()).hexdigest()[:12]
            s['albumId']=key
            a=albums.setdefault(key,{'id':key,'title':s['album'],'kind':'album','key':'album:'+key,'date':s['date'],'members':s['members'],'songIds':[],'tracks':s.get('albumTracks',[]),'format':s.get('format',''),'sourceLinks':s['sourceLinks']})
            a['songIds'].append(s['id'])
            if s['date']<a['date']:a['date']=s['date']
            if len(s.get('albumTracks',[]))>len(a['tracks']):a['tracks']=s['albumTracks']
        songs.append(s)
        vid=s.get('videoId');source=s.get('videoSource',{})
        if vid and source.get('kind','').startswith('official') and ('waktaverse' in source.get('channelUrl','').lower() or 'isegyeidol_ofcl' in source.get('channelUrl','').lower()):
            # Catalog dates are release dates; do NOT re-label these as upload dates.
            videos.setdefault(vid,{'id':vid,'key':'video:'+vid,'kind':'video','title':s['title'],'date':s['date'],'dateBasis':'catalog','dateLabel':s['dateKind'],'url':'https://www.youtube.com/watch?v='+vid,'members':s['members'],'memberBasis':'catalog_credit','channelName':source.get('channel','공식 채널'),'channelKey':'c1' if 'waktaverse' in source.get('channelUrl','').lower() else 'c2','channelUrl':source.get('channelUrl',''),'category':'group','format':s['format'],'checkedAt':s['checkedAt'],'type':source.get('kind'),'summary':'음악 카탈로그에 연결된 공식 영상입니다. 날짜는 '+s['dateKind']+' 기준이며 업로드 시각은 별도 확인이 필요합니다.','relatedSong':s['id'],'tags':s['tags']})
    notices={}
    for r in archive['rows']:
        aid,menu,author,mids,title,published,generalized,checked=r
        notices[str(aid)]={'id':str(aid),'key':'notice:'+str(aid),'kind':'notice','title':title,'date':day(published),'publishedAt':published,'members':mids,'url':'https://cafe.naver.com/steamindiegame/'+str(aid),'sourceId':'cafe-members' if menu==345 else 'cafe-agency','checkedAt':checked,'summary':'공개 목록에서 작성자·게시일을 확인한 공지입니다. 본문 전체와 변경 이력은 원문에서 확인해 주세요.','tags':['공지','멤버 공지' if menu==345 else '소속사 공지'],'type':'notice'}
    for r in snapshot['news']:
        aid=r['sourceUrl'].rstrip('/').split('/')[-1] if r['sourceId'].startswith('cafe-') else r['id']
        notices[aid]={**r,'id':aid,'key':'notice:'+aid,'kind':'notice','date':day(r['publishedAt']),'url':r['sourceUrl'],'summary':r.get('detail',''),'tags':['공지'],'type':'notice'}
    events=[{**r,'kind':'event','key':'event:'+r['id'],'url':r['sourceUrl'],'summary':r.get('detail',''),'tags':['일정']} for r in snapshot['events']]
    histories=[]
    for row in history['events']:
        histories.append({**row,'key':'history:'+row['id'],'kind':'history','summary':row.get('summary','') or row.get('note','') or '공개 출처를 바탕으로 정리한 주요 활동 기록입니다.','sourceLinks':[history['sources'][x] for x in row.get('sources',[]) if x in history['sources']],'checkedAt':history['checkedAt'],'tags':['활동 기록']})
    series=[{'id':'festival-2025','title':'2025 이세계페스티벌','subtitle':'공식 무대 영상 모아보기','description':'왁타버스에서 공개한 STARGAZERS·MEMORY·ELEVATE 무대 영상으로 이어집니다. 공연과 영상의 공개 날짜는 구분합니다.','videoIds':[i for i in ['MCyL9k_Tiok','nsVbRO_k9b8','7V7ZsMt6r-w'] if i in videos],'members':allids,'basis':'reviewed_official_performance','status':'공식 원본 연결'},
      {'id':'music-beginning','title':'처음 만나는 이세돌의 음악','subtitle':'입문 경로 · 운영자 선정','description':'데뷔곡과 단체 발매곡으로 만나는 짧은 감상 경로입니다. 인기순이나 공식 추천 목록이 아닙니다.','songIds':[r['id'] for r in songs if r['id'] in ['rewind','kidding','smile-for-you','smile','be-my-light']][:5],'members':allids,'basis':'editorial','status':'선정 기준 공개'}]
    data={'schemaVersion':1,'baseCommit':BASE,'builtAt':datetime.now(timezone.utc).isoformat(),'snapshotAt':snapshot['generatedAt'],'members':catalog['members'],'channels':list(channels.values()),'songs':songs,'albums':list(albums.values()),'videos':list(videos.values()),'notices':list(notices.values()),'events':events,'history':histories,'series':series,'sources':snapshot['sources'],'forecasts':snapshot['forecasts'],'scope':{'archiveFrom':archive['start'],'archiveThrough':archive['end'],'historicalComplete':False,'videoCheckedAt':catalog['videos']['checkedAt'],'musicCheckedAt':catalog['music']['checkedAt'],'historyCheckedAt':history['checkedAt'],'collectionHealth':snapshot.get('collectionHealth')},'gallery':[{**g,'src':g['src'].removeprefix('./')} for g in gallery],'assets':{'portraits':{i:'assets/portraits/'+i+'.webp' for i in allids},'soop':{i:'assets/soop-profiles/'+i+'.webp' for i in allids}}}
    out=Path(output_path) if output_path else ROOT/'review-1st-dist'
    if out.parent.resolve()!=ROOT or (output_path and not out.name.startswith('release-')):raise ValueError('Invalid release intermediate output')
    if out.is_symlink():raise ValueError('Symlink output refused')
    if out.exists():shutil.rmtree(out)
    out.mkdir()
    shutil.copytree(baseline/'assets',out/'assets')
    for name in ['app.js','styles.css','index.html']:
        shutil.copy2(ROOT/'review-1st'/name,out/name)
    for file,target in [(ROOT/'review-1st/core.js','core.js'),(ROOT/'live/core.js','live-core.js')]:
        (out/target).write_text(re.sub(r'^export ','',file.read_text(),flags=re.M))
    (out/'data.js').write_text('const REVIEW_DATA='+script_json(data)+';\n')
    (out/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    manifest={'review':'review-1st','branch':'feature/review-1st','baseCommit':BASE,'commit':os.getenv('GITHUB_SHA','local-unpublished'),'builtAt':data['builtAt'],'mode':'isolated-preview','publicDeployment':False,'productionWrites':False,'snapshotAt':data['snapshotAt'],'counts':{k:len(data[k]) for k in ['members','songs','albums','videos','notices','events','history','series']}}
    (out/'build-info.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    # Self-contained HTML needs no server. Only approved remote images/LIVE may be fetched.
    copy=json.loads(json.dumps(data))
    def inline(path):return 'data:image/webp;base64,'+base64.b64encode((out/path.split('?')[0]).read_bytes()).decode()
    for group in copy['assets'].values():
        for key,value in group.items():group[key]=inline(value)
    for item in copy['gallery']:item['src']=inline(item['src'])
    css=(out/'styles.css').read_text()
    code='const REVIEW_DATA='+script_json(copy)+';\n'+(out/'core.js').read_text()+'\n'+(out/'live-core.js').read_text()+'\n'+(out/'app.js').read_text()
    sha=lambda s:"'sha256-"+base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()+"'"
    html=(out/'index.html').read_text()
    html=html.replace("script-src 'self'","script-src "+sha(code)).replace("style-src 'self'","style-src "+sha(css))
    html=re.sub(r'<link rel="icon"[^>]+>','',html)
    html=html.replace('<link rel="stylesheet" href="styles.css">','<style>'+css+'</style>')
    html=re.sub(r'<script src="(?:data|core|live-core|app)\.js"></script>','',html)
    html=html.replace('</body>','<script>'+code+'</script></body>')
    (out/'review.html').write_text(html)
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',default=str(ROOT/'dist'));args=parser.parse_args()
    build(Path(args.baseline).resolve())
