#!/usr/bin/env python3
"""Compose the owner-approved album feature onto the complete operating bundle.
No network, deployment, authentication changes or unrelated catalog sampling.
"""
from pathlib import Path
import hashlib,json,os,re,shutil,subprocess
import build_review_1st as first
ROOT=Path(__file__).resolve().parents[1]
ACCEPTED='f2c00e2bb1f4a762e8ff1578f540584652d8053b'
MODULES=['core.js','peak-fallback.js','flow.js','ui.js','flow-view.js']
STYLES=['theme.css','engagement.css','domestic.css','records.css','flow.css']
def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Album promotion anchor changed: '+old[:80])
    return text.replace(old,new,1)
def approval():
    doc=json.loads((ROOT/'albums/accepted.json').read_text())
    if doc.get('acceptedCommit')!=ACCEPTED or doc.get('operatorApprovedDeployment') is not True:raise ValueError('Album deployment not approved')
    for name,digest in doc['sourceHashes'].items():
        path=(ROOT/name).resolve()
        if not path.is_relative_to(ROOT/'albums') or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Approved album source changed: '+name)
    return doc

def snapshot():
    from prepare_album_release import prepare
    prepare()
    data=json.loads((ROOT/'albums/snapshot.json').read_text())
    if data.get('schemaVersion')!=1 or not isinstance(data.get('tracks'),dict):raise ValueError('Invalid album snapshot')
    from collect_album_peak_fallback import reusable
    for item in data['tracks'].values():
        if item.get('melonPeaks',{}).get('sourceType') not in (None,'melon_original_song_info'):raise ValueError('Original record provenance mismatch')
        if 'melonPeakFallback' in item and not reusable(item['melonPeakFallback'],item.get('melon',{})):raise ValueError('Unverified secondary peak')
    if set(data.get('domesticCharts',{}))-{'melon_top100','melon_hot100'}:raise ValueError('Non-Melon rank collection in production')
    return data

def adapt(app):
    for name in ('musicView','songView','albumView','albumCard'):
        app=once(app,'function '+name+'(','function albumsBase'+name[0].upper()+name[1:]+'(')
    app=app.replace('음반','앨범')
    pieces=[]
    for name in MODULES:
        code=(ROOT/'albums'/name).read_text()
        code=code.replace("import {albumVerifiedPeaks} from './core.js';",'')
        code=re.sub(r'^export ','',code,flags=re.M)
        if name=='ui.js':
            start=code.index('function aiBanner()');end=code.index('function aiLink(',start)
            code=code[:start]+"function aiBanner() { return ''; }\n"+code[end:]
            code=once(code,"if(!location.pathname.startsWith('/review-albums/'))return;","if(location.protocol==='file:')return;")
            code=once(code,"fetch('/review-albums/api/insights'","fetch('/src/albums-insights.json'")
            code=code.replace('검토 스냅샷','마지막 확인 데이터').replace('API 응답 실패 · 내장 검토본 표시','갱신 확인 실패 · 마지막 확인 데이터 표시')
        pieces.append(code)
    # Objects stay shared with the existing song/album maps; source titles are untouched.
    normalization="for(const row of [...D.albums,...D.songs])if(typeof row.format==='string')row.format=row.format.replaceAll('음반','앨범');\n"
    return once(app,"if(!location.hash)history.replaceState",normalization+'\n'.join(pieces)+"\nif(!location.hash)history.replaceState")

def build(directory=None):
    approved=approval();out=directory or ROOT/'dist'
    if out.is_symlink():raise ValueError('Symlink output refused')
    meta=json.loads((out/'build-info.json').read_text())
    if meta.get('mode')=='production' and os.getenv('GITHUB_REF')!='refs/heads/main':raise ValueError('Production is main-only')
    if meta.get('albumPromotion'):raise ValueError('Album promotion must run once on a fresh baseline')
    data=snapshot();before=first.extract((out/'src/data.js').read_text(),'REVIEW_DATA')
    preserved={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (out/'src').glob('video-part-*.js')}
    assets={};target=out/'assets/albums';target.mkdir(parents=True,exist_ok=True)
    for group,name in [('covers','ALBUMS_ART'),('brands','ALBUMS_BRANDS'),('badges','ALBUMS_BADGES')]:
        assets[name]={}
        for key,entry in data.get('assets',{}).get(group,{}).items():
            path=(ROOT/entry['path']).resolve()
            if not path.is_relative_to((ROOT/'albums/asset-cache').resolve()) or path.is_symlink():raise ValueError('Unsafe album asset')
            raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
            if digest!=entry['sha256'] or not re.fullmatch('[0-9a-f]{64}',key) and group!='brands' or len(raw)>180000:raise ValueError('Album asset integrity failed')
            (target/(digest+'.webp')).write_bytes(raw);assets[name][key]='assets/albums/'+digest+'.webp'
    (out/'src/albums-insights.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    code='const ALBUMS_SEED='+first.script_json(data)+';\n'+''.join('const '+name+'='+first.script_json(values)+';\n' for name,values in assets.items())
    (out/'src/albums-data.js').write_text(code)
    (out/'src/app.js').write_text(adapt((out/'src/app.js').read_text()))
    with (out/'src/styles.css').open('a') as f:f.write('\n'+'\n'.join((ROOT/'albums'/name).read_text() for name in STYLES))
    html=(out/'index.html').read_text();html=once(html,'<script src="src/app.js"></script>','<script src="src/albums-data.js"></script><script src="src/app.js"></script>')
    (out/'index.html').write_text(html)
    meta['albumPromotion']={'acceptedCommit':ACCEPTED,'operatorApprovedDeployment':True,'snapshotAt':data['generatedAt'],'snapshotSha256':hashlib.sha256((out/'src/albums-insights.json').read_bytes()).hexdigest(),'readEndpoint':'/src/albums-insights.json','fullVideoCatalogPreserved':True,'existingFeedsPreserved':True,'scheduledCollectionChanged':False}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    assert first.extract((out/'src/data.js').read_text(),'REVIEW_DATA')==before
    assert all(hashlib.sha256((out/p).read_bytes()).hexdigest()==digest for p,digest in preserved.items())
    for name in ('app.js','albums-data.js'):subprocess.run(['node','--check',str(out/'src'/name)],check=True)
    if meta['mode']=='production':
        from inour_sftp import load_payload
        load_payload(out,meta['commit'])
    print(json.dumps({'status':'approved_albums_composed','mode':meta['mode'],'videoChunksPreserved':len(preserved),'albumPromotion':meta['albumPromotion']},ensure_ascii=False))
    return meta
if __name__=='__main__':build()
