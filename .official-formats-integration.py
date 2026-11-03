from pathlib import Path

def edit(path,before,after,n=1):
    p=Path(path);s=p.read_text();assert s.count(before)==n,(path,before[:70],s.count(before));p.write_text(s.replace(before,after))
f='scripts/daily_music.py';g='scripts/daily_music_listing.py';j='catalog/daily-music.js'
edit(f,'def classify(k,title):', '''from official_channel_music import EXTRAS, MARKERS, NO as OFFICIAL_NONMUSIC, parse as official_format

def record_keys(row):
    aliases=keys(row['title'],row['members'])
    return {(row['type']+':'+w,artists) for w,artists in aliases} if row['type'] in EXTRAS else aliases

def channel_evidence(k,titles,known):
    if k!='c2':return known
    works=set(known)
    for title in titles:
        r=official_format(clean_text(title),NAMES,performers,keys)
        if r and r['kind'] in ('official_mv','official_audio'):works.update(keys(r['title'],r['members']))
    return works

def needs_review(k,title):
    if k=='c2':return not OFFICIAL_NONMUSIC.search(title) and any(marker.search(title) for _,_,marker in MARKERS)
    return bool(MARK.search(title) and not BLOCK.search(title))

def classify(k,title,evidence=frozenset()):
    if k=='c2':return official_format(clean_text(title),NAMES,performers,keys,evidence)''')
edit(f,"r['type'] not in ('cover','remake','original','official_track')", "r['type'] not in ({'cover','remake','original','official_track'}|EXTRAS)")
edit(f,"        if not isinstance(r['title'],str)","        if r['type'] in EXTRAS and (r['channelKey']!='c2' or r['kind']!='official_video'):raise ValueError('invalid official format')\n        if not isinstance(r['title'],str)")
edit(f,"aliases=keys(r['title'],r['members']);v=r['videoId']", "aliases=record_keys(r);v=r['videoId']",2)
edit(f,"cid,_=CHANNELS[k]; report=", "cid,_=CHANNELS[k]; evidence=set(names); report=")
edit(f,"entries=public_rows(cid,k,now,report,ids)","entries=public_rows(cid,k,now,report,ids,evidence)\n            evidence=channel_evidence(k,(t for _,t,_ in entries),evidence)")
edit(f,'parsed=classify(k,t)','parsed=classify(k,t,evidence)')
edit(f,'if MARK.search(t) and not BLOCK.search(t):report', 'if needs_review(k,t):report')
edit(f,"if keys(parsed['title'],parsed['members']) & names:continue", "if record_keys(parsed) & names:continue")
edit(g,'def public_rows(cid,k,now,report,known):','def public_rows(cid,k,now,report,known,evidence):')
edit(g,"    for vid,(title,age) in list(found.items())[:35]:", "    evidence.update(m.channel_evidence(k,(title for title,_ in found.values()),evidence))\n    for vid,(title,age) in list(found.items())[:35]:")
edit(g,"        if vid in known or not m.MARK.search(title) or m.BLOCK.search(title):continue\n        if not m.classify(k,title):report['review'].append(vid);continue", "        if vid in known:continue\n        if not m.classify(k,title,evidence):\n            if m.needs_review(k,title):report['review'].append(vid)\n            continue")
edit(g,"            if details.get('channelId')!=cid or details.get('videoId')!=vid or details.get('isLiveContent') or details.get('isUpcoming') or m.clean_text(details.get('title',''))!=m.clean_text(title):raise ValueError('video identity mismatch')\n            stamp=m.clock(micro.get('publishDate') or micro.get('uploadDate') or '')", "            from official_channel_music import OBSERVED_ATOM\n            saved=OBSERVED_ATOM.get((cid,vid,title)) if k=='c2' else None\n            if not details and not micro and saved and player.get('playabilityStatus',{}).get('status')=='LOGIN_REQUIRED':\n                # Public channel tile matched; independent current oEmbed verification still required.\n                stamp=m.clock(saved)\n            else:\n                if details.get('channelId')!=cid or details.get('videoId')!=vid or details.get('isLiveContent') or details.get('isUpcoming') or m.clean_text(details.get('title',''))!=m.clean_text(title):raise ValueError('video identity mismatch')\n                stamp=m.clock(micro.get('publishDate') or micro.get('uploadDate') or saved or '')")
edit(j,"const signature=(s)=>s.title", "const extras={album_medley:'앨범 하이라이트 메들리',music_clip:'음악 스페셜클립'};\n  const signature=(s)=>(Object.hasOwn(extras,s.type)?s.type+':':'')+s.title")
edit(j,"['cover','remake','original','official_track'].includes(r.type)","['cover','remake','original','official_track','album_medley','music_clip'].includes(r.type)")
edit(j,'    const p=Date.parse(r.publishedAt)',"    if(Object.hasOwn(extras,r.type) && (r.channelKey!=='c2'||r.kind!=='official_video'))throw Error('Invalid official channel format');\n    const p=Date.parse(r.publishedAt)")
edit(j,"format:r.kind==='official_audio'?'공식 오디오':'공식 음악 영상'", "format:extras[r.type]||(r.kind==='official_audio'?'공식 오디오':r.kind==='official_mv'?'공식 MV':'공식 음악 영상')")
edit('catalog/core.js',"official_track:'공식 음원·MV'", "official_track:'공식 음원·MV',album_medley:'앨범 메들리',music_clip:'음악 스페셜클립'")
edit('catalog/video-ui.js','function musicVideoLabel(s){return MUSIC_VIDEO_LABELS',"function musicVideoLabel(s){if(s.type==='album_medley'||s.type==='music_clip')return s.format;return MUSIC_VIDEO_LABELS")
edit('scripts/enhance_catalog.py',"'endpoint':'/api/music','reviewedBaseline'", "'endpoint':'/api/music','officialFormats':1,'reviewedBaseline'")
edit('scripts/publish_daily_music.py',"    if remote.info(DIR) is None:","    if any(r['type'] in music.EXTRAS for r in fresh):d.require(meta['dailyMusic'].get('officialFormats')==1,'Official format renderer not active')\n    if remote.info(DIR) is None:")
edit('.github/workflows/music-daily.yml','-p test_daily_music.py',"-p 'test_daily_music*.py'")
p=Path('tests/daily-music.test.js');p.write_text(p.read_text()+'''
test('official medley and music clip coexist with the work without replacing reviewed or duplicate video IDs',()=>{
 const c=setup();c.DAILY_MUSIC_CHANNELS.c2={name:'ISEGYE IDOL',url:'https://www.youtube.com/@isegyeidol_ofcl'};
 const mk=(videoId,type)=>({...row,videoId,title:'옛 곡',members:['ine'],channelKey:'c2',type,kind:'official_video'});
 const med=mk('lFgCjRoFjyU','album_medley'),clip=mk('8IY44RZHyw8','music_clip');
 assert.equal(c.applyDailyMusic(doc([med,clip,med])),2);assert.equal(c.CATALOG.music.songs.length,3);
 assert.equal(c.catalogSongs.get('daily-lFgCjRoFjyU').format,'앨범 하이라이트 메들리');assert.equal(c.catalogSongs.get('daily-8IY44RZHyw8').format,'음악 스페셜클립');assert.equal(c.catalogSongs.get('a').title,'옛 곡');
 assert.throws(()=>c.applyDailyMusic(doc([{...med,channelKey:'c14'}])));assert.equal(c.CATALOG.music.songs.length,3);
});
''')
p=Path('docs/BATCHES.md');p.write_text(p.read_text()+'''
### 공식 그룹 채널: 음악 이외의 업로드 제외

`@isegyeidol_ofcl`은 여러 종류의 채널이므로 공식 채널이라는 이유나 `Highlight` 단어만으로 등록하지 않는다. 아티스트·작품명·형식이 명시된 공식 음원/MV, 앨범 하이라이트 메들리, 음악 스페셜클립을 수집한다. 일반 `Special Clip`은 같은 아티스트의 카탈로그 또는 동일 공식 목록의 오디오/MV에서 곡명이 확인될 때만 허용한다. 보컬·라이브·퍼포먼스가 명시된 음악 스페셜클립도 허용한다. 일반 예능, 뉴스, 티저, 메이킹, 비하인드, 리액션, 쇼츠는 제외한다. 다른 8개 채널의 수집 범위와 06:43 예약은 그대로다.

메들리는 앨범 단위의 영상 기록 한 건(수록곡 발매가 아님), 스페셜클립은 별도 음악 영상이다. 영상 ID는 전역에서 한 번만 등록하며, 서로 다른 포맷이 같은 작품명을 쓸 수 있다. 날짜는 공식 영상 공개일이다. `lFgCjRoFjyU`의 공개 시각은 공식 Atom의 `<published>`에서 2026-11-02T09:00:14Z로 확인했다. 같은 채널·영상 ID·제목을 재확인하는 경우에만 이 값을 재사용하고, 상대 날짜와 음반 발매일은 사용하지 않는다.
''')
