import re
from datetime import datetime
LABEL={'rest':'휴방 예상','expected':'방송 예정 · 팬 정리','unknown':'방송 여부 미확인'}

def add(data,now):
    import cafe_batch as cb, schedule_feed as feed
    byurl={r['sourceUrl']:r for r in data['forecasts'] if r.get('dateBasis')=='roundup_title'}
    for d in cb.windows():
        if not d.get('fanCards'):continue
        at=d.get('cardCheckedAt');obs=cb.timestamp(at)
        if obs>cb.timestamp(now):continue
        listed={str(r['articleId']):r for r in d.get('fanSeries',[])}
        for aid,sections in d['fanCards'].items():
            if aid not in listed or not isinstance(sections,dict) or not set(sections)<=set(feed.MEMBERS):raise ValueError('unapproved fan card')
            url=cb.PREFIX+aid;ref=byurl.get(url)
            if not ref or not sections:continue
            data['forecasts']=[p for p in data['forecasts'] if p['sourceUrl']!=url]
            for member,v in sections.items():
                st=v.get('status');tm=v.get('time')
                if set(v)!={'status','time'} or st not in LABEL or (tm is not None and (st!='expected' or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',tm))):raise ValueError('invalid fan card')
                text=feed.MEMBERS[member]+' · '+LABEL[st]+(' · '+tm if tm else '')
                data['forecasts'].append({**ref,'id':ref['id']+'-'+member,'title':text,'members':[member],'time':tm,'certainty':'unknown' if st=='unknown' else 'tentative','checkedAt':at})
