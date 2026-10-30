"""Compose calendar-first view into the approved home bundle."""
from pathlib import Path
import json,re
import schedule_feed
ROOT=Path(__file__).resolve().parents[1]
def compose(app,css,out,meta):
    snapshot=schedule_feed.validate(json.loads((ROOT/'schedule/snapshot.json').read_text()))
    a=app.index('function scheduleView(params){');b=app.index('function guideView()',a)
    app=app[:a]+'function scheduleView(params){return scheduleFeedView(params);}\n'+app[b:]
    core=re.sub(r'^export ', '', (ROOT/'schedule/core.js').read_text(),flags=re.M)
    js=core+'\nconst SCHEDULE_SEED='+json.dumps(snapshot,ensure_ascii=False).replace('<','\\u003c')+';\n'+(ROOT/'schedule/ui.js').read_text()
    if app.count('shell();render();')!=1:raise ValueError('Schedule insertion anchor changed')
    app=app.replace('shell();render();',js+'\nshell();render();')
    css+='\n'+(ROOT/'schedule/theme.css').read_text()
    (out/'src/schedule.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    meta['scheduleFeed']={'schemaVersion':1,'calendarFirst':True,'officialAnnouncementBlock':False,'events':len(snapshot['events']),'news':len(snapshot['news']),'fanReferences':len(snapshot['forecasts']),'generatedAt':snapshot['generatedAt'],'cafeCrawling':False}
    return app,css
