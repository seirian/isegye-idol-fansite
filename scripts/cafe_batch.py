"""Consume repository-reviewed inputs, not unverified search hits. Times are original observations."""
from datetime import date,datetime,timedelta,timezone
from functools import lru_cache
from pathlib import Path
import json,re
import notice_policy as policy
ROOT=Path(__file__).resolve().parents[1];KST=timezone(timedelta(hours=9));PREFIX='https://cafe.naver.com/steamindiegame/'
IDS={345:'cafe-members',1250:'cafe-agency'}

def timestamp(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('timezone required')
    return dt

def validate(d):
    if d['schemaVersion']!=1 or set(d['boards'])!={'345','1250'}:raise ValueError('invalid review packet')
    lo=date.fromisoformat(d['from']); checked=timestamp(d['checkedAt']); end=checked.astimezone(KST).date()
    if not 0<=(end-lo).days<=14:raise ValueError('invalid review window')
    policy.validate_archive({'schemaVersion':1,'checkedAt':d['checkedAt'],'rangeStart':'2021-08-26','rangeEnd':end.isoformat(),'notices':d['notices']})
    for r in d['notices']:
        dt=timestamp(r['publishedAt'])
        if dt>checked or dt.astimezone(KST).date()<lo:raise ValueError('notice outside observation window')
    for m,b in d['boards'].items():
        n=sum(r['menuId']==int(m) for r in d['notices'])
        if b['state']=='reviewed':
            if b['count']!=n or not 1<=b['pages']<=8:raise ValueError('incomplete evidence')
        elif b['state']!='unverified' or n:raise ValueError('unverified rows')
    for f in d.get('fanSeries',[]):
        if set(f)!={'articleId','title','date','publishedAt','sameBoard','sameAuthor','public'} or not all(f[k] is True for k in ('sameBoard','sameAuthor','public')):raise ValueError('unreviewed fan article')
        day=date.fromisoformat(f['date']);dt=timestamp(f['publishedAt']);aid=f['articleId'];title=re.fullmatch(r'\[\s*(\d{1,2})/(\d{1,2})\([^)]{1,4}\)\s*\]\s*이세돌\s*뱅온정보',f['title'])
        if type(aid) is not int or aid<=0 or PREFIX+str(aid) in policy.EXCLUDED_URLS or not title or (int(title[1]),int(title[2]))!=(day.month,day.day) or dt.astimezone(KST).date()!=day or not lo<=day<=end or dt>timestamp(d.get('fanCheckedAt',d['checkedAt'])):raise ValueError('fan series evidence differs')
    return d

@lru_cache(maxsize=1)
def windows():
    return sorted([validate(json.loads(p.read_text())) for p in (ROOT/'schedule/cafe-batches').glob('*.json')],key=lambda d:timestamp(d['checkedAt']))

def official(now=None):
    rows={}
    for d in windows():
        if now and timestamp(d['checkedAt'])>timestamp(now):continue
        for r in d['notices']:rows[r['articleId']]=(r,d['checkedAt'])
    return rows

def fans(now=None):
    result={}
    for d in windows():
        check=d.get('fanCheckedAt',d['checkedAt'])
        if now and timestamp(check)>timestamp(now):continue
        for r in d.get('fanSeries',[]):result[r['articleId']]=(r,check)
    return result

def combined_history(base):
    rows={r['articleId']:r for r in base['notices']};rows.update({i:r for i,(r,_) in official().items()});docs=windows()
    return {**base,'notices':sorted(rows.values(),key=lambda r:(r['publishedAt'],r['articleId'])),'rangeEnd':max([base['rangeEnd']]+[timestamp(d['checkedAt']).astimezone(KST).date().isoformat() for d in docs if all(b['state']=='reviewed' for b in d['boards'].values())])}

def populate(data,now,seed):
    import schedule_feed as feed
    for row,at in sorted(official(now).values(),key=lambda p:timestamp(p[0]['publishedAt']),reverse=True)[:250]:
        post=feed.public_item(IDS[row['menuId']],PREFIX+str(row['articleId']),row['title'],row['publishedAt'],at,members=row['members'],detail='공개 게시판의 작성자·권한·게시일 확인 · 본문 일정 미확인')
        data['news'].append(post)
    for row,at in sorted(fans(now).values(),key=lambda p:p[0]['date'],reverse=True)[:100]:
        post=feed.public_item('fan-roundup',PREFIX+str(row['articleId']),row['title'],row['publishedAt'],at,members=list(feed.MEMBERS),detail='같은 작성자·게시판의 날짜별 뱅온 정리 원문 · 실제 방송 여부 미확인')
        data['forecasts'].append({**post,'date':row['date'],'time':None,'type':'broadcast','status':'reference','certainty':'unknown','dateBasis':'roundup_title'})
    states={}
    for sid in (*IDS.values(),'fan-roundup'):
        obs=[d for d in windows() if timestamp(d['checkedAt'])<=timestamp(now)]
        if not obs:states[sid]={'mode':'reviewed_batch','state':'snapshot','lastAttemptAt':None,'lastSuccessAt':seed['generatedAt'],'detail':'초기 확인 자료'};continue
        d=obs[-1]; at=d['checkedAt'];lo=d['from'];stats={'fromKst':lo,'asOf':at,'inputType':'reviewed_metadata'}
        if sid=='fan-roundup':
            ff=fans(now); last=max((t for _,t in ff.values()),default=seed['generatedAt'],key=timestamp); at=d.get('fanCheckedAt',at); n=len(d.get('fanSeries',[])) if timestamp(at)<=timestamp(now) else 0
            states[sid]={'mode':'reviewed_batch','state':'snapshot' if n else 'needs_review','lastAttemptAt':at,'lastSuccessAt':last,'coverage':{**stats,'asOf':at,'verifiedArticles':n,'complete':False},'detail':'작성자·날짜를 확인한 팬 정리 원문만 반영 · 방송 확정 아님' if n else '지정 원문 외 날짜별 뱅온 자료 미확인'}
        else:
            menu=next(m for m,s in IDS.items() if s==sid); board=d['boards'][str(menu)];ok=board['state']=='reviewed';good=[r for r in obs if r['boards'][str(menu)]['state']=='reviewed']; last=good[-1]['checkedAt'] if good else seed['generatedAt']
            states[sid]={'mode':'reviewed_batch','state':'snapshot' if ok else 'needs_review','lastAttemptAt':at,'lastSuccessAt':last,'coverage':{**stats,'complete':ok,'count':board.get('count')},'detail':'검토 입력 반영 · 원본 확인 '+at if ok else '원본 확인 실패 · 이전 자료 유지'}
    for k in ('news','forecasts'):data[k]=list({r['id']:r for r in data[k]}.values())
    return states
