"""Compose calendar-first schedules plus separately labeled notice publication history."""
from pathlib import Path
from datetime import datetime
import json,re
import schedule_feed,notice_policy
ROOT=Path(__file__).resolve().parents[1]

def history_bundle():
    data=notice_policy.archive()
    coverage=json.loads((ROOT/'schedule/notice-history-coverage.json').read_text())
    rows=[];events=[]
    for r in data['notices']:
        rows.append([r['articleId'],r['menuId'],r['author'],r['members'],r['title'],r['publishedAt'],r['titleGeneralized']])
        event=schedule_feed.event_from_title(r['title'],r['publishedAt'],True)
        if event and not r['titleGeneralized']:
            events.append([r['articleId'],event['date'],event['time'],event['type'],event['certainty'],event['status'],event['detail']])
    dates=[datetime.fromisoformat(r['publishedAt']).astimezone(notice_policy.KST).date().isoformat() for r in data['notices']]
    return {'checkedAt':data['checkedAt'],'start':min(dates) if dates else data['rangeStart'],
            'end':max(dates) if dates else data['rangeEnd'],'requestedEnd':data['rangeEnd'],
            'completePublicListings':coverage.get('complete') is True,
            'bodiesReviewed':False,'rows':rows,'events':events}

def compose(app,css,out,meta):
    snapshot=schedule_feed.validate(notice_policy.clean_snapshot(json.loads((ROOT/'schedule/snapshot.json').read_text())))
    history=history_bundle()
    a=app.index('function scheduleView(params){');b=app.index('function guideView()',a)
    app=app[:a]+'function scheduleView(params){return scheduleFeedView(params);}\n'+app[b:]
    core=re.sub(r'^export ', '', (ROOT/'schedule/core.js').read_text(),flags=re.M)
    serial=lambda v:json.dumps(v,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
    js=core+'\nconst SCHEDULE_SEED='+serial(snapshot)+';\nconst NOTICE_ARCHIVE='+serial(history)+';\n'+(ROOT/'schedule/ui.js').read_text()
    if app.count('shell();render();')!=1:raise ValueError('Schedule insertion anchor changed')
    app=app.replace('shell();render();',js+'\nshell();render();')
    before="window.addEventListener('hashchange',()=>{closeMenu();if(location.hash==='#main'){document.getElementById('main').focus();return;}render({focus:true});});"
    after="window.addEventListener('hashchange',event=>{closeMenu();if(location.hash==='#main'){document.getElementById('main').focus();return;}if(scheduleRouteChanged(event))return;render({focus:true});});"
    if app.count(before)!=1:raise ValueError('Schedule route anchor changed')
    app=app.replace(before,after,1)
    css+='\n'+(ROOT/'schedule/theme.css').read_text()+'\n'+(ROOT/'schedule/accessibility.css').read_text()
    (out/'src/schedule.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    meta['scheduleFeed']={'schemaVersion':1,'calendarFirst':True,'officialAnnouncementBlock':False,
        'events':len(snapshot['events']),'news':len(snapshot['news']),'fanReferences':len(snapshot['forecasts']),
        'generatedAt':snapshot['generatedAt'],'cafeCrawling':False,'unverifiedSearchPublished':False,
        'publicationPolicy':'approved-authors-only-v1','noticeHistory':{'count':len(history['rows']),
        'titleDatedEvents':len(history['events']),'start':history['start'],'end':history['end'],
        'completePublicListings':history['completePublicListings'],'bodiesReviewed':False},
        'calendarUX':{'dateSelectionPreservesViewport':True,'sameSourceSameDayMerged':True,
        'breaksIncludedInNotices':True,'recentNewsPanel':False,'selectedDayBelow':True,
        'visibleItemsPerDay':4,'memberColors':True,'berrizAgencyPriority':True},
        'berriz':{'noticeCount':sum(x['sourceId']=='berriz-notice' for x in snapshot['news']),
                  'calendarCount':sum(x['sourceId']=='berriz-calendar' for x in snapshot['events']),
                  'publicOnly':True,'fanBoardsCollected':False}}
    return app,css
