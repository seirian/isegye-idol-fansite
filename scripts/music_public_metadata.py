"""Read metadata already public on the canonical watch page; never play/download media."""
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import urlsplit,parse_qs
import re
from daily_music_listing import embedded,tree,text
class Canonical(HTMLParser):
    def __init__(self):super().__init__();self.urls=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='link' and a.get('rel')=='canonical':self.urls.append(a.get('href',''))
        if tag=='meta' and a.get('property')=='og:url':self.urls.append(a.get('content',''))
def public_watch_date(body,cid,vid,expected_title):
    """Return the displayed absolute date, without inventing a timezone or release time.

    Only primary watch results are examined; recommendations and relative ages cannot
    supply identity, credits, or date. Independent oEmbed and thumbnail checks follow.
    """
    import daily_music as m
    canonical=Canonical();canonical.feed(body)
    def matching(u):
        p=urlsplit(u)
        return p.scheme=='https' and p.hostname=='www.youtube.com' and p.path=='/watch' and parse_qs(p.query).get('v')==[vid]
    if not canonical.urls or not all(matching(u) for u in canonical.urls):raise ValueError('canonical video mismatch')
    j=embedded(body,'ytInitialData')
    nodes=j.get('contents',{}).get('twoColumnWatchNextResults',{}).get('results',{}).get('results',{}).get('contents',[])
    primary=[n['videoPrimaryInfoRenderer'] for n in nodes if 'videoPrimaryInfoRenderer' in n]
    owners=[n['videoOwnerRenderer'] for item in nodes if 'videoSecondaryInfoRenderer' in item for n in tree(item['videoSecondaryInfoRenderer']) if 'videoOwnerRenderer' in n]
    if len(primary)!=1 or len(owners)!=1:raise ValueError('public video metadata missing')
    if m.clean_text(text(primary[0].get('title',{})))!=m.clean_text(expected_title):raise ValueError('public title mismatch')
    if owners[0].get('navigationEndpoint',{}).get('browseEndpoint',{}).get('browseId')!=cid:raise ValueError('public owner mismatch')
    raw=text(primary[0].get('dateText',{}))
    hit=re.fullmatch(r'(?:최초 공개:\s*)?(20\d{2})\.\s*(\d{1,2})\.\s*(\d{1,2})\.',raw)
    if hit:return datetime(*map(int,hit.groups())).date().isoformat()
    raw=re.sub(r'^(?:Premiered|Streamed live on)\s+','',raw)
    for fmt in ('%b %d, %Y','%B %d, %Y'):
        try:return datetime.strptime(raw,fmt).date().isoformat()
        except ValueError:pass
    raise ValueError('no absolute public date')
