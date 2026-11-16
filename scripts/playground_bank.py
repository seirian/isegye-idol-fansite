"""Question-bank invariants and deterministic fact-only question construction."""
from pathlib import Path
from datetime import datetime,timedelta,timezone
import copy,hashlib,json,re,unicodedata
from urllib.parse import urlparse
from build_playground import validate
ROOT=Path(__file__).resolve().parents[1]
KST=timezone(timedelta(hours=9));NAMES={'ine':'아이네','jingburger':'징버거','lilpa':'릴파','jururu':'주르르','gosegu':'고세구','viichan':'비챤'}
MAX_DAILY=8;MAX_QUESTIONS=1000

def encoded(v):return (json.dumps(v,ensure_ascii=False,separators=(',',':'),sort_keys=True)+'\n').encode()
def digest(v):return hashlib.sha256(encoded(v)).hexdigest()
def seed():return validate(json.loads((ROOT/'playground/catalog.json').read_text()))
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKC',s).casefold() if c.isalnum())
def clock(s):
    d=datetime.fromisoformat(s.replace('Z','+00:00'))
    if d.tzinfo is None:raise ValueError('Timezone required')
    return d

def validate_catalog(d,base=None):
    base=base or seed();validate(d)
    if d['version']!=base['version'] or d['categories']!=base['categories'] or d['tracks']!=base['tracks']:raise ValueError('Base facts changed')
    byid={q['id']:q for q in d['questions']}
    if any(byid.get(q['id'])!=q for q in base['questions']) or any(d['sources'].get(k)!=v for k,v in base['sources'].items()):raise ValueError('Reviewed facts changed')
    facts=[]
    for q in d['questions'][len(base['questions']):]:
        p=q.get('provenance',{})
        if q['status']!='reviewed' or p.get('template')!='official-channel-v1' or not re.fullmatch('[0-9a-f]{64}',p.get('factKey','')):raise ValueError('Unverified automatic question')
        if p['factKey'] in facts:raise ValueError('Duplicate fact')
        facts.append(p['factKey']);datetime.fromisoformat(q['eligibleFrom'])
        if any(d['sources'][s]['kind']!='primary' for s in q['sources']):raise ValueError('Auto question needs primary evidence')
    if len(encoded(d))>4500000:raise ValueError('Bank too large')
    return d

def validate_feed(f,base=None):
    if not isinstance(f,dict) or f.get('schemaVersion')!=1 or f.get('feed')!='playground' or f.get('baseVersion')!=(base or seed())['version']:raise ValueError('Feed schema')
    clock(f['generatedAt']);d=validate_catalog(f['catalog'],base)
    if f.get('sha256')!=digest(d):raise ValueError('Bank digest')
    return f

def published_bytes(feed):
    """Preserve reviewed category iteration order on the wire.

    The digest remains canonical and order-independent. Daily seeded selection
    iterates categories, so alphabetically sorting the served mapping would
    reshuffle today's five even when no eligible questions were added.
    """
    validate_feed(feed)
    wire=copy.deepcopy(feed)
    wire['catalog']['categories']=copy.deepcopy(seed()['categories'])
    return (json.dumps(wire,ensure_ascii=False,separators=(',',':'))+'\n').encode()

def auto_question(row,verified,now):
    """Ask about channel identity, not unverified lyrics, dates or performer inference."""
    if row.get('type') not in ('cover','original','remake','official_track'):return None
    members=row.get('members',[])
    if len(members)!=1 or members[0] not in NAMES or verified.get('member')!=members[0]:return None
    title=row.get('title','');vid=row.get('videoId','')
    if not isinstance(title,str) or not 1<=len(title)<=140 or re.search(r'[<>\x00-\x1f]',title) or not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):return None
    fact=digest([norm(title),members[0],row['type']]);key='channel-'+fact[:24];sid='official-'+hashlib.sha256(vid.encode()).hexdigest()[:20]
    choices=[NAMES[m] for m in NAMES if m!=members[0]][:3]+[NAMES[members[0]]]
    day=now.astimezone(KST).date();typ='커버' if row['type']=='cover' else '음악'
    q={'id':key,'category':'covers' if row['type']=='cover' else 'music','level':'가볍게',
       'stem':f'〈{title}〉 {typ} 영상의 공식 원본 채널은 어느 멤버의 채널일까요?',
       'choices':choices,'answer':3,'hint':'공개 원본의 채널 정보를 기준으로 하는 문제예요.',
       'explanation':f'이 문항에서 연결한 〈{title}〉 영상은 {NAMES[members[0]]}의 공식 채널에 공개되어 있습니다. 다른 멤버의 동명 커버가 있는 경우에도 아래 원본 영상을 기준으로 합니다.',
       'sources':[sid],'related':'/#/member/'+members[0],'inspiration':[],'status':'reviewed',
       'eligibleFrom':(day+timedelta(days=1)).isoformat(),'provenance':{'template':'official-channel-v1','factKey':fact,'videoId':vid}}
    source={'title':'YouTube · '+title+' · '+NAMES[members[0]],'kind':'primary','url':'https://www.youtube.com/watch?v='+vid,'checkedAt':day.isoformat(),'note':'공식 등록 채널과 공개 영상 제목을 당일 다시 대조했습니다. 음원 발매일을 뜻하지 않습니다.'}
    return q,sid,source

def assemble(previous,proposals,now):
    base=seed();old=validate_feed(previous,base) if previous else None;d=copy.deepcopy(old['catalog'] if old else base)
    today=now.astimezone(KST).date().isoformat();added_before=(old.get('addedToday',0) if old and old.get('batchDate')==today else 0)
    ids={q['id'] for q in d['questions']};facts={q.get('provenance',{}).get('factKey') for q in d['questions']};added=[]
    for q,sid,source in proposals:
        if len(added)+added_before>=MAX_DAILY or len(d['questions'])>=MAX_QUESTIONS:break
        if q['id'] in ids or q['provenance']['factKey'] in facts:continue
        d['questions'].append(q);d['sources'][sid]=source;ids.add(q['id']);facts.add(q['provenance']['factKey']);added.append(q['id'])
    validate_catalog(d,base)
    f={'schemaVersion':1,'feed':'playground','baseVersion':base['version'],'generatedAt':now.isoformat(),'batchDate':today,'addedToday':added_before+len(added),'sha256':digest(d),'catalog':d}
    return validate_feed(f,base),added
