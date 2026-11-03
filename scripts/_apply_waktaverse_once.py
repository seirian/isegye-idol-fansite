"""One-time work-branch patch; removed before promotion. No production access."""
from pathlib import Path
import json,re,sys
ROOT=Path.cwd()
def patch(name,old,new):
 p=ROOT/name;s=p.read_text();assert s.count(old)==1,(name,old[:80],s.count(old));p.write_text(s.replace(old,new))
patch('scripts/daily_music.py',"FIELDS={'videoId','channelKey','title','members','type','kind','publishedAt','checkedAt'}", "FIELDS={'videoId','channelKey','title','members','type','kind','publishedAt','checkedAt'}\nOPTIONAL_FIELDS={'datePrecision','credits','context'}\nPERFORMANCE_TYPES={'performance'}")
patch('scripts/daily_music.py','def norm(s):', "def publication_clock(s):\n    # Date-only metadata stays date-only in storage/UI; this is for ordering only.\n    if re.fullmatch(r'20\\d{2}-\\d{2}-\\d{2}',s or ''):return datetime.fromisoformat(s).replace(tzinfo=KST)\n    return clock(s)\n\ndef norm(s):")
patch('scripts/daily_music.py',"titles=set().union(*(keys(r['title'],r['members']) for r in m['songs']))", "titles=set().union(*(keys(t,r['members']) for r in m['songs'] for t in [r['title'],*r.get('aliases',[])]))")
patch('scripts/daily_music.py',"    aliases=keys(row['title'],row['members'])", "    if row['type'] in PERFORMANCE_TYPES:return {('performance:'+norm(row['title']),tuple(sorted(row['members'])))}\n    aliases=keys(row['title'],row['members'])")
patch('scripts/daily_music.py',"    if k!='c2':return known", "    if k not in ('c1','c2'):return known")
patch('scripts/daily_music.py',"        r=official_format(clean_text(title),NAMES,performers,keys)", "        r=classify(k,clean_text(title),known)")
patch('scripts/daily_music.py','def needs_review(k,title):', "def needs_review(k,title):\n    if k=='c1':\n        from waktaverse_music import MUSIC,NONMUSIC\n        return bool(MUSIC.search(title) and not NONMUSIC.search(title) and (GROUP.search(title) or performers(title)))")
patch('scripts/daily_music.py','def classify(k,title,evidence=frozenset()):', "def classify(k,title,evidence=frozenset()):\n    if k=='c1':\n        from waktaverse_music import parse as waktaverse_format\n        return waktaverse_format(clean_text(title),NAMES,performers,keys,evidence)")
patch('scripts/daily_music.py','if set(r)!=FIELDS or', 'if not FIELDS<=set(r) or not set(r)<=FIELDS|OPTIONAL_FIELDS or')
patch('scripts/daily_music.py',"({'cover','remake','original','official_track'}|EXTRAS)", "({'cover','remake','original','official_track'}|EXTRAS|PERFORMANCE_TYPES)")
patch('scripts/daily_music.py',"        if r['type'] in EXTRAS and (r['channelKey']!='c2' or r['kind']!='official_video'):raise ValueError('invalid official format')", """        if r['type'] in EXTRAS and (r['channelKey'] not in ('c1','c2') or r['kind']!='official_video'):raise ValueError('invalid official format')
        if r['type'] in PERFORMANCE_TYPES and (r['channelKey']!='c1' or r['kind']!='official_video'):raise ValueError('invalid performance source')
        if 'context' in r and (r['channelKey']!='c1' or r['context'] not in ('collab','festival')):raise ValueError('invalid music context')
        if 'credits' in r and (r['channelKey']!='c1' or not isinstance(r['credits'],str) or not 0<len(r['credits'])<=200 or re.search(r'[<>\\x00-\\x1f]',r['credits'])):raise ValueError('invalid collaborator credits')
        day=bool(re.fullmatch(r'20\\d{2}-\\d{2}-\\d{2}',r['publishedAt'] or ''))
        if day != (r.get('datePrecision')=='day') or ('datePrecision' in r and r['datePrecision']!='day'):raise ValueError('invalid publication precision')""")
patch('scripts/daily_music.py',"if clock(r['publishedAt'])>clock(r['checkedAt'])", "if publication_clock(r['publishedAt'])>clock(r['checkedAt'])")
patch('scripts/daily_music.py',"                rows.append(dict(parsed,videoId=v,channelKey=k,publishedAt=p,checkedAt=now.isoformat()))", "                rows.append(dict(parsed,videoId=v,channelKey=k,publishedAt=p,checkedAt=now.isoformat(),**({'datePrecision':'day'} if len(p)==10 else {})))")
patch('scripts/daily_music.py','        return k,rows,report', """        if k=='c1':
            from waktaverse_history import collect
            historical,coverage=collect(now);rows.extend(historical);report['historical']=coverage
            if coverage['errors']:
                report['review'].extend(e['videoId'] for e in coverage['errors']);report['state']='partial' if rows or report['state']!='error' else 'error'
            elif rows and report['state']=='error':report['state']='partial'
        return k,rows,report""")
patch('scripts/daily_music_listing.py',"            body=m.read('https://www.youtube.com/watch?v='+vid+'&hl=en',5500000).decode();", """            body=m.read('https://www.youtube.com/watch?v='+vid+'&hl=en',5500000).decode();
            if k=='c1':
                from music_public_metadata import public_watch_date
                day=public_watch_date(body,cid,vid,title)
                if now-timedelta(days=30)<=m.publication_clock(day)<=now:out.append((vid,title,day))
                continue
            """)
patch('scripts/enhance_catalog.py',"'officialFormats':1,", "'officialFormats':1,'waktaverseFormats':1,")
patch('scripts/publish_daily_music.py',"    if any(r['type'] in music.EXTRAS for r in fresh):", "    if any(r['type'] in music.PERFORMANCE_TYPES or set(r)&music.OPTIONAL_FIELDS for r in fresh):d.require(meta['dailyMusic'].get('waktaverseFormats')==1,'Waktaverse music renderer not active')\n    if any(r['type'] in music.EXTRAS for r in fresh):")
patch('scripts/publish_daily_music.py',"'newItems':added,", "'newItems':added,'waktaverseIds':[r['videoId'] for r in rows if r['channelKey']=='c1'],'waktaverseHistory':review['sources']['c1'].get('historical'),")
p=ROOT/'catalog/music.json';d=json.loads(p.read_text());aliases={'rewind':['리와인드','REWIND','RE:WIND'],'kidding':['키딩'],'another-world':['어나더 월드'],'lockdown':['락다운'],'stargazers':['스타게이저스']}
for s in d['songs']:
 if s['id'] in aliases:s['aliases']=aliases[s['id']]
p.write_text(json.dumps(d,ensure_ascii=False,separators=(',',':'))+'\n')
patch('catalog/core.js',"music_clip:'음악 스페셜클립'", "music_clip:'음악 스페셜클립',performance:'공연·편곡'")
patch('catalog/core.js','export function catalogQuery(params)', "export const catalogIsOfficialTrack=s=>s.type==='official_track'||['official_mv','official_audio'].includes(s.videoSource?.kind);\nexport function catalogQuery(params)")
patch('catalog/core.js',"  const found=items.filter(s=>(q.type==='all'||s.type===q.type)", "  const compact=s=>s.normalize('NFKC').toLocaleLowerCase('ko').replace(/[^\\p{L}\\p{N}]/gu,'');\n  const found=items.filter(s=>(q.type==='all'||s.type===q.type||(q.type==='official_track'&&catalogIsOfficialTrack(s)))")
patch('catalog/core.js',"[s.title,s.album||'',s.format,s.members.map(id=>names[id]||id).join(' ')].join(' ').normalize('NFKC').toLocaleLowerCase('ko').includes(w)", "(()=>{const hay=[s.title,...(s.aliases||[]),s.title.includes('RE:WIND')||s.title.includes('RE : WIND')?'리와인드':'',s.album||'',s.format,s.scope==='group'?'이세계아이돌 이세돌 ISEGYE IDOL':'',s.videoSource?.channel||'',s.videoSource?.kind==='official_mv'?'공식 MV 뮤직비디오':'',s.members.map(id=>names[id]||id).join(' ')].join(' ').normalize('NFKC').toLocaleLowerCase('ko');return hay.includes(w)||(compact(w)&&compact(hay).includes(compact(w)));})()")
for old,new in [("CATALOG.music.songs.some(s=>s.type==='official_track')","CATALOG.music.songs.some(catalogIsOfficialTrack)"),("CATALOG.music.songs.filter(s=>s.type==='official_track').length","CATALOG.music.songs.filter(catalogIsOfficialTrack).length")]:patch('catalog/ui.js',old,new)
patch('catalog/daily-music.js',"music_clip:'음악 스페셜클립'", "music_clip:'음악 스페셜클립',performance:'공식 공연·편곡 영상'")
patch('catalog/daily-music.js',"'album_medley','music_clip'].includes", "'album_medley','music_clip','performance'].includes")
patch('catalog/daily-music.js',"(r.channelKey!=='c2'||r.kind!=='official_video')", "(!['c1','c2'].includes(r.channelKey)||r.kind!=='official_video'||(r.type==='performance'&&r.channelKey!=='c1'))")
patch('catalog/daily-music.js','    const p=Date.parse(r.publishedAt)', """    if(r.context!==undefined&&(!['collab','festival'].includes(r.context)||r.channelKey!=='c1'))throw Error('Invalid context');
    if(r.credits!==undefined&&(typeof r.credits!=='string'||!r.credits||r.credits.length>200||/[<>\\x00-\\x1f]/.test(r.credits)||r.channelKey!=='c1'))throw Error('Invalid credits');
    const day=/^20\\d{2}-\\d{2}-\\d{2}$/.test(r.publishedAt);if(day!==(r.datePrecision==='day')||(r.datePrecision!==undefined&&r.datePrecision!=='day'))throw Error('Invalid date precision');
    const p=Date.parse(r.publishedAt)""")
patch('catalog/daily-music.js',"context:'standard',date:new Date(p+9*3600000).toISOString().slice(0,10)", "context:r.context||'standard',date:day?r.publishedAt:new Date(p+9*3600000).toISOString().slice(0,10)")
patch('catalog/daily-music.js',"note:'공식 채널의 공개 영상 기준으로 일배치에서 등록했습니다. 영상 공개일과 음반 발매일은 다를 수 있습니다.'", "note:(r.credits?'공동 참여·피처링: '+r.credits+'. ':'')+(day?'YouTube 원문에 표시된 공개 날짜 기준이며 시각·시간대는 추정하지 않습니다. ':'')+'공식 채널의 공개 영상 기준으로 일배치에서 등록했습니다. 영상 공개일과 음반 발매일은 다를 수 있습니다.'")
# Date.parse normalizes impossible dates; reject those rather than displaying them.
p=ROOT/'catalog/daily-music.js';s=p.read_text();s=s.replace("throw Error('Invalid music timestamp');", "throw Error('Invalid music timestamp');if(day&&new Date(p).toISOString().slice(0,10)!==r.publishedAt)throw Error('Invalid publication date');");p.write_text(s)
p=ROOT/'catalog/video-ui.js';s=p.read_text();assert "s.type==='album_medley'||s.type==='music_clip'" in s;p.write_text(s.replace("s.type==='album_medley'||s.type==='music_clip'","s.type==='album_medley'||s.type==='music_clip'||s.type==='performance'"))
# Existing c2 exclusion now deliberately permits c1, but no other channel's scope changes.
p=ROOT/'tests/test_daily_music_formats.py';s=p.read_text();s=s.replace("if k!='c2'", "if k not in ('c1','c2')");p.write_text(s)
# Generate reviewed historical queue from the actual read-only audit artifact.
sys.path.insert(0,str(ROOT/'scripts'));import daily_music as m
D=json.loads(Path('/tmp/waktaverse-audit/audit.json').read_text());baseline=m.baseline()[0]
accepted=set('MCyL9k_Tiok nsVbRO_k9b8 nz2_gNQDiVM 7V7ZsMt6r-w DJLa8QYUtmQ v9Jqz13gg8k JiIvPGY2Xdk KLOevIVg7Ww rDFUl2mHIW4 fgSXAKsq-Vo Empfi8q0aas JY-gJkMuJ94 wyhwJnNpVJI 8KTFf2X-ago QgMFpuos4Rg k5O1F_IS0mU YmELthNomns i4SRH9jfUMQ K8WC6uWyC9I 7XFJ4s0j9z0 plO-C9aSwxs YZ0xA3LUzNQ owlLg3R9u6c IzrIYIqlBnA YwQkPlFlOJQ DIomV3Ebmz8'.split());h=[];fixtures=[]
for x in D['candidates']:
 v=x['videoId'];yes=v in accepted;fixtures.append({'videoId':v,'title':x['title'],'music':yes})
 assert bool(m.classify('c1',x['title'],m.baseline()[1]))==yes,(v,x['title'])
 if not yes or v in baseline:continue
 raw=next(d['dateText']['simpleText'] for d in x['dates'] if 'dateText' in d);a=re.search(r'(20\d{2})\.\s*(\d+)\.\s*(\d+)\.',raw).groups();day=f'{int(a[0]):04}-{int(a[1]):02}-{int(a[2]):02}';h.append({'videoId':v,'sourceTitle':x['title'],'publishedDate':day})
assert len(h)==15 and len(fixtures)==44
(ROOT/'catalog/waktaverse-history.json').write_text(json.dumps({'schemaVersion':1,'channelId':m.CHANNELS['c1'][0],'reviewedAt':D['checkedAt'],'coverage':{'publicVideoIdsChecked':len(D['videos']),'artistRelatedCandidates':len(D['candidates']),'acceptedMusicVideos':26,'alreadyRegistered':11,'historicalQueue':15,'note':'Bounded observed public listings and channel searches, not a claim of all past or unavailable uploads. Exact page date only; no time-zone inference.'},'videos':h},ensure_ascii=False,indent=2)+'\n')
(ROOT/'tests/fixtures/waktaverse-titles.json').write_text(json.dumps(fixtures,ensure_ascii=False,indent=2)+'\n')
# Keep the recently approved UI cleanup suite; append only our additional browser suite.
p=ROOT/'scripts/verify_release_v04.py';s=p.read_text();lines=s.splitlines(True);anchor=next(line for line in lines if "suites.append(('daily-music'" in line);indent=anchor[:len(anchor)-len(anchor.lstrip())];s=s.replace(anchor,anchor+indent+"suites.append(('waktaverse','tests/waktaverse_browser.py',{'WAKTA_TEST_URL':url,'WAKTA_OUT':str(out/'waktaverse')}))\n");assert 'ui_cleanup_browser.py' in s;p.write_text(s)
p=ROOT/'docs/BATCHES.md';s=p.read_text();s+='''

### 왁타버스 음악 누락 보충과 검색

왁타버스 `@waktaverse`는 기존 9개 공식 채널의 c1이다. 중복 채널을 추가하지 않고 제목 판별과 과거 보충을 강화했다. 매일 06:43 KST 예약은 유지한다. 최근 30일 신규 조회에 더해 `catalog/waktaverse-history.json`의 검토된 과거 영상 15건도 매번 원문·업로더·oEmbed·썸네일을 확인한다. 실패 시 기존 자료를 보존하고 검토 보류로 남긴다.

확인한 공개 영상 ID 134개에서 관련 후보 44개, 음악 26개(기존 11개, 누락 15개)를 선별했다. 전체 과거/비공개 영상에 대한 완전 수집 보증은 아니다. 명시적인 멤버 참여 음악·MV·협업/피처링·CM송과 확인된 곡의 공연/재즈 버전만 허용하고 타 출연자만의 노래, 티저, 안무, 쇼츠, BGM, 예능, 리액션은 제외한다. 협업 원문 참여정보는 상세에 남긴다.

공연·편곡은 별도 영상 유형으로 원곡을 덮어쓰지 않는다. 공개 페이지에 날짜만 있으면 `publishedAt: YYYY-MM-DD`, `datePrecision: day`로 기록하고 시각·시간대를 추정하지 않는다. canonical 영상 ID, 본문 제목과 업로더 ID가 모두 일치해야 공개 날짜를 채택한다. 기존 음반 발매일은 그대로다.

RE : WIND의 공식 MV `fgSXAKsq-Vo`는 재등록하지 않는다. 리와인드/REWIND/RE:WIND 검색과 기존 오리지널 곡의 공식 MV·오디오 필터를 지원한다. 일배치 보고서에 `waktaverseIds`, `waktaverseHistory` 검증 결과를 남긴다.
''';p.write_text(s)
print('Applied narrow Waktaverse changes; historical rows:',len(h))
