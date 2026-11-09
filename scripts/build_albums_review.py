#!/usr/bin/env python3
"""Compile only albums-dist from the approved application; never modify production."""
from pathlib import Path
from datetime import datetime, timezone
import base64, hashlib, json, os, re, shutil
import build_review_1st as first
ROOT = Path(__file__).resolve().parents[1]
BASE = '0593d96d855760f51b4cc5b51cb4969eac987a23'
def once(text, old, new):
    if text.count(old) != 1: raise ValueError('Album build anchor changed: '+old[:80])
    return text.replace(old, new, 1)
def build():
    if os.getenv('DEPLOY_ENV') == 'production': raise ValueError('Album review is not a production build')
    baseline = ROOT/'dist'; out = ROOT/'albums-dist'
    if out.is_symlink(): raise ValueError('Symlink output refused')
    app = (baseline/'src/app.js').read_text()
    before = {p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['dist/src/app.js','dist/index.html','review-1st/app.js','auth/Gateway.php']}
    snapshot = json.loads((ROOT/'albums/snapshot.json').read_text())
    if snapshot.get('schemaVersion') != 1 or not isinstance(snapshot.get('tracks'),dict): raise ValueError('Snapshot required')
    if any(t.get('melonPeaks', {}).get('sourceType') not in (None, 'melon_original_song_info') for t in snapshot['tracks'].values()):
        raise ValueError('Non-original Melon record in preview snapshot')
    data = first.extract((baseline/'src/data.js').read_text(),'REVIEW_DATA')
    # Source-owned titles remain verbatim; only preview classification labels change.
    for entry in data['albums'] + data['songs']:
        if isinstance(entry.get('format'), str):
            entry['format'] = entry['format'].replace('음반', '앨범')
    all_videos=[]
    for path in sorted((baseline/'src').glob('video-part-*.js')):
        raw=path.read_text(); prefix='REVIEW_DATA.videos.push(...'
        if not raw.startswith(prefix) or not raw.rstrip().endswith(');'): raise ValueError('Video chunk schema changed')
        all_videos.extend(json.loads(raw[len(prefix):].strip()[:-2]))
    keep={s.get('videoId') for s in data['songs']}; channels={}; sample={}
    for v in sorted(all_videos,key=lambda v:v.get('publishedAt') or v.get('date',''),reverse=True):
        key=v.get('channelKey','unknown'); count=channels.get(key,0)
        if count<16 or v['id'] in keep: sample[v['id']]=v
        channels[key]=count+1
    data['videos']=list(sample.values());data['scope']['offlineSample']=True
    def inline(value):
        path=(baseline/value.split('?')[0]).resolve()
        if not path.is_relative_to(baseline.resolve()) or not path.is_file() or path.is_symlink(): raise ValueError('Unsafe image path')
        return 'data:image/webp;base64,'+base64.b64encode(path.read_bytes()).decode()
    for group in data['assets'].values():
        for k,v in group.items(): group[k]=inline(v)
    for item in data['gallery']: item['src']=inline(item['src'])
    legacy=(baseline/'src/production-ui.js').read_text()
    catalog=first.extract(legacy,'CATALOG')
    for channel in catalog['videos']['channels']: channel['videos']=channel['videos'][:3]
    pattern=r'^const CATALOG=[^\n]+;'
    if len(re.findall(pattern,legacy,flags=re.M))!=1: raise ValueError('Legacy catalog changed')
    legacy=re.sub(pattern,lambda _:'const CATALOG='+first.script_json(catalog)+';',legacy,count=1,flags=re.M)
    migration=(ROOT/'site/storage-migration.js').read_text()
    app=once(app,migration,'/* Preview storage is independent; no production preferences are read. */')
    for name in ('musicView','songView','albumView','albumCard'):
        app=once(app,'function '+name+'(', 'function albumsBase'+name[0].upper()+name[1:]+'(')
    app=app.replace('음반','앨범')
    app=app.replace('isegye:archive:', 'isegye:albums-review:')
    app=once(app,"if(!location.hash)history.replaceState(null,'','#/home');render();", "if(!location.hash)history.replaceState(null,'','#/music?tab=albums');render();")
    artwork={};brands={};badges={}
    for group,destination in [('covers',artwork),('brands',brands),('badges',badges)]:
        for key,asset in snapshot.get('assets',{}).get(group,{}).items():
            path=(ROOT/asset['path']).resolve()
            if not path.is_relative_to((ROOT/'albums/asset-cache').resolve()) or not path.is_file() or path.is_symlink():raise ValueError('Missing or unsafe album asset')
            raw=path.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=asset['sha256'] or len(raw)>180000:raise ValueError('Album asset integrity/size')
            destination[key]='data:image/webp;base64,'+base64.b64encode(raw).decode()
    addition='const ALBUMS_ART='+first.script_json(artwork)+';\nconst ALBUMS_BRANDS='+first.script_json(brands)+';\nconst ALBUMS_BADGES='+first.script_json(badges)+';\n'+re.sub(r'^export ','',(ROOT/'albums/core.js').read_text(),flags=re.M)+'\n'+(ROOT/'albums/ui.js').read_text()
    app=once(app,"if(!location.hash)history.replaceState",addition+"\nif(!location.hash)history.replaceState")
    css=(baseline/'src/styles.css').read_text()+'\n'+(ROOT/'albums/theme.css').read_text()+'\n'+(ROOT/'albums/engagement.css').read_text()+'\n'+(ROOT/'albums/domestic.css').read_text()+'\n'+(ROOT/'albums/records.css').read_text()
    code='const ALBUMS_SEED='+first.script_json(snapshot)+';\nconst REVIEW_DATA='+first.script_json(data)+';\n'+(baseline/'src/core.js').read_text()+'\n'+(baseline/'src/live-core.js').read_text()+'\n'+legacy+'\n'+app
    code=code.replace('isegye:theme:v1','isegye:albums-review:theme:v1').replace('isegye:bookmarks:v1','isegye:albums-review:bookmarks:v1')
    sha=lambda s:"'sha256-"+base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()+"'"
    html=(baseline/'index.html').read_text()
    html=re.sub(r'<script src="[^"]+"[^>]*></script>','',html)
    html=re.sub(r'<link rel="icon"[^>]+>','',html)
    html=once(html,'<link rel="stylesheet" href="src/styles.css">','<style>'+css+'</style>')
    html=once(html,"script-src 'self'",'script-src '+sha(code))
    html=once(html,"style-src 'self'",'style-src '+sha(css))
    html=once(html,'</body>','<script>'+code+'</script></body>')
    html=html.replace('<title>ISEGYE! · 이세계아이돌 비공식 팬 아카이브</title>','<title>앨범 검토 · ISEGYE!</title>')
    if 'noindex,nofollow' not in html or len(html.encode())>=9*1024*1024: raise ValueError('Preview size or robots policy failed')
    if out.exists(): shutil.rmtree(out)
    out.mkdir()
    for name in ('review.html','index.html'): (out/name).write_text(html)
    (out/'insights.json').write_text(json.dumps(snapshot,ensure_ascii=False,indent=2)+'\n')
    meta={'review':'albums-first-review','branch':'feature/albums','baseCommit':BASE,'commit':os.getenv('GITHUB_SHA','0'*40),'builtAt':datetime.now(timezone.utc).isoformat(),'mode':'isolated-preview','snapshotAt':snapshot['generatedAt'],'counts':{k:len(data[k]) for k in ('members','songs','albums','videos')},'fullAlbumCatalog':True,'unrelatedVideoCatalog':'bounded preview sample','productionUIReplaced':False,'productionBatchChanged':False,'externalCollection':'workflow only; browser reads same-origin snapshot API'}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    (out/'robots.txt').write_text('User-agent: *\nDisallow: /\n')
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==v for p,v in before.items())
    print(json.dumps({'status':'isolated_review_built','bytes':len(html.encode()),**meta},ensure_ascii=False))
    return meta
if __name__=='__main__':build()
