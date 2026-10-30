"""Publication allowlist: reviewed public member/agency notices, never search hits.

Only public listing metadata is imported. No account identifiers, article bodies,
comments, session values or profile data are part of this archive.
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from functools import lru_cache
import json, re
ROOT = Path(__file__).resolve().parents[1]
MEMBERS = {'ine','jingburger','lilpa','jururu','gosegu','viichan'}
FAN_URL = 'https://cafe.naver.com/steamindiegame/22137397'
EXCLUDED_URLS = {'https://cafe.naver.com/steamindiegame/22133027',
                 'https://cafe.naver.com/steamindiegame/22133865'}
FIELDS = {'articleId','menuId','author','members','title','publishedAt','verifiedRole','public','titleGeneralized'}
KST = timezone(timedelta(hours=9))

def validate_archive(data):
    if data.get('schemaVersion') != 1 or data.get('rangeStart') != '2021-08-26':
        raise ValueError('invalid notice archive version/range')
    checked = datetime.fromisoformat(data.get('checkedAt','').replace('Z','+00:00'))
    if checked.tzinfo is None: raise ValueError('archive time needs timezone')
    if not re.fullmatch(r'20\d{2}-\d{2}-\d{2}', data.get('rangeEnd','')):
        raise ValueError('invalid archive end')
    rows = data.get('notices')
    if not isinstance(rows,list) or len(rows) > 20000: raise ValueError('invalid archive size')
    ids=set()
    for row in rows:
        if set(row) != FIELDS: raise ValueError('unexpected notice metadata')
        aid = row['articleId']; menu = row['menuId']; author = row['author']
        if type(aid) is not int or aid <= 0 or aid in ids: raise ValueError('duplicate notice')
        ids.add(aid)
        if row['public'] is not True or type(row['titleGeneralized']) is not bool: raise ValueError('non-public notice')
        if menu == 345:
            if author not in MEMBERS or row['verifiedRole'] != 'staff' or row['members'] != [author]:
                raise ValueError('unapproved member author')
        elif menu == 1250:
            if author != 'parable' or row['verifiedRole'] not in ('staff','manager'):
                raise ValueError('unapproved agency author')
        else: raise ValueError('unapproved board')
        if not isinstance(row['members'],list) or not row['members'] or not set(row['members']) <= MEMBERS:
            raise ValueError('invalid notice members')
        if not isinstance(row['title'],str) or not 1 <= len(row['title']) <= 220:
            raise ValueError('invalid notice title')
        published=datetime.fromisoformat(row['publishedAt'].replace('Z','+00:00'))
        if published.tzinfo is None or not data['rangeStart'] <= published.astimezone(KST).date().isoformat() <= data['rangeEnd']:
            raise ValueError('notice date outside scope')
        if 'https://cafe.naver.com/steamindiegame/'+str(aid) in EXCLUDED_URLS:
            raise ValueError('explicitly excluded post')
    return data

@lru_cache(maxsize=1)
def archive():
    return validate_archive(json.loads((ROOT/'schedule/approved-notices.json').read_text()))

@lru_cache(maxsize=1)
def reviewed_sources():
    return {'https://cafe.naver.com/steamindiegame/'+str(r['articleId']):
            'cafe-members' if r['menuId']==345 else 'cafe-agency'
            for r in archive()['notices']}

def is_publishable(row):
    source=row.get('sourceId'); url=row.get('sourceUrl','')
    if url in EXCLUDED_URLS: return False
    if source == 'naver-search': return False
    if source in ('cafe-members','cafe-agency'):
        return reviewed_sources().get(url) == source
    if source == 'fan-roundup': return url == FAN_URL
    if source == 'parable-web':
        from urllib.parse import urlsplit
        try:
            u=urlsplit(url)
            return u.scheme=='https' and u.hostname=='parable-asia.com' and not u.username and not u.password and u.port in (None,443)
        except ValueError:return False
    return False

def clean_snapshot(value):
    """Remove unapproved rows before merging OLD data, not only future fetches."""
    cleaned={**value}
    for bucket in ('news','events','forecasts'):
        cleaned[bucket]=[row for row in value.get(bucket,[]) if is_publishable(row)]
    cleaned['sources']=[{**s,**({'state':'restricted','mode':'disabled_unverified',
        'lastAttemptAt':None,'lastSuccessAt':None,
        'detail':'작성자가 확인되지 않은 검색 글은 수집·표시하지 않습니다.'} if s['id']=='naver-search' else {})}
        for s in value.get('sources',[])]
    cleaned['publicationPolicy']='approved-authors-only-v1'
    return cleaned
