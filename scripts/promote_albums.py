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
            code=once(code,"fetch('/review-albums/api/insights'","fetch('/api/albums'")
            code=code.replace('검토 스냅샷','마지막 확인 데이터').replace('API 응답 실패 · 내장 검토본 표시','갱신 확인 실패 · 마지막 확인 데이터 표시')
            code=once(code,"if(next.generatedAt!==albumInsights.generatedAt)throw new Error('Snapshot version mismatch');","if(!albumAcceptRuntime(next))throw new Error('Invalid runtime album snapshot');")
            code=once(code,"albumInsights=next;albumApiState='동일 출처 API 확인';","albumInsights=next;albumApiState='동일 출처 API 확인';if(/^#\\/(music|album|song)(?:[/?]|$)/.test(location.hash))render();")
            code=once(code, "catch {albumApiState='갱신 확인 실패 · 마지막 확인 데이터 표시';}", "catch {albumApiState='갱신 확인 실패 · 마지막 확인 데이터 표시';if(/^#\\/(music|album|song)(?:[/?]|$)/.test(location.hash))render();}")
        if name=='flow-view.js':
            code=once(code, '${graphic}<div class="ai-flow-summary">', '${graphic}${demo?"":albumFlowFreshness(kind)}<div class="ai-flow-summary">')
            code=code.replace('정기 수집은 검토 단계에서 활성화하지 않았습니다.', '앨범 배치는 00시 및 07~23시 정각(KST)에 실행하며 01:00~06:59에는 중지합니다. 20분·40분에는 누락된 현재 시간만 보충합니다. 게시 실패 시 이전 데이터를 유지합니다.')
        pieces.append(code)
    pieces.append((ROOT/'albums/runtime.js').read_text())
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
    from album_releases import extend_music,compose_review
    legacy_path=out/'src/production-ui.js';legacy=legacy_path.read_text()
    catalog=first.extract(legacy,'CATALOG');catalog['music']=extend_music(catalog['music'])
    composed=compose_review(before,catalog['music'])
    (out/'src/data.js').write_text('const REVIEW_DATA='+first.script_json(composed)+';\n')
    legacy=re.sub(r'^const CATALOG=[^\n]+;',lambda _: 'const CATALOG='+first.script_json(catalog)+';',legacy,count=1,flags=re.M)
    legacy_path.write_text(legacy)
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
    meta['albumPromotion']={'acceptedCommit':ACCEPTED,'operatorApprovedDeployment':True,'snapshotAt':data['generatedAt'],'snapshotSha256':hashlib.sha256((out/'src/albums-insights.json').read_bytes()).hexdigest(),'readEndpoint':'/api/albums','fullVideoCatalogPreserved':True,'existingFeedsPreserved':True,'scheduledCollectionChanged':True}
    from album_releases import load_catalog
    meta['dailyAlbums']={'schemaVersion':1,'endpoint':'/api/albums','assetsEndpoint':'/api/albums/assets/','catalogTrackIds':sorted(s['id'] for s in load_catalog()['songs']),'schedule':'00시 및 07~23시 정각 KST (01~06시 중지)', 'watchdog':'20분·40분 누락 시간만 보충'}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    assert all(composed[k][:len(before[k])]==before[k] for k in ('songs','albums'))
    assert all(composed[k]==before[k] for k in before if k not in ('songs','albums'))
    assert all(hashlib.sha256((out/p).read_bytes()).hexdigest()==digest for p,digest in preserved.items())
    for name in ('app.js','albums-data.js','data.js','production-ui.js'):subprocess.run(['node','--check',str(out/'src'/name)],check=True)
    if meta['mode']=='production':
        from inour_sftp import load_payload
        load_payload(out,meta['commit'])
    print(json.dumps({'status':'approved_albums_composed','mode':meta['mode'],'videoChunksPreserved':len(preserved),'albumPromotion':meta['albumPromotion']},ensure_ascii=False))
    return meta
if __name__=='__main__':build()
