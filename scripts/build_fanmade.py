#!/usr/bin/env python3
"""Build the isolated Fanmade review. No network, production writes or real works."""
from pathlib import Path
from datetime import datetime,timezone
import base64,hashlib,json,os,re
ROOT=Path(__file__).resolve().parents[1]
BASE='7542c84466d87632d45baa5251a8e74781c58259'
BRANCH='feature/fanmade'

def validate(data):
    if data.get('schemaVersion')!=1 or data.get('sampleOnly') is not True:raise ValueError('This review accepts explicit demo data only')
    seen=set()
    for group in ('works','creators','exhibitions'):
        if not isinstance(data.get(group),list) or not 1<=len(data[group])<=100:raise ValueError('Invalid catalog collection')
        for row in data[group]:
            ident=row.get('id','')
            if not re.fullmatch('[a-z0-9-]{1,64}',ident) or ident in seen:raise ValueError('Invalid/duplicate identifier')
            seen.add(ident)
    creators={c['id'] for c in data['creators']};exhibitions={x['id'] for x in data['exhibitions']}
    for c in data['creators']:
        if not c.get('name','').startswith('예시 창작자 ') or c.get('originalUrl') is not None:raise ValueError('Not a synthetic creator')
    for x in data['exhibitions']:
        if x.get('sample') is not True:raise ValueError('Unlabelled exhibition')
    for w in data['works']:
        if w.get('sample') is not True or w.get('originalUrl') is not None or w.get('publishedAt') is not None or w.get('permission')!={'status':'demo'}:raise ValueError('Unapproved real work in demo')
        if w.get('creatorId') not in creators or not set(w.get('exhibitions',[]))<=exhibitions:raise ValueError('Broken relationship')
        if w.get('kind') not in ('art','video','craft') or w.get('ratio') not in ('portrait','landscape','square'):raise ValueError('Invalid presentation')
        if type(w.get('tone')) is not int or not 0<=w['tone']<=3:raise ValueError('Invalid tone')
        if not isinstance(w.get('frames'),list) or not 1<=len(w['frames'])<=8:raise ValueError('Invalid gallery')
        if not w.get('members') or not set(w['members'])<={'group','ine','jingburger','lilpa','jururu','gosegu','viichan'}:raise ValueError('Invalid member')
        for key in ('title','story','medium'):
            if not isinstance(w.get(key),str) or not 1<=len(w[key])<=1200:raise ValueError('Invalid text')
    return data

def build():
    if os.getenv('DEPLOY_ENV')=='production' or os.getenv('GITHUB_REF') in ('refs/heads/main','refs/heads/develop'):raise ValueError('Preview branch/local build only')
    src=ROOT/'fanmade';data=validate(json.loads((src/'catalog.json').read_text()))
    serial=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    core=re.sub(r'^export ','',(src/'core.js').read_text(),flags=re.M)
    js='const FANMADE_DATA='+serial+';\n'+core+'\n'+(src/'app.js').read_text();css=(src/'styles.css').read_text()
    if '</script' in js.lower() or '</style' in css.lower():raise ValueError('Unsafe inline closing tag')
    h64=lambda x:base64.b64encode(hashlib.sha256(x.encode()).digest()).decode()
    csp="default-src 'none'; script-src 'sha256-"+h64(js)+"'; style-src 'sha256-"+h64(css)+"'; img-src 'none'; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'"
    html=(src/'index.html').read_text().replace('<!--CSP-->','<meta http-equiv="Content-Security-Policy" content="'+csp+'">').replace('<!--STYLE-->','<style>'+css+'</style>').replace('<!--SCRIPT-->','<script>'+js+'</script>')
    out=ROOT/'fanmade-dist'
    if out.is_symlink():raise ValueError('Symlink output refused')
    out.mkdir(exist_ok=True);raw=html.encode()
    for name in ('review.html','index.html'):(out/name).write_bytes(raw)
    meta={'review':'fanmade','branch':BRANCH,'baseCommit':BASE,'commit':os.getenv('GITHUB_SHA','local'),'builtAt':datetime.now(timezone.utc).isoformat(),'mode':'fanmade-preview','counts':{k:len(data[k]) for k in ('works','creators','exhibitions')},'htmlSha256':hashlib.sha256(raw).hexdigest(),'htmlBytes':len(raw),'productionWrites':False,'liveFeedsConnected':False,'sampleOnly':True}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n');print(json.dumps(meta,ensure_ascii=False))
if __name__=='__main__':build()
