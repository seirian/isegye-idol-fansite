#!/usr/bin/env python3
"""Package a self-contained, hash-CSP preview. Never touches operating artifacts."""
from pathlib import Path
from datetime import datetime,timezone,date
import base64,hashlib,json,os,re
from urllib.parse import urlparse
ROOT=Path(__file__).resolve().parents[1]
BRANCH='feature/playground'
BASE='7542c84466d87632d45baa5251a8e74781c58259'
def validate(d):
    if d.get('schemaVersion')!=1 or not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.\d+',d.get('version','')):raise ValueError('Schema/version')
    if not 10<=len(d['questions'])<=1000 or not 3<=len(d['tracks'])<=100:raise ValueError('Catalog bounds')
    sources=d['sources'];ids=[]
    for key,s in sources.items():
        u=urlparse(s['url'])
        if u.scheme!='https' or u.username or u.password or not u.hostname:raise ValueError('Unsafe source URL')
        date.fromisoformat(s['checkedAt'])
    for q in d['questions']:
        if not re.fullmatch('[a-z0-9-]{1,60}',q['id']) or q['id'] in ids:raise ValueError('Question id')
        ids.append(q['id'])
        if q['category'] not in d['categories'] or q['status'] not in ('reviewed','community'):raise ValueError('Category/status')
        if len(q['choices'])!=4 or len(set(q['choices']))!=4 or type(q['answer']) is not int or not 0<=q['answer']<4:raise ValueError('Answer choices')
        if not q['sources'] or any(i not in sources or sources[i]['kind']=='context' for i in q['sources']):raise ValueError('Missing answer evidence')
        for text in [q['stem'],q['hint'],q['explanation'],*q['choices']]:
            if not isinstance(text,str) or not 1<=len(text)<=800 or '<' in text:raise ValueError('Question text')
        for r in q['inspiration']:
            if r['source'] not in sources or not r['items'] or any(type(i)is not int or i<1 or i>60 for i in r['items']):raise ValueError('Reference mapping')
        if q['related'] and not re.fullmatch(r'/#/(?:song/[a-z0-9-]+|member/[a-z0-9-]+|history|content|members|music)',q['related']):raise ValueError('Unsafe internal link')
    if len({t['id'] for t in d['tracks']})!=len(d['tracks']):raise ValueError('Duplicate track')
    for t in d['tracks']:
        date.fromisoformat(t['date'])
        if t['dateKind']!='최초 국내 음원 발매일' or not t['sources'] or any(s not in sources for s in t['sources']):raise ValueError('Release date evidence')
    return d

def build():
    if os.getenv('DEPLOY_ENV')=='production' or os.getenv('GITHUB_REF') in ('refs/heads/main','refs/heads/develop'):raise ValueError('Preview branch/local only')
    src=ROOT/'playground';d=validate(json.loads((src/'catalog.json').read_text()))
    serial=json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    core=re.sub(r'^export ','',(src/'core.js').read_text(),flags=re.M)
    app=(src/'app.js').read_text().replace('<!--PREVIEW-QUIZ-OPTIONS-->',(src/'preview-quiz-options.html').read_text().rstrip('\n'))
    js='const PLAYGROUND_DATA='+serial+';\n'+core+'\n'+app;css=(src/'styles.css').read_text()
    if '</script' in js.lower() or '</style' in css.lower():raise ValueError('Unsafe closing tag')
    h64=lambda x:base64.b64encode(hashlib.sha256(x.encode()).digest()).decode()
    csp="default-src 'none'; script-src 'sha256-"+h64(js)+"'; style-src 'sha256-"+h64(css)+"'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'"
    html=(src/'index.html').read_text().replace('<!--CSP-->','<meta http-equiv="Content-Security-Policy" content="'+csp+'">').replace('<!--STYLE-->','<style>'+css+'</style>').replace('<!--SCRIPT-->','<script>'+js+'</script>')
    out=ROOT/'playground-dist'
    if out.is_symlink():raise ValueError('Symlink output')
    out.mkdir(exist_ok=True);raw=html.encode()
    for n in ('review.html','index.html'):(out/n).write_bytes(raw)
    meta={'review':'playground','branch':BRANCH,'baseCommit':BASE,'commit':os.getenv('GITHUB_SHA','local'),'builtAt':datetime.now(timezone.utc).isoformat(),'mode':'playground-preview','questionVersion':d['version'],'counts':{'questions':len(d['questions']),'tracks':len(d['tracks']),'sources':len(d['sources'])},'htmlSha256':hashlib.sha256(raw).hexdigest(),'htmlBytes':len(raw),'productionWrites':False,'liveFeedsConnected':False,'sampleOnly':False,'realQuestionBank':True}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n');print(json.dumps(meta,ensure_ascii=False))
if __name__=='__main__':build()
