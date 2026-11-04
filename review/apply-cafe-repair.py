"""One-use, exact-anchor source integration on the repair branch only."""
from pathlib import Path
import hashlib,json,os
assert os.environ.get('GITHUB_REF') == 'refs/heads/fix/cafe-schedule-refresh'

def change(name,before,after):
    p=Path(name);s=p.read_text()
    assert s.count(before)==1,(name,before[:70],s.count(before))
    p.write_text(s.replace(before,after,1))

change('scripts/notice_policy.py','    cleaned={**value}\n',"    import cafe_runtime\n    runtime=cafe_runtime.source_map(value.get('cafeEvidence'),value['generatedAt'])\n    cleaned={**value}\n")
change('scripts/notice_policy.py','if is_publishable(row)]','if is_publishable(row) or cafe_runtime.matches(row,runtime)]')
change('scripts/schedule_feed.py'," if len(json.dumps(doc).encode())>LIMIT:raise FeedError('snapshot_too_large')"," if len(json.dumps(doc).encode())>LIMIT:raise FeedError('snapshot_too_large')\n if 'cafeEvidence' in doc:\n  import cafe_runtime\n  cafe_runtime.validate_evidence(doc['cafeEvidence'],doc['generatedAt'])")
change('scripts/schedule_feed.py','def collect(previous=None,fetch=request,now=None,berriz_reader=None):','def collect(previous=None,fetch=request,now=None,berriz_reader=None,cafe_review=None):')
change('scripts/schedule_feed.py',' cafe_batch_cards.add(data,now)',' cafe_batch_cards.add(data,now)\n import cafe_runtime\n batch_states.update(cafe_runtime.populate(data,previous,cafe_review,now,batch_states))')
change('scripts/schedule_feed.py',"   current[key]=sorted(byid.values()", "   if key=='forecasts':\n    detailed={r['sourceUrl'] for r in byid.values() if r.get('sourceId')=='fan-roundup' and len(r.get('members',[]))==1}\n    byid={i:r for i,r in byid.items() if not (r.get('sourceId')=='fan-roundup' and len(r.get('members',[]))>1 and r['sourceUrl'] in detailed)}\n   current[key]=sorted(byid.values()")
change('scripts/schedule_feed.py',"   fresh_urls={r['sourceUrl'] for r in current['news'] if r['checkedAt']==current['generatedAt']}","   prior_news={r['sourceUrl']:r for r in previous['news']}\n   fresh_urls={r['sourceUrl'] for r in current['news'] if r['checkedAt']==current['generatedAt'] or (r['sourceId'] in ('cafe-members','cafe-agency') and r['sourceUrl'] in prior_news and iso(r['checkedAt'])>iso(prior_news[r['sourceUrl']]['checkedAt']))}")
change('scripts/publish_schedule_feed.py','import notice_policy','import notice_policy\nimport schedule_health\nfrom collections import Counter')
change('scripts/publish_schedule_feed.py',"        raw=(json.dumps(value","        value['collectionHealth']=schedule_health.assess(value)\n        raw=(json.dumps(value")
change('scripts/publish_schedule_feed.py',"'counts':{k:len(value[k]) for k in ('events','news','forecasts')},","'counts':{k:len(value[k]) for k in ('events','news','forecasts')},\n                'collectionHealth':value['collectionHealth'],\n                'cafeNewsByKstDay':dict(Counter(feed.iso(r['publishedAt']).astimezone(feed.KST).date().isoformat() for r in value['news'] if r['sourceId']=='cafe-members' and r.get('publishedAt'))),\n                'runtimeEvidenceCounts':{k:len(value.get('cafeEvidence',{}).get(k,[])) for k in ('notices','fanSeries')},")
change('scripts/publish_schedule_feed.py','        import paramiko',"        review_path=os.getenv('ISEGYE_CAFE_REVIEW_PATH')\n        packet=None\n        if review_path:\n            import cafe_runtime\n            packet=cafe_runtime.validate_packet(json.loads(Path(review_path).read_text()),feed.stamp())\n        import paramiko")
change('scripts/publish_schedule_feed.py','result=publish(d.Remote(c))','result=publish(d.Remote(c),lambda **kw:feed.collect(**kw,cafe_review=packet))')
change('scripts/publish_schedule_feed.py','The official Cafe Search API is optional. Cafe/internal API crawling is forbidden.','The official Search API is discovery only. Bounded browser-reviewed metadata is supplied by a separate credential-free step; direct Cafe/internal API requests remain forbidden.')
change('scripts/cafe_batch_discovery.py','    result=discover();print(json.dumps(result,ensure_ascii=False));file=',"    result=discover();Path('cafe-discovery.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\\n');print(json.dumps(result,ensure_ascii=False));file=")
change('scripts/review_cafe_window.py','One-time public review. Not an hourly Cafe crawler. No credentials or direct API calls.','Bounded public-list review of two approved boards. No credentials or direct API calls.')
change('scripts/compose_schedule.py',"'generatedAt':snapshot['generatedAt'],'cafeCrawling':False,'unverifiedSearchPublished':False,","'generatedAt':snapshot['generatedAt'],'directCafeApiCrawling':False,'unverifiedSearchPublished':False,\n        'cafePublicWindowReview':{'automatic':True,'boardIds':[345,1250],'overlapDays':3,'runtimeEvidence':True},")
change('schedule/core.js',' if(!Array.isArray(data.sources)'," if(data.cafeEvidence!==undefined)scheduleCafeEvidence(data);\n if(!Array.isArray(data.sources)")
change('schedule/core.js','export function scheduleApprovedRows(rows, approvedSources) {\n return rows.filter(r=>','export function scheduleApprovedRows(rows, approvedSources, snapshot={}) {\n const runtime=scheduleCafeEvidence(snapshot);\n return rows.filter(r=>scheduleCafeMatches(r,runtime)||')
client=r'''

// Same-origin publisher evidence, not a Search snippet or a caller-supplied source label.
export function scheduleCafeEvidence(data) {
 const result=new Map(),proof=data?.cafeEvidence;if(proof===undefined)return result;
 const sameKeys=(value,keys)=>value&&typeof value==='object'&&!Array.isArray(value)&&Object.keys(value).sort().join('|')===[...keys].sort().join('|');
 const members=['ine','jingburger','lilpa','jururu','gosegu','viichan'];
 const official=['articleId','menuId','author','members','title','publishedAt','verifiedRole','public','titleGeneralized','checkedAt'];
 const fan=['articleId','title','date','publishedAt','sameBoard','sameAuthor','public','checkedAt'];
 const stamp=v=>typeof v==='string'&&/(?:Z|[+-]\d{2}:\d{2})$/.test(v)?Date.parse(v):NaN;
 const generated=stamp(data.generatedAt);
 if(!sameKeys(proof,['schemaVersion','notices','fanSeries'])||proof.schemaVersion!==1||!Number.isFinite(generated))throw new Error('invalid Cafe evidence');
 for(const key of ['notices','fanSeries']){
  if(!Array.isArray(proof[key])||proof[key].length>(key==='notices'?600:100))throw new Error('invalid Cafe evidence size');
  for(const r of proof[key]){
   const isOfficial=key==='notices';
   if(!sameKeys(r,isOfficial?official:fan)||!Number.isSafeInteger(r.articleId)||r.articleId<=0||[22133027,22133865].includes(r.articleId)||r.public!==true||typeof r.title!=='string'||!r.title||r.title.length>220||/[<>\x00-\x1f]/.test(r.title))throw new Error('invalid Cafe metadata');
   const url='https://cafe.naver.com/steamindiegame/'+r.articleId,published=stamp(r.publishedAt),checked=stamp(r.checkedAt);
   if(result.has(url)||!Number.isFinite(published)||!Number.isFinite(checked)||published>checked||checked>generated)throw new Error('invalid Cafe observation');
   let source='fan-roundup';
   if(isOfficial){
    if(!Array.isArray(r.members)||!r.members.length||r.members.some(m=>!members.includes(m))||new Set(r.members).size!==r.members.length||typeof r.titleGeneralized!=='boolean')throw new Error('invalid Cafe members');
    if(r.menuId===345&&members.includes(r.author)&&r.verifiedRole==='staff'&&r.members.length===1&&r.members[0]===r.author)source='cafe-members';
    else if(r.menuId===1250&&r.author==='parable'&&['staff','manager'].includes(r.verifiedRole))source='cafe-agency';
    else throw new Error('unapproved Cafe writer');
   }else{
    const m=r.title.match(/^\[\s*(\d{1,2})\/(\d{1,2})\([^)]{1,4}\)\s*\]\s*이세돌\s*뱅온정보$/);
    if(!m||r.sameAuthor!==true||r.sameBoard!==true||!scheduleValidDate(r.date)||schedulePostedDate(r.publishedAt)!==r.date||Number(m[1])!==Number(r.date.slice(5,7))||Number(m[2])!==Number(r.date.slice(8)))throw new Error('unverified fan reference');
   }
   result.set(url,{source,record:r});
  }
 }
 return result;
}
export function scheduleCafeMatches(row,proofs) {
 const proof=proofs.get(row.sourceUrl);if(!proof||row.sourceId!==proof.source||row.publishedAt!==proof.record.publishedAt)return false;
 const r=proof.record;
 if(proof.source==='fan-roundup')return row.date===r.date&&row.dateBasis==='roundup_title'&&['unknown','tentative'].includes(row.certainty);
 return row.title===r.title&&row.checkedAt===r.checkedAt&&JSON.stringify(row.members)===JSON.stringify(r.members);
}
export function scheduleCollectionMessage(data,now=Date.now()) {
 if(!data.collectionHealth)return '';
 const outdated=data.sources.filter(s=>s.id!=='naver-search').some(s=>s.state!=='ok'||!Number.isFinite(Date.parse(s.lastSuccessAt))||now-Date.parse(s.lastSuccessAt)>3*60*60*1000);
 return data.collectionHealth.state!=='complete'||outdated?'일부 출처 수집 지연 · 이전 확인 자료를 표시합니다.':'';
}
'''
p=Path('schedule/core.js');p.write_text(p.read_text()+client)
for bucket in ('news','events','forecasts'):
    change('schedule/ui.js',f'scheduleApprovedRows(scheduleSnapshot.{bucket},noticeApprovedSources)',f'scheduleApprovedRows(scheduleSnapshot.{bucket},noticeApprovedSources,scheduleSnapshot)')
change('schedule/ui.js',"scheduleLoadFailed?'갱신 확인 실패 · 이전 자료를 표시합니다.':''", "scheduleLoadFailed?'갱신 확인 실패 · 이전 자료를 표시합니다.':scheduleCollectionMessage(scheduleSnapshot)")
change('schedule/ui.js',' · 자동 갱신 자료 아님',' · 팬 정리 참고, 실제 방송 확정 아님')
change('schedule/ui.js','카페 본문 정기 크롤링은 사용하지 않습니다. 베리즈와 패러블 공식 뉴스룸은 매시간 갱신을 시도하며 실행이 지연될 수 있습니다.','카페는 승인된 두 공개 게시판의 목록과 같은 작성자의 지정 뱅온정보만 검증합니다. 원문 전체·댓글·로그인 자료는 저장하지 않습니다. 카페 검증 자료·베리즈·패러블 공식 뉴스룸은 매시간 갱신을 시도하며 실행이 지연될 수 있습니다.')
change('schedule/ui.js'," return heading('소식·일정'", " const shownNotices=scheduleAllNews().filter(r=>['cafe-members','cafe-agency'].includes(r.sourceId));\n const lastNotice=shownNotices.map(r=>schedulePostedDate(r.publishedAt)).filter(Boolean).sort().at(-1)||NOTICE_ARCHIVE.end;\n return heading('소식·일정'")
change('schedule/ui.js',"${NOTICE_ARCHIVE.rows.length.toLocaleString('ko-KR')}","${shownNotices.length.toLocaleString('ko-KR')}")
change('schedule/ui.js',"${e(NOTICE_ARCHIVE.end.replaceAll('-','.'))}","${e(lastNotice.replaceAll('-','.'))}")
anchor="    suites.append(('home-presentation','tests/home_presentation_browser.py',{'PRESENTATION_URL':url,'PRESENTATION_OUT':str(out/'home-presentation')}))"
change('scripts/verify_release_v04.py',anchor,anchor+"\n    suites.append(('cafe-runtime','tests/schedule_runtime_browser.py',{'CAFE_RUNTIME_URL':url,'CAFE_RUNTIME_OUT':str(out/'cafe-runtime')}))")
p=Path('review/home-release.json');approval=json.loads(p.read_text())
for key in approval['sourceHashes']:
    approval['sourceHashes'][key]=hashlib.sha256(Path(key).read_bytes()).hexdigest()
for key in ('scripts/cafe_runtime.py','scripts/refresh_reviewed_cafe.py','scripts/schedule_health.py','scripts/schedule_feed.py','scripts/publish_schedule_feed.py'):
    approval['sourceHashes'][key]=hashlib.sha256(Path(key).read_bytes()).hexdigest()
approval['presentationUpdates'].append({'requestedAt':'2026-11-04','scope':'Recover November 3-4 approved public Cafe notices; connect bounded credential-free public-window review to hourly data publication, preserve validated runtime provenance across runs, admit only matching verified runtime sources in the calendar, distinguish publication success from source freshness/incomplete collection. Keep existing author rules, LIVE, auth, legal bodies and hosting boundaries.'})
p.write_text(json.dumps(approval,ensure_ascii=False,indent=2)+'\n')
print('Exact-anchor schedule repair integration complete')
