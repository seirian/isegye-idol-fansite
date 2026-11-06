#!/usr/bin/env python3
"""Second review: keep review-1 immutable, reuse production LIVE/member renderers.
Only generates review-2nd-dist. It cannot publish or change production/auth data.
"""
from pathlib import Path
import argparse, base64, hashlib, json, os, re, shutil
import tinycss2
import build_review_1st as first
import review_2nd_polish as polish
import review_2nd_cleanup as cleanup
ROOT=Path(__file__).resolve().parents[1]
PRODUCTION='b05d0c91f482dfd666e2b70e70c49ebe4ece2175'
FIRST='013998a27293d28fc54ba17950e190f5ed9f6db5'

def one(text, before, after):
    if text.count(before)!=1: raise ValueError('Review anchor changed: '+before[:90])
    return text.replace(before,after,1)

def between(text, a, b):
    if text.count(a)!=1 or text.count(b)!=1: raise ValueError('Production extraction anchor changed: '+a)
    return text[text.index(a):text.index(b,text.index(a))]

def plain(text): return re.sub(r'^export ', '', text, flags=re.M)

def production_adapter(baseline):
    src=(baseline/'src/app.js').read_text()
    top=between(src,'const drawings=','function shell(){')
    a,b=top.index('let storage;'),top.index('const badge=')
    top=top[:a]+"const isSaved=id=>prefs.favorites.includes('member:'+id);\n"+top[b:]
    old=next(l for l in top.splitlines() if l.startswith('const saveButton='))
    top=one(top,old,"const saveButton=id=>`<button class=\"icon-btn save-button\" data-save=\"member:${e(id)}\" aria-label=\"${e(recordById.get(id)?.title||'멤버')} ${isSaved(id)?'즐겨찾기 해제':'즐겨찾기 저장'}\" aria-pressed=\"${isSaved(id)}\">${icon('bookmark')}</button>`;")
    catalog=first.extract(src,'CATALOG')
    live=between(src,'const liveMonitor=','const CATALOG=')
    catalog_ui=between(src,'const catalogProfiles=','function catalogMusicView(params){')
    visuals=between(src,'function visualLiveThumbnail(', 'const HISTORY_TYPES=')
    visuals+=between(src,'function visualLiveArt(', 'function historyLink(')
    labels=next(l for l in src.splitlines() if l.startswith('const MUSIC_VIDEO_LABELS='))
    label_fn=next(l for l in src.splitlines() if l.startswith('function musicVideoLabel('))
    chunks=[plain((baseline/'src/lib.js').read_text()),plain((baseline/'src/data.js').read_text()),plain((baseline/'src/portraits.js').read_text()),'const e=escapeHtml;',top,plain((ROOT/'live/core.js').read_text()),live,'const CATALOG='+first.script_json(catalog)+';',plain((ROOT/'catalog/core.js').read_text()),labels,label_fn,catalog_ui,visuals]
    code='\n'.join(chunks)
    # The same approved portrait bytes are embedded for the gated single-file preview.
    code=code.replace('./assets/portraits/${m.id}.webp?v=${PORTRAITS[m.id].version}','${REVIEW_DATA.assets.portraits[m.id]}')
    return "const ProductionUI=(()=>{\n"+code+'''\nconst wrap=(page,html)=>`<div class="production-ui" data-operating-page="${page}">${html}</div>`;
return {home:()=>wrap('home-live',liveHomeView()),live:()=>wrap('live',liveView()),members:()=>wrap('members',catalogMembersView()),member:id=>wrap('member',catalogMemberView(id)),mount:liveMount};
})();\n'''

def scoped_css(text):
    """Scope original selectors, preserving declarations, media rules and theme tokens."""
    def selector(tokens):
        groups=[];part=[]
        for t in tokens:
            if t.type=='literal' and t.value==',': groups.append(tinycss2.serialize(part).strip());part=[]
            else: part.append(t)
        groups.append(tinycss2.serialize(part).strip())
        out=[]
        for s in groups:
            if s.startswith(':root'):
                s=s.replace(':root','',1)
                out.append((s+' ' if s else '')+'.production-ui')
            elif s in ('body','html'): out.append('.production-ui')
            elif s.startswith('[data-theme') or s.startswith('html[data-theme'):
                s=s.removeprefix('html'); split=s.find(']')+1
                out.append(s[:split]+' .production-ui'+s[split:])
            else: out.append('.production-ui '+s)
        return ','.join(out)
    def rules(items):
        out=[]
        for r in items:
            if r.type=='qualified-rule':out.append(selector(r.prelude)+'{'+tinycss2.serialize(r.content)+'}')
            elif r.type=='at-rule':
                start='@'+r.at_keyword+' '+tinycss2.serialize(r.prelude)
                if r.content is None:out.append(start+';')
                elif r.lower_at_keyword in ('media','supports','layer'):out.append(start+'{'+rules(tinycss2.parse_rule_list(r.content,skip_comments=True,skip_whitespace=True))+'}')
                else:out.append(start+'{'+tinycss2.serialize(r.content)+'}')
        return '\n'.join(out)
    return rules(tinycss2.parse_stylesheet(text,skip_comments=True,skip_whitespace=True))

def adapt_app(text):
    # Separate namespaces: neither preview changes production or the first review's settings.
    text=text.replace('review-1st','review-2nd').replace('review1','review2').replace('1차 검토','2차 검토')
    text=one(text,"['live','LIVE·방송','video']","['live','LIVE','video'],['content','콘텐츠','book']")
    text=one(text,"video:'live',series:'live'","video:'content',series:'content'")
    text=text.replace('#/live?tab=','#/content?tab=')
    text=one(text,"url('live',{tab})","url('content',{tab})")
    text=one(text,"['live','방송','video']","['live','LIVE','video']")
    text=one(text,'aria-label="더보기"><a href="#/members">','aria-label="더보기"><a href="#/content">콘텐츠</a><a href="#/members">')
    # Remove the discarded first-review member pages, not merely hide their tabs.
    a=text.index('function membersView()');b=text.index('function scheduleView(p)',a)
    text=text[:a]+"function membersView(){return ProductionUI.members();}\nfunction memberView(id){return ProductionUI.member(id);}\n\n"+text[b:]
    a=text.index('function liveSummaryHtml()');b=text.index('function homeView(p)',a)
    text=text[:a]+"function liveSummaryHtml(){return ProductionUI.home();}\n"+text[b:]
    a=text.index('function liveCardsHtml(');b=text.index('function liveView(p)',a)
    text=text[:a]+text[b:]
    a=text.index(" if(tab==='now')body=");b=text.index(" if(tab==='videos'",a)
    text=text[:a]+text[b:]
    text=one(text,"function liveView(p){const tab=p.get('tab')||'now';let body='';","function contentView(p){const tab=['videos','replay','series'].includes(p.get('tab'))?p.get('tab'):'videos';let body='';")
    text=one(text,"heading('지금 보고, 놓친 순간도 찾고','실제 방송 상태와 공지, 다시보기와 주요 콘텐츠를 구분해서.','LIVE & BROADCAST')+tabs([['now','방송 중'],['videos','최근 영상'],['replay','다시보기'],['series','시리즈·합방']],tab)","heading('콘텐츠','최근 영상부터 다시보기, 시리즈와 합방까지. 다시 보고 싶은 순간을 찾아보세요.','CONTENTS')+tabs([['videos','최근 영상'],['replay','다시보기'],['series','시리즈·합방']],tab)")
    text=one(text,"else if(root==='live')html=liveView(r.params);","else if(root==='live')html=ProductionUI.live();else if(root==='content')html=contentView(r.params);")
    a=text.index('function paintLive()');b=text.index('function render()',a)
    text=text[:a]+text[b:]
    text=one(text,'mountGallery();refreshLive();','mountGallery();ProductionUI.mount(root);')
    a=text.index("setInterval(()=>{if(!document.hidden){paintLive();refreshLive();}}")
    b=text.index("if(!location.hash)",a)
    text=text[:a]+text[b:]
    text=one(text," if(action==='refresh-live'){if(Date.now()-liveAttempt<10000){toast('중복 조회를 줄이기 위해 잠시 후 다시 확인해 주세요.');return;}refreshLive(true);}","")
    text=one(text,"heading('기록과 기록 사이의 이야기','일상 공지는 소식·일정에서, 주요 활동의 흐름은 이곳에서.','OUR TIMELINE')",'''`<header class="page-heading story-heading"><div><p class="eyebrow">OUR STORY <span class="story-since">SINCE 2021</span></p><h1>차곡차곡, 우리의 발자취.</h1><p>오디션의 첫 시작부터 음악과 무대, 함께 만든 순간까지.</p></div></header>`''')
    # Both calendar and agenda/list expose names and colors; no inference from titles.
    text=one(text,'<article class="row-card" data-item-key="${esc(r.key)}">','<article class="row-card" data-item-key="${esc(r.key)}" data-member-tone="${r.members?.length===1?r.members[0]:\'group\'}" data-agency="${isAgency(r)}">')
    text=one(text,"${badge(label,'neutral')}","${isAgency(r)?badge('★ 소속사 공지','agency'):badge(label,'neutral')}")
    before="rows.sort((a,b)=>a.date.localeCompare(b.date)||(a.kind==='event'?-1:1)-(b.kind==='event'?-1:1)"
    text=one(text,before,"rows.sort((a,b)=>a.date.localeCompare(b.date)||Number(isAgency(b))-Number(isAgency(a))||(a.kind==='event'?-1:1)-(b.kind==='event'?-1:1)")
    old='''<span class="day-chip ${r.kind} ${r.members.length===1?'tone-'+r.members[0]:''}">${esc(r.title.replace(/^\[[^\]]+\]\s*/,''))}</span>'''
    new='''<span class="day-chip ${r.kind}" data-member-tone="${r.members.length===1?r.members[0]:'group'}" data-agency="${isAgency(r)}" title="${esc(memberText(r.members)+' · '+r.title)}">${isAgency(r)?'★ 소속사 · ':r.members.length===1?esc(names[r.members[0]])+' · ':'이세돌 · '}${esc(r.title.replace(/^\[[^\]]+\]\s*/,''))}</span>'''
    text=one(text,old,new)
    text=one(text,'''${D.members.map(x=>`<span class="tone-${x.id}"><i class="dot"></i> ${x.name}</span>`).join('')}</div>${content}''','''${D.members.map(x=>`<span class="tone-${x.id}"><i class="dot"></i> ${x.name}</span>`).join('')}<span class="agency-label">★ 소속사 공지</span></div>${content}''')
    text=one(text,"['cafe','멤버·소속사 카페'],['fan','팬 참고']","['cafe','멤버·소속사 카페'],['agency','소속사 공지'],['fan','팬 참고']")
    text=one(text,"if(source==='fan')rows=[];","if(source==='agency')rows=rows.filter(isAgency);if(source==='fan')rows=[];")
    text="const isAgency=r=>['berriz-notice','cafe-agency','parable-web'].includes(r.sourceId);\n"+text
    a=text.index('const scopeRows=');b=text.index('function notFound()',a)
    text=text[:a]+(ROOT/'review-2nd/review-guide.js').read_text()+'\n'+text[b:]
    # Legacy incoming first-review links continue to select the right content tab.
    text=one(text,"function render(){const r=route(),root=r.parts[0];", "function render(){let r=route();if(r.parts[0]==='live'&&['videos','replay','series'].includes(r.params.get('tab'))){history.replaceState(null,'',url('content',Object.fromEntries(r.params)));r=route();}const root=r.parts[0];")
    if any(x in text for x in ('OUR TIMELINE','기록과 기록 사이의 이야기','LIVE·방송')):raise ValueError('Discarded first-review text remains')
    return text

def build(baseline, snapshot_path=None, output_path=None):
    if os.getenv('GITHUB_REF') not in (None,'refs/heads/feature/review-2nd') or os.getenv('DEPLOY_ENV')=='production':raise ValueError('Second review branch only')
    out=Path(output_path) if output_path else ROOT/'review-2nd-dist'
    if out.parent.resolve()!=ROOT or (output_path and not out.name.startswith('release-')):raise ValueError('Invalid release intermediate output')
    src=ROOT/(out.name+'-source') if output_path else ROOT/'review-1st-dist'
    first.build(baseline, snapshot_path=snapshot_path, output_path=src if output_path else None)
    if out.is_symlink():raise ValueError('Symlink output')
    if out.exists():shutil.rmtree(out)
    shutil.copytree(src,out)
    app=cleanup.app(polish.app(adapt_app((src/'app.js').read_text())))
    legacy=polish.adapter(production_adapter(baseline),(baseline/'src/app.js').read_text())
    css=polish.without_review_footer((src/'styles.css').read_text())+'\n'+scoped_css((baseline/'src/styles.css').read_text())+'\n'+(ROOT/'review-2nd/changes.css').read_text()+'\n'+(ROOT/'review-2nd/polish.css').read_text()
    (out/'app.js').write_text(app);(out/'production-ui.js').write_text(legacy);(out/'styles.css').write_text(css)
    meta=json.loads((out/'build-info.json').read_text());meta.update(review='review-2nd',branch='feature/review-2nd',firstReviewCommit=FIRST,operatingPagesCommit=PRODUCTION,accepted=['home-recent-content','music','history-layout','schedule-layout'],restored=['production-home-live','production-live-page','production-members-and-detail','member-colors','agency-notice-priority'],contentTabs=['videos','replay','series'],navigationCount=7)
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    data=first.extract((out/'data.js').read_text(),'REVIEW_DATA');copy=json.loads(json.dumps(data))
    # The standalone gated HTML is a sample, not the operating catalog.
    # Keep all records in data.js for review and production; only inline a
    # bounded multi-channel selection to respect the existing 9 MiB cap.
    by_channel={}
    for item in sorted(copy['videos'],key=lambda v:v.get('publishedAt') or v.get('date',''),reverse=True):
        key=item.get('channelKey','unknown')
        bucket=by_channel.setdefault(key,[])
        if len(bucket)<16:bucket.append(item)
    copy['videos']=[item for bucket in by_channel.values() for item in bucket]
    copy['scope']['offlineSample']=True

    inline=lambda p:'data:image/webp;base64,'+base64.b64encode((out/p.split('?')[0]).read_bytes()).decode()
    for group in copy['assets'].values():
        for k,v in group.items():group[k]=inline(v)
    for item in copy['gallery']:item['src']=inline(item['src'])
    # The standalone preview also embeds the legacy catalog. Bound its
    # duplicated per-channel video samples; the real production-ui.js and
    # published catalog are not modified.
    offline_catalog=first.extract(legacy,'CATALOG')
    for channel in offline_catalog['videos']['channels']:
        channel['videos']=channel['videos'][:3]
    legacy_pattern=r'^const CATALOG=[^\\n]+;'
    if len(re.findall(legacy_pattern,legacy,flags=re.M))!=1:
        raise ValueError('Offline catalog slot changed')
    offline_legacy=re.sub(legacy_pattern,lambda _: 'const CATALOG='+first.script_json(offline_catalog)+';',legacy,count=1,flags=re.M)
    code='const REVIEW_DATA='+first.script_json(copy)+';\n'+(out/'core.js').read_text()+'\n'+(out/'live-core.js').read_text()+'\n'+offline_legacy+'\n'+app
    sha=lambda s:"'sha256-"+base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()+"'"
    index=(src/'index.html').read_text().replace('1차 검토','2차 검토').replace('review-1st','review-2nd')
    index=index.replace('<script src="app.js"></script>','<script src="production-ui.js"></script><script src="app.js"></script>')
    # Production LIVE thumbnails need their original permitted image host.
    index=index.replace('https://i.ytimg.com;', 'https://i.ytimg.com https://liveimg.sooplive.com;')
    (out/'index.html').write_text(index)
    html=index.replace("script-src 'self'","script-src "+sha(code)).replace("style-src 'self'","style-src "+sha(css))
    html=re.sub(r'<link rel="icon"[^>]+>','',html).replace('<link rel="stylesheet" href="styles.css">','<style>'+css+'</style>')
    html=re.sub(r'<script src="(?:data|core|live-core|production-ui|app)\.js"></script>','',html)
    html=html.replace('</body>','<script>'+code+'</script></body>');(out/'review.html').write_text(html)
    if len(html.encode())>=9*1024*1024:raise ValueError('Gated preview exceeds allowed size')
    print(json.dumps({'review':'review-2nd','htmlBytes':len(html.encode()),'counts':meta['counts'],'productionUIReused':True},ensure_ascii=False))
    return meta

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--baseline',required=True);parser.add_argument('--snapshot');parser.add_argument('--output');args=parser.parse_args();build(Path(args.baseline).resolve(), snapshot_path=args.snapshot, output_path=args.output)
