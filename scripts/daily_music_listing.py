"""Read public page metadata only. No internal API, cookies, sign-in or media extraction."""
import json,re
from datetime import timedelta,timezone
from urllib import request

def embedded(text,var):
    found=re.search(r'(?:var\s+)?'+var+r'\s*=\s*(?=\{)',text)
    if not found:raise ValueError('public metadata unavailable')
    return json.JSONDecoder().raw_decode(text,found.end())[0]

def tree(x):
    if isinstance(x,dict):
        yield x
        for v in x.values():yield from tree(v)
    elif isinstance(x,list):
        for v in x:yield from tree(v)

def text(obj):return obj.get('simpleText') or ''.join(x.get('text','') for x in obj.get('runs',[]))

def public_rows(cid,k,now,report,known):
    import daily_music as m
    # Requested identity and canonical channel metadata must agree before looking at any tiles.
    content=m.read('https://www.youtube.com/channel/'+cid+'/videos?hl=en',4500000).decode();page=embedded(content,'ytInitialData')
    if page.get('metadata',{}).get('channelMetadataRenderer',{}).get('externalId')!=cid:raise ValueError('listing identity mismatch')
    active=[n['tabRenderer'] for n in tree(page.get('contents',{})) if n.get('tabRenderer',{}).get('selected') and n['tabRenderer'].get('title','').casefold()=='videos']
    if len(active)!=1:raise ValueError('videos tab unavailable')
    found={}
    for node in tree(active[0].get('content',{})):
        v=node.get('videoRenderer') or node.get('gridVideoRenderer')
        if v:
            vid=v.get('videoId');t=text(v.get('title',{}));age=text(v.get('publishedTimeText',{}))
        elif 'lockupViewModel' in node:
            v=node['lockupViewModel'];vid=v.get('contentId');meta=v.get('metadata',{}).get('lockupMetadataViewModel',{});t=meta.get('title',{}).get('content','');age=' '.join(x.get('content','') for x in tree(meta.get('metadata',{})) if isinstance(x.get('content'),str) and 'ago' in x['content'])
        else:continue
        if m.VID.fullmatch(vid or '') and t:found[vid]=(t,age)
    if not found:raise ValueError('unrecognized or empty public listing')
    report.update(transport='public_videos_tab',listingSample=len(found));out=[]
    for vid,(title,age) in list(found.items())[:35]:
        # The relative UI label is only an inexpensive exclusion for clearly old posts. Never used as the publication timestamp.
        if re.search(r'\b(?:[2-9]|\d{2,}) months? ago|\b(?:\d+ years?|a year) ago',age,re.I):continue
        if vid in known or not m.MARK.search(title) or m.BLOCK.search(title):continue
        if not m.classify(k,title):report['review'].append(vid);continue
        try:
            body=m.read('https://www.youtube.com/watch?v='+vid+'&hl=en',5500000).decode();player=embedded(body,'ytInitialPlayerResponse');details=player.get('videoDetails',{});micro=player.get('microformat',{}).get('playerMicroformatRenderer',{})
            if details.get('channelId')!=cid or details.get('videoId')!=vid or details.get('isLiveContent') or details.get('isUpcoming') or m.clean_text(details.get('title',''))!=m.clean_text(title):raise ValueError('video identity mismatch')
            stamp=m.clock(micro.get('publishDate') or micro.get('uploadDate') or '')
            if now-timedelta(days=30)<=stamp<=now:out.append((vid,title,stamp.astimezone(timezone.utc).isoformat()))
        except (ValueError,KeyError,TypeError,OSError):report['verificationErrors']+=1;report['review'].append(vid)
    return out
