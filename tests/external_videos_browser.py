"""Read-only browser checks of the exact composed operating bundle."""
from pathlib import Path
from collections import Counter
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlsplit
import json, os, threading
from playwright.sync_api import sync_playwright, expect
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'test-results/external-videos';OUT.mkdir(parents=True,exist_ok=True)
class Handler(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(ROOT/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
url=f'http://127.0.0.1:{server.server_port}/';checks=[]
def check(name,value,**details):
    checks.append({'name':name,'passed':bool(value),**details})
    if not value:raise AssertionError(name+(' '+json.dumps(details,ensure_ascii=False) if details else ''))
def video_count(name,keys,video_id,expected=1):
    actual=keys.count('video:'+video_id)
    check(name,actual==expected,videoId=video_id,expected=expected,actual=actual)
try:
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.getenv('BROWSER_PATH') or None)
        ctx=browser.new_context(viewport={'width':1440,'height':1000});page=ctx.new_page();errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        ctx.route('**/*',lambda r:r.continue_() if r.request.url.startswith(url) else r.abort())
        for endpoint in ('schedule','music','history','albums'):
            ctx.route('**/api/'+endpoint,lambda r:r.fulfill(status=503,content_type='application/json',body='{}'))
        def go(route):
            page.goto(url+'#/'+route,wait_until='domcontentloaded');expect(page.locator('#main h1')).to_be_visible()
            page.evaluate('render()')
        def music_results(label):
            # The contract is about the complete search result, not which page a
            # growing, newest-first catalog puts an approved performance on.
            # Stay in this document so the isolated regression fixture survives
            # even when the preceding check happened to finish on page one.
            page.evaluate("() => {location.hash='#/music?tab=videos&q=REBELS';render();}")
            expect(page.locator('#main h1')).to_be_visible()
            expected=page.evaluate("""() => filtered(
                D.videos.filter(v=>v.category==='group'||v.type==='external_performance'),
                new URLSearchParams('tab=videos&q=REBELS')).map(v=>v.key)""")
            total=int(page.locator('#main .result-bar strong').inner_text())
            keys=[];pages=[];visited=set();number=1
            while True:
                current=urlsplit(page.url).fragment
                check(label+' pagination advances without cycles',current not in visited and number<=max(1,total),page=number)
                visited.add(current)
                cards=page.locator('#main .grid > [data-item-key^="video:"]').evaluate_all('(cards)=>cards.map(card=>card.dataset.itemKey)')
                pages.append(cards);keys.extend(cards)
                next_link=page.locator('#main .pagination').get_by_role('link',name='다음',exact=True)
                if next_link.count()==0:break
                check(label+' one next-page link',next_link.count()==1,actual=next_link.count())
                href=next_link.get_attribute('href')
                target=urlsplit(href)
                route,_,query=target.fragment.partition('?')
                check(label+' next page preserves the search',not target.scheme and not target.netloc and not target.path and
                      route=='/music' and parse_qs(query)=={'tab':['videos'],'q':['REBELS'],'page':[str(number+1)]},href=href)
                next_link.click()
                expect(page).to_have_url(url+href)
                page.wait_for_function('hash => renderedHash === hash && location.hash === hash',arg=href)
                number+=1
            check(label+' all reported results rendered',len(keys)==total,expected=total,actual=len(keys),pages=len(pages))
            check(label+' complete DOM agrees with music eligibility',Counter(keys)==Counter(expected),
                  missing=list((Counter(expected)-Counter(keys)).elements())[:10],
                  extra=list((Counter(keys)-Counter(expected)).elements())[:10])
            for video_id,name in [('mkJRSPYjX8k','M2 relay'),('sy40EGkSfRA','Music Core stage'),('Mj7q8HU8ZXg','full performance')]:
                video_count(label+' '+name+' exactly once in search data',expected,video_id)
                video_count(label+' '+name+' exactly once across pages',keys,video_id)
            video_count(label+' teaser excluded from search data',expected,'_E9ZHH9R7o4',0)
            video_count(label+' teaser excluded from every music page',keys,'_E9ZHH9R7o4',0)
            return pages
        go('content?tab=videos&category=external')
        selected=page.evaluate("() => D.videos.filter(v=>['_E9ZHH9R7o4','Mj7q8HU8ZXg','sy40EGkSfRA','mkJRSPYjX8k'].includes(v.id)).map(v=>({id:v.id,type:v.type,category:v.category,channelKey:v.channelKey,channelName:v.channelName,relatedSong:v.relatedSong}))")
        for video_id,kind,channel_key,channel_name in [
            ('_E9ZHH9R7o4','external_teaser','studio-choom-selected','STUDIO CHOOM [스튜디오 춤]'),
            ('Mj7q8HU8ZXg','external_performance','studio-choom-selected','STUDIO CHOOM [스튜디오 춤]'),
            ('sy40EGkSfRA','external_performance','mbc-music-core-selected','MBCkpop'),
            ('mkJRSPYjX8k','external_performance','m2-relay-selected','M2'),
        ]:
            rows=[v for v in selected if v['id']==video_id]
            check(video_id+' exactly once in complete catalog',len(rows)==1,expected=1,actual=len(rows))
            expected={'id':video_id,'type':kind,'category':'external','channelKey':channel_key,'channelName':channel_name,'relatedSong':'rebels'}
            check(video_id+' retains its source and classification',rows[0]==expected,expected=expected,actual=rows[0])
        check('five selected external videos',page.locator('[data-item-key^="video:"]').count()==5)
        for video_id in ('Mj7q8HU8ZXg','_E9ZHH9R7o4'):
            check(video_id+' in external contents exactly once',page.locator(f'#main .grid > [data-item-key="video:{video_id}"]').count()==1)
        check('source-labelled cards',page.locator('#main').inner_text().count('외부 채널 · STUDIO CHOOM')==2)
        check('newest collaboration first',page.locator('[data-item-key^="video:"]').first.get_attribute('data-item-key')=='video:P15VglxEkss')
        check('MBC source-labelled card',page.locator('#main').inner_text().count('외부 채널 · MBCkpop')==1)
        check('M2 source-labelled card',page.locator('#main').inner_text().count('외부 채널 · M2')==1)
        check('superseded upload absent',page.evaluate("!D.videos.some(v=>v.id==='z8AJgnTC52k')"))
        check('channel filter option',page.locator('option[value="studio-choom-selected"]').count()==1)
        go('content?tab=videos&channel=studio-choom-selected&q=레블스')
        check('channel and alias search',page.locator('[data-item-key^="video:"]').count()==2)
        go('content?tab=videos&channel=mbc-music-core-selected&q=음악중심')
        check('MBC channel and program search',page.locator('[data-item-key^="video:"]').count()==1)
        check('MBC exact selected ID',page.locator('[data-item-key^="video:"]').first.get_attribute('data-item-key')=='video:sy40EGkSfRA')
        go('content?tab=videos&channel=m2-relay-selected&q=릴레이댄스')
        check('M2 channel and title search',page.locator('[data-item-key^="video:"]').count()==1)
        check('M2 exact selected ID',page.locator('[data-item-key^="video:"]').first.get_attribute('data-item-key')=='video:mkJRSPYjX8k')
        go('content?tab=videos&category=group&q=릴레이댄스')
        check('M2 not a group-owned upload',page.locator('[data-item-key="video:mkJRSPYjX8k"]').count()==0)
        go('content?tab=videos&category=group&q=MBCkpop')
        check('MBC not a group-owned upload',page.locator('[data-item-key^="video:"]').count()==0)
        go('content?tab=videos&category=group&q=STUDIO%20CHOOM')
        check('not mislabelled group-owned',page.locator('[data-item-key^="video:"]').count()==0)
        go('content?tab=videos&category=external&channel=irise-collab-selected&members=lilpa&q=아이리제')
        check('IRISE channel and Lilpa filter',page.locator('[data-item-key="video:P15VglxEkss"]').count()==1)
        check('IRISE source-labelled card','외부 채널 · IRISÉ' in page.locator('#main').inner_text())
        for member in ('ine','jingburger','jururu','gosegu','viichan'):
            go('content?tab=videos&category=external&members='+member+'&q=아이리제')
            check('collaboration not attributed to '+member,page.locator('[data-item-key="video:P15VglxEkss"]').count()==0)
        go('content?tab=videos&category=external&members=lilpa,gosegu&match=all&q=아이리제')
        check('collaboration cannot match all group members',page.locator('[data-item-key="video:P15VglxEkss"]').count()==0)
        for category in ('group','member'):
            go('content?tab=videos&category='+category+'&q=아이리제')
            check('IRISE not '+category+' owned',page.locator('[data-item-key="video:P15VglxEkss"]').count()==0)
        go('music?tab=videos&q=아이리제')
        check('collaboration not in music performance videos',page.locator('[data-item-key="video:P15VglxEkss"]').count()==0)
        music_results('current catalog')
        # Add only in-memory, newer group uploads. Keep the selected source rows
        # untouched and restore the original array before any following checks.
        original_video_count=page.evaluate('D.videos.length')
        page.evaluate("""() => {
            const original=D.videos, template=original.find(v=>v.category==='group');
            if(!template)throw new Error('Missing official group fixture template');
            const newer=Array.from({length:24},(_,i)=>{
                const id='pageguard'+String(i).padStart(2,'0');
                if(original.some(v=>v.id===id))throw new Error('Pagination fixture ID collision');
                return {...template,id,key:'video:'+id,title:'REBELS pagination regression '+i,
                    date:'2099-01-01',publishedAt:'2099-01-01T00:00:00Z'};
            });
            window.restoreExternalVideoPaginationFixture=()=>{
                D.videos=original;
                delete window.restoreExternalVideoPaginationFixture;
                render();
            };
            D.videos=[...original,...newer];
        }""")
        try:
            pages=music_results('catalog with 24 newer matches')
            check('all 24 added matches participate in the regression',sum(key.startswith('video:pageguard') for cards in pages for key in cards)==24)
            check('pagination regression actually crosses the first 24 cards',len(pages)>1 and len(pages[0])==24 and 'video:Mj7q8HU8ZXg' not in pages[0],pages=len(pages))
        finally:
            page.evaluate('restoreExternalVideoPaginationFixture()')
        check('pagination fixture restores the original catalog',page.evaluate('D.videos.length')==original_video_count)
        go('song/rebels')
        related=page.locator('section[aria-label="관련 퍼포먼스 영상"]')
        expect(related).to_be_visible()
        check('both attached to existing song exactly once',related.locator('a[href="#/video/Mj7q8HU8ZXg"]').count()==1 and related.locator('a[href="#/video/_E9ZHH9R7o4"]').count()==1)
        check('M2 linked to existing song',related.locator('a[href="#/video/mkJRSPYjX8k"]').count()>0)
        check('M2 publisher labelled','M2' in related.locator('.ai-muted').inner_text())
        check('MBC linked to existing song',related.locator('a[href="#/video/sy40EGkSfRA"]').count()>0)
        check('related section labels both publishers','MBCkpop' in related.locator('.ai-muted').inner_text() and 'STUDIO CHOOM' in related.locator('.ai-muted').inner_text())
        check('newest full performance first in related list',related.locator('a[href^="#/video/"]').first.get_attribute('href')=='#/video/mkJRSPYjX8k')
        check('collaboration not linked as REBELS performance',related.locator('a[href="#/video/P15VglxEkss"]').count()==0)
        check('official MV stays primary',page.locator('.ai-platform-link[href="https://www.youtube.com/watch?v=y-klhPVFblg"]').count()==1)
        check('no extra songs or album tracks',page.evaluate("D.songs.filter(s=>s.id==='rebels').length===1 && !D.songs.some(s=>['_E9ZHH9R7o4','Mj7q8HU8ZXg','sy40EGkSfRA','mkJRSPYjX8k'].includes(s.videoId)) && D.albums.find(a=>a.title==='Across Dimensions').songIds.length===5"))
        for vid,duration in [('_E9ZHH9R7o4','0:31'),('Mj7q8HU8ZXg','3:12'),('sy40EGkSfRA','3:08'),('mkJRSPYjX8k','3:18')]:
            go('video/'+vid)
            check(vid+' direct original',page.locator('a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v='+vid)
            check(vid+' duration',duration in page.locator('.detail-meta').inner_text())
            check(vid+' source identification',('M2' if vid=='mkJRSPYjX8k' else 'MBCkpop' if vid=='sy40EGkSfRA' else 'STUDIO CHOOM') in page.locator('#main .badges').first.inner_text())
            if vid=='mkJRSPYjX8k':
                check('M2 title and relay format',page.locator('#main h1').inner_text()=='[릴레이댄스] 이세계아이돌(ISEGYE IDOL) - REBELS (4K)' and page.evaluate("D.videos.find(v=>v.id==='mkJRSPYjX8k').format==='4K 릴레이댄스'"))
                check('M2 publication date visible','2026.11.16' in page.locator('.detail-meta').inner_text().replace(' ',''))
                check('M2 quality is source-title based','원본 제목의 표기 기준' in page.locator('#main').inner_text())
            if vid=='sy40EGkSfRA':
                check('MBC stage is not falsely 4K','4K' not in page.locator('#main h1').inner_text() and page.evaluate("D.videos.find(v=>v.id==='sy40EGkSfRA').format==='음악방송 무대'"))
                check('Japan viewing restriction is visible','일본 지역에서 시청이 제한' in page.locator('#main').inner_text())
                check('MBC publication date visible','2026.11.14' in page.locator('.detail-meta').inner_text().replace(' ',''))
            check(vid+' existing song link',page.locator('a[href="#/song/rebels"]').count()>0)
            check(vid+' paired video link',page.locator('section[aria-label="관련 퍼포먼스 영상"] a[href^="#/video/"]').count()>0)
            if vid in ('_E9ZHH9R7o4','Mj7q8HU8ZXg'):
                paired='Mj7q8HU8ZXg' if vid=='_E9ZHH9R7o4' else '_E9ZHH9R7o4'
                related=page.locator('section[aria-label="관련 퍼포먼스 영상"]')
                check(vid+' links to the exact STUDIO CHOOM counterpart',related.locator(f'a[href="#/video/{paired}"]').count()==1)
                check(vid+' excludes itself from related performances',related.locator(f'a[href="#/video/{vid}"]').count()==0)
        go('video/P15VglxEkss')
        check('IRISE exact title',page.locator('#main h1').inner_text()=='[IRISÉ LIVE] 오늘은 릴파 선배님과 함께! 🩵💙')
        check('collaboration replay badge','합방 다시보기' in page.locator('#main .badges').first.inner_text())
        check('collaboration original link',page.locator('a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v=P15VglxEkss')
        check('collaboration hour duration','1:35:31' in page.locator('.detail-meta').inner_text())
        check('collaboration only Lilpa credited',page.evaluate("JSON.stringify(videos.get('P15VglxEkss').members)==='[\"lilpa\"]'"))
        check('actual start and publication distinct','18:04:24' in page.locator('.detail-copy').inner_text() and '19:45:19' in page.locator('.detail-copy').inner_text())
        check('RU restriction visible','러시아' in page.locator('.detail-copy').inner_text())
        check('collaboration not falsely related to music',page.locator('section[aria-label="관련 퍼포먼스 영상"]').count()==0 and page.locator('a[href="#/song/rebels"]').count()==0)
        check('no undefined song recommendations',page.evaluate("externalPerformanceLinks(undefined)===''"))
        feed={'schemaVersion':1,'feed':'daily-music','generatedAt':datetime.now(timezone.utc).isoformat(),'rows':[]}
        page.evaluate('(f)=>ProductionFeeds.applyMusic(f)',feed)
        check('daily refresh preserves all four',page.evaluate("D.videos.filter(v=>['_E9ZHH9R7o4','Mj7q8HU8ZXg','sy40EGkSfRA','mkJRSPYjX8k'].includes(v.id)).length===4"))
        check('daily refresh preserves selected collaboration exactly once',page.evaluate("D.videos.filter(v=>v.id==='P15VglxEkss'&&v.type==='external_collaboration').length===1 && videos.get('P15VglxEkss').members.length===1"))
        check('daily refresh preserves original MV',page.evaluate("songs.get('rebels').videoId==='y-klhPVFblg'"))
        for width in (320,390,1440):
            page.set_viewport_size({'width':width,'height':1000})
            for route in ('content?tab=videos&category=external','video/Mj7q8HU8ZXg','video/sy40EGkSfRA','video/mkJRSPYjX8k','video/P15VglxEkss','song/rebels'):
                go(route)
                check(str(width)+' no overflow '+route,page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
            if width in (390,1440):
                page.locator('section[aria-label="관련 퍼포먼스 영상"]').screenshot(path=str(OUT/f'related-{width}.png'))
                go('video/P15VglxEkss')
                page.screenshot(path=str(OUT/f'irise-lilpa-{width}.png'),full_page=True)
        check('full catalog retained',page.evaluate('D.videos.length')>26000)
        check('no Javascript errors',not errors)
        browser.close()
finally:
    server.shutdown()
    (OUT/'report.json').write_text(json.dumps({'checks':checks},ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'passed':len(checks)}))
