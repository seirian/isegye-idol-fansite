"""Offline evidence reduction only; inputs are digest-pinned by the review workflow."""
from pathlib import Path
from datetime import datetime,timezone
from collections import defaultdict
from copy import deepcopy
from io import BytesIO
import argparse,hashlib,json,re,sys,zipfile
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import album_history_backfill as b

def props(raw):
    n=BeautifulSoup(raw,'html.parser').select_one('script#__NEXT_DATA__')
    if not n:raise ValueError('Missing rendered source data')
    return json.loads(n.string)['props']['pageProps']
def sourceclock(value):
    at=datetime.fromisoformat(value)
    if at.tzinfo is not None or at.minute or at.second or at.microsecond:raise ValueError('Unexpected source clock')
    return at.replace(tzinfo=b.KST)
def complete(url,raw,tracks):
    m=re.fullmatch(re.escape(b.BASE)+r'/chart/melon/(top100|hot100-d100)/(\d{8})/(\d{1,2})',url)
    if not m:raise ValueError('Wrong dated route')
    slug,day,hh=m.groups();at=datetime.strptime(day+hh.zfill(2),'%Y%m%d%H').replace(tzinfo=b.KST)
    kind=next(k for k,v in b.KINDS.items() if v==slug);data=props(raw)['data'];rows=data['data']
    chart={'melon_top100':'MELON_TOP100_CHART','melon_hot100':'MELON_HOT100_D100_CHART'}[kind]
    if (data.get('platform')!='melon' or data.get('chart')!=chart or sourceclock(data['time'])!=at
        or data.get('size')!=100 or len(rows)!=100 or {r['ranking'] for r in rows}!=set(range(1,101))
        or len({str(r['song']['id']) for r in rows})!=100):raise ValueError('Incomplete or wrong-clock chart')
    idx={str(r['song']['id']):r['ranking'] for r in rows}
    return {'url':url,'responseSha256':hashlib.sha256(raw).hexdigest(),'chart':kind,'hour':b.hour(at),
        'verifiedFullChartSize':100,'observations':{sid:idx.get(r['trackId']) for sid,r in tracks.items()
        if b.clock(r['releaseAt'])<=at<=b.clock(r['charts'][kind]['scannedThrough'])}}

def prepare(review_path,dated_path,baseline_path):
    review=json.loads(zipfile.ZipFile(review_path).read('review.json'))
    if review.get('cutoffAt')!=b.CUTOFF.isoformat():raise ValueError('Unexpected reviewed cutoff')
    data={k:deepcopy(review[k]) for k in ['schemaVersion','sourceType','cutoffAt','tracks','excluded','searches']}
    data['reviewCheckedAt']=review.get('checkedAt');data['sourceReviewErrors']=deepcopy(review.get('errors',[]))
    data['reviewStopped']=review.get('stopped');data['sourceConflicts']=[]
    data['scope']='Finite owner-requested search and history review for registered 16 albums/works; no recurring third-party requests'
    full={p['url']:deepcopy(p) for p in review.get('fullCharts',[])}
    z=zipfile.ZipFile(dated_path)
    for entry in json.loads(z.read('index.json')):
        if entry.get('url') in full or not entry.get('file'):continue
        raw=z.read(entry['file'])
        if hashlib.sha256(raw).hexdigest()!=entry['sha256']:raise ValueError('Changed dated source evidence')
        try:full[entry['url']]=complete(entry['url'],raw,data['tracks'])
        except ValueError:data['sourceReviewErrors'].append({'url':entry['url'],'state':'incomplete_dated_chart_not_used'})
    for sid,r in data['tracks'].items():
        for kind,c in r['charts'].items():
            index={p[0]:p[1] for p in c['points']};outs={};blocked=set();proofs=[]
            start,end=b.hour(b.clock(r['releaseAt'])),b.hour(b.clock(c['scannedThrough']))
            for url,p in sorted(full.items()):
                if p['chart']!=kind or sid not in p['observations'] or not start<=p['hour']<=end:continue
                h,rank=p['hour'],p['observations'][sid]
                if p.get('verifiedFullChartSize')!=100 or not re.fullmatch('[a-f0-9]{64}',p.get('responseSha256','')):raise ValueError('Missing complete proof')
                at=datetime.fromtimestamp(h*3600,b.KST)
                if url!=b.BASE+'/chart/melon/'+b.KINDS[kind]+'/'+at.strftime('%Y%m%d')+'/'+str(at.hour):raise ValueError('Dated source time mismatch')
                if h in blocked:continue
                old=index.get(h,outs.get(h,'absent'))
                if old!='absent' and old!=rank:
                    blocked.add(h);index.pop(h,None);outs.pop(h,None)
                    data['sourceConflicts'].append({'sid':sid,'chart':kind,'hour':h,'trendRank':old,'datedRank':rank});continue
                proof={'hour':h,'source':url,'responseSha256':p['responseSha256'],'verifiedFullChartSize':100}
                if rank is None:outs[h]=None
                elif type(rank) is int and 1<=rank<=100:index[h]=rank
                else:raise ValueError('Invalid dated rank')
                proofs.append({**proof,'rank':rank})
            c['points']=[[h,v] for h,v in sorted(index.items()) if h not in blocked]
            c['out']=[{k:v for k,v in p.items() if k!='rank'} for p in proofs if p['hour'] in outs and p['hour'] not in blocked and p['rank'] is None]
            # A page URL uniquely identifies a source hour; do not duplicate evidence.
            c['out']=list({p['hour']:p for p in c['out']}.values())
            c['datedEvidence']=[p for p in proofs if p['hour'] not in blocked]
    b.validate_dataset(data)
    catalog=__import__('album_releases').load_catalog()['songs']
    if set(data['searches'])!={s['id'] for s in catalog}:raise ValueError('Not all registered titles were searched')
    raw=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode();digest=hashlib.sha256(raw).hexdigest()
    target=ROOT/'albums/backfills/catalog-20261116.json';target.parent.mkdir(exist_ok=True);target.write_bytes(raw)
    module=ROOT/'scripts/album_history_backfill.py';text=module.read_text()
    if text.count('TO_BE_PINNED_AFTER_REVIEW')!=1:raise ValueError('Unexpected dataset pin state')
    module.write_text(text.replace('TO_BE_PINNED_AFTER_REVIEW',digest))
    baseline_zip=zipfile.ZipFile(baseline_path);prior=json.loads(baseline_zip.read('rebels-backfill-report.json'));baseline_raw=baseline_zip.read('rebels-backfill-after.json')
    if prior.get('status')!='published' or not prior.get('verifiedReadback') or hashlib.sha256(baseline_raw).hexdigest()!=prior['afterSha256']:raise ValueError('Unverified live baseline')
    baseline=json.loads(baseline_raw);report=b.apply(baseline,dataset=data,digest=digest)
    from daily_albums import validate
    validate(baseline,exact=True)
    (ROOT/'album-history-baseline-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'album-history-candidate.json').write_text(json.dumps(baseline,ensure_ascii=False,separators=(',',':'))+'\n')
    albums=defaultdict(lambda:{'tracks':0,'added':0,'top100':0,'hot100':0})
    for row in report['tracks'].values():
        a=albums[row['album']];a['tracks']+=1
        for kind,c in row['charts'].items():a['added']+=c['addedHistoricalSlots'];a[kind.replace('melon_','')]+=c['addedHistoricalSlots']
    summary={'datasetSha256':digest,'datasetBytes':len(raw),'sourcePublicRequests':review.get('publicRequests'),
        'searchedTitles':len(data['searches']),'exactSearchMatches':sum(any(p.get('exactIdFound') for p in v) for v in data['searches'].values()),
        'albums':dict(albums),'tracks':len(report['tracks']),'excluded':data['excluded'],'addedHistoricalSlots':report['addedHistoricalSlots'],
        'rollingAdded':report['rollingAdded'],'conflicts':report['conflicts'],'sourceConflicts':data['sourceConflicts'],
        'failedPages':sum(c['failedPages'] for r in report['tracks'].values() for c in r['charts'].values()),
        'reviewedPages':sum(len(c['pages']) for r in data['tracks'].values() for c in r['charts'].values()),'reviewStopped':data['reviewStopped']}
    (ROOT/'album-history-review-summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    lines=['# Registered album historical repair — 2026-11-16','',
      'Owner-requested scope: the 16 registered albums/works, with 24 Melon tracks and two video-only exclusions. Individual verified release timestamps through 2026-11-16 10:00 KST; HOT100 scanned through the first 101 days as a conservative eligibility boundary. No inferred ranks or blanket chart-out conversion.',
      '', '## Baseline audit (actual publication is verified separately)', '',
      '| Album | Tracks | TOP100 added | HOT100 added |', '|---|---:|---:|---:|']
    for name,a in albums.items():lines.append(f"| {name} | {a['tracks']} | {a['top100']} | {a['hot100']} |")
    lines+=['',f"Verified baseline additions: {report['addedHistoricalSlots']}; rolling-window additions: {report['rollingAdded']}. Dataset SHA256: `{digest}`.",
      '', '## Source and limitations',
      'Each registered title was searched in the actual 가이섬 public search UI endpoint. Exact Melon song/album IDs, title, artist and individual release date/time were verified against song pages. Monthly rendered trend pages were read with the visible end-date form contract. Numeric ranks only were accepted; null cells remain unverified. Chart-out records require a complete exact-hour chart with 100 unique IDs and ranks 1–100. Source URLs and response digests are retained in the reviewed finite dataset.',
      'Source: https://xn--o39an51b2re.com/ ; attribution conditions: https://xn--o39an51b2re.com/policy . No lyrics, source UI, artwork or unrelated artists’ rank datasets are republished. This is not a licensed Melon partner API.',
      'Unverified hours include source omissions, no published chart, chart eligibility boundaries and unproven chart-out; they are NOT all collection failures. No claim of complete all-hour history is made.',
      '', '## Preservation and publication',
      'Compact permanent per-song archives are separate from the rolling 30-day feed. Only recent missing/error observations are added to rolling histories; existing valid observations and collection/source clocks are preserved. Conflicts are reported and existing verified values win. The normal collector reuses the immutable local dataset without new third-party requests. Date controls show bounded 30-day historical windows with source attribution.',
      'Publication requires the historical UI to be deployed, the existing main-only owner/host checks and pause controls, a shared album lock, live-byte comparison, previous-feed backup and readback verification. Other song fields, video-only works, account stores, routes, collection schedules and unrelated feeds are unchanged. Investigation workflows and raw source HTML are excluded from the production tree.']
    (ROOT/'docs/ALBUM_HISTORY_20261116.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary,ensure_ascii=False),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('review');p.add_argument('dated');p.add_argument('baseline');a=p.parse_args();prepare(a.review,a.dated,a.baseline)
