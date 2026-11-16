"""Branch-only deterministic staging from previously reviewed evidence. No live writes."""
from pathlib import Path
from io import BytesIO
from datetime import datetime,timedelta,timezone
import hashlib,json,os,re,sys,zipfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
KST=timezone(timedelta(hours=9));START=datetime(2026,11,9,18,tzinfo=KST);END=datetime(2026,11,16,9,tzinfo=KST)
BASE='https://xn--o39an51b2re.com'
def digest(raw):return hashlib.sha256(raw).hexdigest()
def archive(ident,sha,local):
    if os.getenv('REBELS_LOCAL_EVIDENCE'):
        raw=Path(os.environ['REBELS_LOCAL_EVIDENCE'],local).read_bytes()
    else:
        from album_observation_archive import request,API
        raw=request(API+'/actions/artifacts/'+str(ident)+'/zip',os.environ['GH_TOKEN'],binary=True)
    assert digest(raw)==sha,'Evidence archive hash mismatch'
    return zipfile.ZipFile(BytesIO(raw))
def nextdata(raw):
    match=re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',raw.decode(),re.S)
    assert match,'Missing rendered page data'
    return json.loads(match[1])['props']['pageProps']['data']
def generate():
    a=archive(14187774745,'d3902c890ff4d42e4d221b36ae4aceea26b59691332e929bfa8ff3cb75ab9a5c','rebels-source-evidence.zip')
    z=archive(14188916741,'0670d300c8115aa4148b48bf677b5ccfa2d86b62ab3e61b5c5bca1ddfd17076e','rebels-dated-evidence.zip')
    output={'schemaVersion':1,'trackId':'603813508','albumId':'15120216','releaseAt':START.isoformat(),'cutoffAt':END.isoformat(),'sourceAttribution':'가이섬 공개 차트 기록 · REBELS 한 곡 일회성 검증·보완','evidenceRunId':43782307006,'charts':{}}
    for kind,slug,n,enum in [('melon_top100','top100',1,'MELON_TOP100_CHART'),('melon_hot100','hot100-d100',2,'MELON_HOT100_D100_CHART')]:
        raw=a.read(f'public-{n}.html');data=nextdata(raw)
        assert data['songId']=='603813508' and data['chart']==enum and data['timeUnit']=='HOURS',data['chart']
        ranks=[]
        for row in data['data']:
            at=datetime.fromisoformat(row['time']).replace(tzinfo=KST);rank=row['ranking']
            if START<=at<=END and rank is not None:
                assert type(rank) is int and 1<=rank<=100 and at.minute==at.second==at.microsecond==0
                ranks.append([int((at-START).total_seconds()/3600),rank])
        chart={'source':BASE+'/chart/melon/'+slug+'/trend/ranking/603813508','responseSha256':digest(raw),'ranked':ranks,'out':[]}
        for info in json.loads(z.read('index.json')):
            if 'error' in info or info['chart']!=enum:continue
            raw=z.read(info['file']);assert digest(raw)==info['sha256']
            full=nextdata(raw);at=datetime.fromisoformat(full['time']).replace(tzinfo=KST)
            assert START<=at<=END and full['chart']==enum and info['at']==full['time']
            url=BASE+'/chart/melon/'+slug+'/'+at.strftime('%Y%m%d')+'/'+str(at.hour)
            assert info['url']==url and info['finalUrl']==url
            rows=full['data'];assert len(rows)==100 and sorted(p['ranking'] for p in rows)==list(range(1,101))
            assert len({p['song']['id'] for p in rows})==100 and not any(p['song']['id']=='603813508' for p in rows)
            chart['out'].append({'offset':int((at-START).total_seconds()/3600),'source':url,'responseSha256':info['sha256'],'verifiedFullChartSize':100})
        chart['out'].sort(key=lambda p:p['offset'])
        if kind=='melon_top100':chart['unresolved']=[{'offset':22,'source':BASE+'/chart/melon/top100/20261110/16','reason':'Source chart did not contain a complete unique rank 1-100 list; blank is not classified as out.'}]
        else:chart['sourceAbsentHoursKst']=[2,3,4,5,6]
        output['charts'][kind]=chart
    output['fullChartEvidenceRunId']=43782800358
    raw=(json.dumps(output,ensure_ascii=False,separators=(',',':'))+'\n').encode()
    assert digest(raw)=='7f0d257f5c8c921b8573425cde384387c20b30e7a3af82e553dacf74741e5e6e',digest(raw)
    path=ROOT/'albums/backfills/rebels-20261116.json';path.parent.mkdir(exist_ok=True);path.write_bytes(raw)
    baseline=archive(14187286366,'774db6baa173b57d7a64d873da5e4c231846cd573506d9caa2f251a6c54cddf6','rebels-audit-baseline.zip')
    (ROOT/'rebels-baseline-evidence.json').write_bytes(baseline.read('albums/snapshot.json'))

EDITS={
'scripts/daily_albums.py':{'before':'51afaa504a7bfec194bbe0ca00805f4aa5925a4b3479eca41b50dd8d80d017c3','after':'12ed925dcaa44265430865d5e7d114bbadb2d36a2fdb4813b90bd5580d2cca76','edits':[[9743,9743,"# Finite REBELS-only repair; pinned local facts, never a recurring external crawl.\n    from rebels_melon_backfill import apply as repair_rebels, END as repair_cutoff\n    identity = data.get('tracks', {}).get('rebels', {}).get('melon', {})\n    if (identity.get('trackId') == '603813508' and identity.get('albumId') == '15120216'\n            and clock(data['generatedAt']) >= repair_cutoff):\n        repair_rebels(data, at=clock(data['generatedAt']))\n    "]]},
'albums/flow.js':{'before':'31c0e0ec2910741b08021bdd8b8519caf69f362aa45ca3190986f7a94f04343f','after':'279b48b9c4ec7b46972a015666637a3e42adb752f6a6964dc9271aa6ba7278aa','edits':[[5497,5497,"\n// A fixed, song-specific historical source. Never accept arbitrary feed URLs.\nexport function albumHistoricalReference(item, kind) {\n  const h=item?.melonHistoricalBackfill;\n  if(!h || h.schemaVersion!==1 || h.sourceType!=='guyso_public_historical'\n      || h.trackId!=='603813508' || h.albumId!=='15120216'\n      || item?.melon?.trackId!==h.trackId || item?.melon?.albumId!==h.albumId\n      || !/^[a-f0-9]{64}$/.test(h.datasetSha256||''))return null;\n  const slug={melon_top100:'top100',melon_hot100:'hot100-d100'}[kind];\n  if(!slug)return null;\n  const url=`https://xn--o39an51b2re.com/chart/melon/${slug}/trend/ranking/603813508`;\n  const entry=h.charts?.[kind],from=Date.parse('2026-11-09T18:00:00+09:00'),to=Date.parse('2026-11-16T09:00:00+09:00');\n  if(entry?.source!==url || !Array.isArray(entry.at) || entry.at.length>160)return null;\n  const times=entry.at.map(Date.parse);\n  if(times.some(t=>!Number.isFinite(t)||t<from||t>to||t%3600000))return null;\n  return {url,times:new Set(times),label:'가이섬 대조·보완'};\n}\n"]]},
'albums/flow-view.js':{'before':'68abb856d19cc81b27410e3c43a27894e7d9a3df22ca74ceb4169f89c17626f6','after':'a2d55475b644641b1bae85471e3c37dce29006a251576ba5854331782281199e','edits':[[262,262,";\n  const historical=demo?null:albumHistoricalReference(aiData(s.id),kind);\n  const provenance=t=>historical?.times.has(Date.parse(t))?' · 가이섬 대조·보완':''"],[1432,1432,"provenance(point.at)}${"],[1502,1502,"provenance(point.at)}${"],[1567,1567,"${provenance(point.at)}"],[2030,2030,"':historical?'멜론 관측값 · 가이섬 과거 기록 포함"],[2507,2507,"${historical&&kind==='melon_hot100'?'원본 차트 미제공 또는 미확인 간격 · 중간 순위를 추정하지 않습니다':'"],[2539,2539,"'}"],[4870,4870,"${historical?'멜론 직접 수집 및 가이섬 과거 기록':'"],[4879,4879,"'}"],[5463,5463,"${provenance(row.at)}"],[5545,5545,"${historical?`<a href=\"${esc(historical.url)}\" target=\"_blank\" rel=\"noopener noreferrer\">과거 기록 출처: 가이섬</a> · ${kind==='melon_top100'?'11/10 16:00은 원자료 불완전으로 미확인':'02~06시는 원자료에 시간별 차트가 없는 구간'} · `:''}"]]}}

def edit():
    for name,row in EDITS.items():
        path=ROOT/name;raw=path.read_bytes();assert digest(raw)==row['before'],name+' base differs'
        text=raw.decode()
        for a,b,new in reversed(row['edits']):text=text[:a]+new+text[b:]
        assert digest(text.encode())==row['after'],name+' result differs'
        path.write_text(text)
    path=ROOT/'albums/accepted.json';assert digest(path.read_bytes())=='16422bd35b9fca05272426ca23cc28c8d0e172c80e60922de424b89beb9143c2'
    data=json.loads(path.read_text());names=['albums/flow.js','albums/flow-view.js']
    previous={p:data['sourceHashes'][p] for p in names};current={p:EDITS[p]['after'] for p in names}
    data['sourceHashes'].update(current)
    data['amendments']=[{'id':'rebels-backfill-20261116','scope':'User-requested REBELS-only historical repair attribution; existing album layout and other songs unchanged.','previousSourceHashes':previous,'sourceHashes':current}]
    raw=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode();assert digest(raw)=='2317a52ef01a9852f6693c4d490c2652f20387810243ec64118bde2e2e13be47'
    path.write_bytes(raw)
    for name,sha in {'scripts/rebels_melon_backfill.py':'f800b726e3fd4443535a695285314810603210eddb08b7ce9db4ea3c08906bf4','tests/test_rebels_melon_backfill.py':'7badded297355433484afb5e40e905fe06fbd16fa343fb48b2c165845518046f'}.items():
        assert digest((ROOT/name).read_bytes())==sha,name+' transport differs'

if __name__=='__main__':generate();edit()
