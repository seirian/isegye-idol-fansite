"""Finite catalog-wide historical repair; no third-party requests.
Permanent compact history is separate from the existing rolling 30-day feed.
Existing valid observations win; source and collection clocks never change.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse, hashlib, json, os, re

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'albums/backfills/catalog-20261116.json'
DATA_SHA256='c617afafca19b5c1f3f33225d29472ef12861f809b19bf78746aa14eeec12801'
BASE='https://xn--o39an51b2re.com'
KST=timezone(timedelta(hours=9));UTC=timezone.utc
CUTOFF=datetime(2026,11,16,10,tzinfo=KST)
KINDS={'melon_top100':'top100','melon_hot100':'hot100-d100'}
ARCHIVE='melonHistoryArchive'
MAX_POINTS=50000
# The reviewed 24-song scope is fixed; later catalog additions are not an error.
TARGET_TRACKS=frozenset(['rewind', 'winter-spring', 'kidding', 'misty-rainbow', 'stargazers', 'elevate', 'memory', 'be-my-light', 'nameless', 'white', 'smile-for-you', 'lockdown', 'another-world', 'syzygy', 'over', 'superhero', 'cat-save-world', 'your-turn', 'pump-jump-bump', 'love-cells', 'rebels', 'back-2-the-future', 'anti-hero', 'dream-residue'])

def clock(value):
    stamp=datetime.fromisoformat(value.replace('Z','+00:00'))
    if stamp.tzinfo is None:raise ValueError('Timezone required')
    return stamp.astimezone(UTC)

def hour(stamp):return int(stamp.timestamp()//3600)

def valid(point,track):
    try:
        at=clock(point['at']);rank=point.get('rank')
        return (point.get('trackId')==track and not(at.minute or at.second or at.microsecond)
            and ((point.get('status')=='ranked' and type(rank) is int and 1<=rank<=100)
                or (point.get('status')=='out' and rank is None)))
    except (KeyError,ValueError,TypeError,AttributeError):return False

def validate_dataset(data):
    from album_releases import load_catalog
    catalog={s['id']:s for s in load_catalog()['songs'] if s.get('dateKind')!='영상 공개일'}
    if (data.get('schemaVersion')!=1 or data.get('sourceType')!='guyso_public_historical'
        or data.get('cutoffAt')!=CUTOFF.isoformat() or set(data.get('tracks',{}))!=TARGET_TRACKS
        or not TARGET_TRACKS.issubset(catalog)):
        raise ValueError('Unexpected historical catalog/window')
    for sid,item in data['tracks'].items():
        track,album=item.get('trackId',''),item.get('albumId','')
        if not re.fullmatch(r'[1-9]\d{1,11}',track) or not re.fullmatch(r'[1-9]\d{1,11}',album):raise ValueError('Invalid identity')
        start=clock(item['releaseAt'])
        if start.astimezone(KST).date().isoformat()!=catalog[sid]['date'] or start>CUTOFF:raise ValueError('Release date mismatch')
        if item.get('identitySource')!=BASE+'/song/melon/'+track:raise ValueError('Wrong song source')
        if not re.fullmatch('[a-f0-9]{64}',item.get('identitySha256','')):raise ValueError('Missing identity digest')
        if set(item.get('charts',{}))!=set(KINDS):raise ValueError('Wrong chart kinds')
        for kind,chart in item['charts'].items():
            root=BASE+'/chart/melon/'+KINDS[kind]
            if chart.get('source')!=root+'/trend/ranking/'+track:raise ValueError('Wrong chart source')
            end=clock(chart['scannedThrough'])
            if not start<=end<=CUTOFF:raise ValueError('Invalid chart window')
            seen=set()
            for p in chart['points']:
                if (not isinstance(p,list) or len(p)!=2 or type(p[0]) is not int or p[0] in seen
                    or not hour(start)<=p[0]<=hour(end) or type(p[1]) is not int or not 1<=p[1]<=100):raise ValueError('Invalid rank/time')
                seen.add(p[0])
            for p in chart.get('out',[]):
                if type(p.get('hour')) is not int:raise ValueError('Invalid out hour')
                at=datetime.fromtimestamp(p['hour']*3600,KST)
                if (not start<=at<=end or p['hour'] in seen or p.get('source')!=root+'/'+at.strftime('%Y%m%d')+'/'+str(at.hour)
                    or p.get('verifiedFullChartSize')!=100 or not re.fullmatch('[a-f0-9]{64}',p.get('responseSha256',''))):raise ValueError('Out needs complete dated chart')
                seen.add(p['hour'])
            if len(seen)>MAX_POINTS:raise ValueError('Too many archive points')
            for p in chart.get('pages',[]):
                date=datetime.strptime(p['endDate'],'%Y-%m-%d').date()
                if p.get('url')!=chart['source']+'?end='+date.isoformat():raise ValueError('Unexpected period URL')
                if 'error' not in p and not re.fullmatch('[a-f0-9]{64}',p.get('responseSha256','')):raise ValueError('Missing period digest')
    return data

def load_dataset(path=DATA):
    raw=path.read_bytes();digest=hashlib.sha256(raw).hexdigest()
    if len(raw)>4000000 or digest!=DATA_SHA256:raise ValueError('Reviewed historical dataset changed')
    return validate_dataset(json.loads(raw)),digest

def previous_native(item,record,digest):
    archive=item.get(ARCHIVE,{})
    if (archive.get('schemaVersion')!=1 or archive.get('trackId')!=record['trackId']
        or archive.get('albumId')!=record['albumId'] or archive.get('datasetSha256')!=digest):return {}
    result={}
    for kind in KINDS:
        rows=archive.get('charts',{}).get(kind,{}).get('points',[])
        start,end=hour(clock(record['releaseAt'])),hour(clock(record['charts'][kind]['scannedThrough']))
        if not isinstance(rows,list) or len(rows)>MAX_POINTS:raise ValueError('Malformed previous archive')
        result[kind]={};last=-1
        for p in rows:
            if (not isinstance(p,list) or len(p)!=3 or type(p[0]) is not int or not start<=p[0]<=end or p[0]<=last
                or type(p[2]) is not int or p[2] not in (0,1)
                or (p[1] is not None and (type(p[1]) is not int or not 1<=p[1]<=100))):raise ValueError('Malformed previous point')
            last=p[0]
            if p[2]==1:result[kind][p[0]]=p[1]
    return result

def apply(data,*,previous=None,dataset=None,digest=None,at=None,strict=True):
    if dataset is None:dataset,digest=load_dataset()
    at=at or datetime.now(UTC)
    if at<CUTOFF:raise ValueError('Historical cutoff is in the future')
    before=deepcopy(data)
    report={'schemaVersion':1,'datasetSha256':digest,'cutoffAt':CUTOFF.isoformat(),'tracks':{},'conflicts':[],'skipped':[],'excluded':dataset.get('excluded',[])}
    for sid,record in dataset['tracks'].items():
        item=data.get('tracks',{}).get(sid,{});m=item.get('melon',{})
        if m.get('trackId')!=record['trackId'] or m.get('albumId')!=record['albumId']:
            if strict:raise ValueError('Live identity mismatch: '+sid)
            report['skipped'].append(sid);continue
        prior=(previous or before).get('tracks',{}).get(sid,{})
        native=previous_native(prior,record,digest)
        archive={'schemaVersion':1,'trackId':record['trackId'],'albumId':record['albumId'],'releaseAt':record['releaseAt'],
            'through':CUTOFF.isoformat(),'sourceType':'guyso_public_historical','datasetSha256':digest,'charts':{}}
        detail={'title':record['title'],'album':record['album'],'releaseAt':record['releaseAt'],'charts':{}}
        for kind in KINDS:
            chart=record['charts'][kind];start,end=hour(clock(record['releaseAt'])),hour(clock(chart['scannedThrough']))
            external={p[0]:p[1] for p in chart['points']};external.update({p['hour']:None for p in chart.get('out',[])})
            rows={h:[h,rank,0] for h,rank in external.items()}
            for h,rank in native.get(kind,{}).items():rows[h]=[h,rank,1]
            indexed={};existing_hours=set();added=[]
            for p in item.get('charts',{}).get(kind,[]):
                key=clock(p['at'])
                if key in indexed:raise ValueError('Duplicate existing chart hour: '+sid)
                indexed[key]=deepcopy(p)
                if not valid(p,record['trackId']):continue
                h=hour(key)
                if not start<=h<=end:continue
                existing_hours.add(h)
                if h in external and external[h]!=p['rank']:
                    report['conflicts'].append({'sid':sid,'chart':kind,'at':p['at'],'existingRank':p['rank'],'referenceRank':external[h]})
                # Current verified evidence wins, including over a prior retained conflict.
                rows[h]=[h,p['rank'],0 if h in external and external[h]==p['rank'] else 1]
            for h,rank,origin in sorted(rows.values()):
                stamp=datetime.fromtimestamp(h*3600,UTC)
                if not at-timedelta(days=30)<=stamp<=at:continue
                old=indexed.get(stamp)
                if old is not None and valid(old,record['trackId']):continue
                indexed[stamp]={'at':stamp.isoformat(),'trackId':record['trackId'],'rank':rank,'status':'out' if rank is None else 'ranked'}
                added.append(stamp.isoformat())
            if added:
                updated=sorted(indexed.values(),key=lambda p:clock(p['at']))
                item.setdefault('charts',{})[kind]=updated;item['melon'][kind.replace('melon_','')+'History']=deepcopy(updated)
            compact=[rows[h] for h in sorted(rows)];prior_hours=set();old_archive=prior.get(ARCHIVE,{})
            if old_archive.get('datasetSha256')==digest:prior_hours={p[0] for p in old_archive.get('charts',{}).get(kind,{}).get('points',[])}
            baseline=existing_hours|prior_hours;total=end-start+1
            archive['charts'][kind]={'source':chart['source'],'through':chart['scannedThrough'],'points':compact,
                'reviewedPages':len(chart.get('pages',[])),'failedPages':sum('error' in p for p in chart.get('pages',[])),
                'requestedHourlySlots':total,'verifiedSlots':len(compact),'unverifiedHourlySlots':total-len(compact)}
            detail['charts'][kind]={'existingVerifiedSlots':len(baseline),'addedHistoricalSlots':len(set(rows)-baseline),
                'rollingAdded':len(added),'rollingAddedAt':added,'verifiedSlots':len(compact),
                'ranked':sum(p[1] is not None for p in compact),'verifiedOut':sum(p[1] is None for p in compact),
                'requestedHourlySlots':total,'unverifiedHourlySlots':total-len(compact),'failedPages':archive['charts'][kind]['failedPages']}
        item[ARCHIVE]=archive;report['tracks'][sid]=detail
    restored=deepcopy(data)
    for sid in report['tracks']:
        old,row=before['tracks'][sid],restored['tracks'][sid]
        for kind in KINDS:
            if kind in old.get('charts',{}):row.setdefault('charts',{})[kind]=deepcopy(old['charts'][kind])
            elif 'charts' in row:row['charts'].pop(kind,None)
            mirror=kind.replace('melon_','')+'History'
            if mirror in old.get('melon',{}):row['melon'][mirror]=deepcopy(old['melon'][mirror])
            else:row['melon'].pop(mirror,None)
        if 'charts' not in old and not row.get('charts'):row.pop('charts',None)
        if ARCHIVE in old:row[ARCHIVE]=deepcopy(old[ARCHIVE])
        else:row.pop(ARCHIVE,None)
    if restored!=before:raise ValueError('Unrelated fields changed')
    report.update(changed=data!=before,unrelatedFieldsUnchanged=True,sourceClocksUnchanged=True,
        addedHistoricalSlots=sum(c['addedHistoricalSlots'] for r in report['tracks'].values() for c in r['charts'].values()),
        rollingAdded=sum(c['rollingAdded'] for r in report['tracks'].values() for c in r['charts'].values()))
    return report

def reuse_published(data,previous):
    """Daily collection only preserves a repair activated by the UI-gated publisher."""
    at=clock(data['generatedAt'])
    if at<CUTOFF:return None
    published=any(row.get(ARCHIVE,{}).get('datasetSha256')==DATA_SHA256
        for row in previous.get('tracks',{}).values())
    if not published:return None
    return apply(data,previous=previous,at=at,strict=False)

def patch_remote(remote):
    import album_runtime as runtime
    d=runtime.d;router,release,active_path=runtime.active(remote)
    app=remote.read(active_path+'/src/app.js') or b''
    d.require(b'albumArchiveWindow' in app and '과거 기록 출처: 가이섬'.encode() in app,'Historical archive UI must be deployed first')
    runtime.owned(remote);d.require(remote.info(runtime.path('.lock')) is None,'Another album operation is active')
    lock=os.urandom(24);remote.new(runtime.path('.lock'),lock);remote.s.chmod(runtime.path('.lock'),0o600)
    try:
        raw=remote.read(runtime.path('current.json'));d.require(raw is not None,'Existing production feed required')
        data=runtime.decode(raw);d.require(data.get('feed')=='daily-albums','Wrong live feed');report=apply(data)
        from daily_albums import validate
        validate(data,exact=True);candidate=(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        d.require(len(candidate)<=runtime.MAX_BYTES,'Historical feed exceeds transport budget')
        (ROOT/'album-history-before.json').write_bytes(raw);(ROOT/'album-history-after.json').write_bytes(candidate)
        d.require(remote.read(d.ROOT+'/.htaccess')==router and remote.info(d.ROOT+'/.deploy-lock') is None,'Release changed during repair')
        d.require(remote.read(runtime.path('current.json'))==raw,'Live feed changed; refusing overwrite')
        if report['changed']:
            remote.replace(runtime.path('previous.json'),raw,remote.read(runtime.path('previous.json')));remote.s.chmod(runtime.path('previous.json'),0o600)
            remote.replace(runtime.path('current.json'),candidate,raw);remote.s.chmod(runtime.path('current.json'),0o600)
        else:candidate=raw
        try:
            d.require(remote.read(runtime.path('current.json'))==candidate,'Historical readback failed')
            d.require(remote.read(d.ROOT+'/.htaccess')==router,'Router changed after repair')
        except Exception:
            if report['changed'] and remote.read(runtime.path('current.json'))==candidate:remote.replace(runtime.path('current.json'),raw,candidate)
            raise
        report.update(status='published' if report['changed'] else 'already_applied',verifiedReadback=True,release=release,
            beforeSha256=d.digest(raw),afterSha256=d.digest(candidate),checkedAt=datetime.now(UTC).isoformat(),
            collectionGeneratedAt=data['generatedAt'],routingUnchanged=True,accountStoreReadOrWritten=False)
        return report
    finally:
        if remote.read(runtime.path('.lock'))==lock:remote.remove_own(runtime.path('.lock'),lock)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['audit','publish']);parser.add_argument('--snapshot',type=Path,default=ROOT/'albums/snapshot.json');args=parser.parse_args()
    if args.action=='audit':
        data=json.loads(args.snapshot.read_text());report=apply(data)
        (ROOT/'album-history-candidate.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
    else:
        from album_runtime import connection
        from album_hourly import allowed,night_deadline
        if not allowed():raise RuntimeError('Existing night pause policy respected')
        password=os.environ.pop('ISEGYE_SFTP_PASSWORD','')
        with night_deadline(),connection(password) as remote:report=patch_remote(remote)
    (ROOT/'album-history-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False));return 0
if __name__=='__main__':raise SystemExit(main())
