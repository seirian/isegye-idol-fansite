#!/usr/bin/env python3
"""Build an offline, hash-CSP, three-game preview; no production artifacts written."""
from pathlib import Path
from datetime import datetime, timezone
import base64, hashlib, json, os, re
ROOT=Path(__file__).resolve().parents[1]
BRANCH='feature/playground-games'
BASE='37fcb9490e40a337a473881d0dc24e7401956d59'
def sha(raw):return hashlib.sha256(raw).hexdigest()
def catalog():
    music=json.loads((ROOT/'catalog/music.json').read_text())
    mapping=json.loads((ROOT/'catalog/video-sources.json').read_text())
    selections={}
    for line in (ROOT/'catalog/video-sources.tsv').read_text().splitlines():
        if line and not line.startswith('#'):
            sid,vid,kind,channel=line.split('\t');selections[sid]=(vid,kind,channel)
    songs=[]
    def add(s,vid,kind,channel,checked):
        if kind not in ('official_mv','official_video','official_audio') or mapping['channels'].get(channel,{}).get('role')!='official':return
        if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise ValueError('Video ID')
        if not re.fullmatch(r'[a-z0-9-]{1,80}',s['id']) or not 1<=len(s['title'])<=140:raise ValueError('Song identity')
        if not s['members'] or any(x not in ('ine','jingburger','lilpa','jururu','gosegu','viichan') for x in s['members']):raise ValueError('Member identity')
        if any(r['id']==s['id'] for r in songs):return
        songs.append({'id':s['id'],'title':s['title'],'members':s['members'],'album':s.get('album',''),'aliases':s.get('aliases',[]),'url':'https://www.youtube.com/watch?v='+vid,'checkedAt':checked})
    for s in music['songs']:
        if s['id'] in selections:add(s,*selections[s['id']],mapping['checkedAt'])
    releases=json.loads((ROOT/'catalog/album-releases.json').read_text())['releases']
    for a in releases:
        for t in a['tracks']:add(dict(t,members=a['members'],album=a['title']),t['videoId'],t['kind'],t['channelKey'],a['checkedAt'])
    if len(songs)<8:raise ValueError('Insufficient verified official selections')
    return {'schemaVersion':1,'checkedAt':music['checkedAt'],'note':'기존 공식 원본 매핑의 최소 메타데이터. 원본 전체 재생이나 이용허락의 확인을 뜻하지 않습니다. 각 곡의 원 자료 확인일을 별도로 보존합니다.','songs':songs}
def build():
    if os.getenv('DEPLOY_ENV')=='production' or os.getenv('GITHUB_REF') in ('refs/heads/main','refs/heads/develop'):raise ValueError('Isolated preview only')
    src=ROOT/'playground-games';data=catalog();core=(src/'core.js').read_text()
    names=re.findall(r'^export (?:const|function) (\w+)',core,re.M)
    core=re.sub(r'^export ','',core,flags=re.M)
    serial=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    js='const ARCADE_DATA='+serial+';\nconst ARCADE_CORE=(()=>{\n'+core+'\nreturn {'+','.join(names)+'};\n})();\n'+(src/'app.js').read_text()
    css=(src/'styles.css').read_text()+'\n'+(ROOT/'review-2nd/polish.css').read_text()
    if '</script' in js.lower() or '</style' in css.lower():raise ValueError('Closing tag')
    h64=lambda s:base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
    csp="default-src 'none'; script-src 'sha256-"+h64(js)+"'; style-src 'sha256-"+h64(css)+"'; img-src 'none'; connect-src 'none'; media-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'"
    html=(src/'index.html').read_text().replace('<!--CSP-->','<meta http-equiv="Content-Security-Policy" content="'+csp+'">').replace('<!--STYLE-->','<style>'+css+'</style>').replace('<!--SCRIPT-->','<script>'+js+'</script>')
    out=ROOT/'playground-games-dist'
    if out.is_symlink():raise ValueError('Symlink output')
    out.mkdir(exist_ok=True);raw=html.encode()
    for n in ('index.html','review.html'):(out/n).write_bytes(raw)
    files=['playground-games/core.js','playground-games/app.js','playground-games/styles.css','playground-games/index.html','catalog/music.json','catalog/video-sources.json','catalog/video-sources.tsv','catalog/album-releases.json','review-2nd/polish.css']
    meta={'review':'playground-games','branch':BRANCH,'baseCommit':BASE,'commit':os.getenv('GITHUB_SHA','local'),'builtAt':datetime.now(timezone.utc).isoformat(),'mode':'playground-games-preview','counts':{'games':3,'songs':len(data['songs'])},'htmlSha256':sha(raw),'htmlBytes':len(raw),'productionWrites':False,'liveFeedsConnected':False,'externalMediaUsed':False,'storageKey':'isegye:review:playground-games:v1','sourceHashes':{f:sha((ROOT/f).read_bytes()) for f in files}}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    (out/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(meta,ensure_ascii=False));return meta
if __name__=='__main__':build()
