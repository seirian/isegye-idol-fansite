"""Rules for the mixed ISEGYE IDOL official channel only (c2). No network here."""
import re
import unicodedata

EXTRAS = {'album_medley', 'music_clip'}
ARTIST = r'(?:ISEGYE\s*IDOL|이세계\s*아이돌|이세돌)'
GROUP = rf'{ARTIST}(?:\s*\(\s*{ARTIST}\s*\))?'
MEMBER = r'(?:아이네|INE|징버거|JINGBURGER|릴파|LILPA|주르르|JURURU|고세구|GOSEGU|비챤|VIICHAN)'
CREDIT = rf'(?:{GROUP}|{MEMBER}(?:\s*\(\s*{MEMBER}\s*\))?(?:\s*[&,×+]\s*{MEMBER})*)'
FORMATS = [
    ('album_medley', 'official_video', r'(?:highlight\s+medley|album\s+(?:highlight\s+)?medley|하이라이트\s*메들리|앨범\s*(?:하이라이트\s*)?메들리)'),
    ('music_clip', 'official_video', r'(?:official\s+|공식\s*)?(?:(?:vocal|live|performance|music|보컬|라이브|퍼포먼스|음악)\s*)?(?:special\s+clip|스페셜\s*클립)(?:\s*[-|·:]?\s*(?:live\s+(?:clip|performance)|vocal\s+live|라이브\s*클립))?'),
    ('official_track','official_mv',r'(?:(?:official|공식)\s*)?(?:performance\s+)?(?:m/?v|music\s+video|뮤직\s*비디오)'),
    ('official_track','official_audio',r'(?:official\s+audio|공식\s*(?:오디오|음원))'),
    ('official_track','official_video',r'(?:official\s+(?:lyric(?:s)?\s+video|visuali[sz]er)|공식\s*리릭\s*비디오)'),
    ('original','official_video',r'(?:original\s+song|자작곡|오리지널\s*곡)'),
    ('remake','official_video',r'(?:remake|리메이크)'),
    ('cover','official_video',r'(?:vocal\s+cover|cover(?:\s+song)?|커버(?:곡)?)'),
]
MARKERS = [(typ, kind, re.compile(rf'(?:\(\s*(?:{p})\s*\)|\[\s*(?:{p})\s*\]|(?:{p}))\s*$',re.I)) for typ,kind,p in FORMATS]
ALBUM = r'(?:(?:the\s+)?(?:\d+(?:st|nd|rd|th)\s+)?(?:mini\s+|full\s+|single\s+)?album|(?:미니|정규|싱글)?\s*(?:\d+집\s*)?(?:앨범|음반))'
WORK = re.compile(rf'(?P<credit>{CREDIT})\s*(?:[-–—|:]\s*)?(?:{ALBUM}\s*)?(?P<work>.+?)\s*',re.I)
# To avoid treating a sentence containing an MV title as the song itself, a work in
# free text must either be quoted/bracketed or follow an explicit artist separator.
PAIRS = {'‘':'’','“':'”',"'":"'",'"':'"','「':'」','『':'』','[':']','〈':'〉','《':'》'}
NO = re.compile(r'티저|예고|비하인드|메이킹|리액션|예능|브이로그|언박싱|인터뷰|제작기|다시보기|챌린지|게임\s*(?:방송|플레이)|로고\s*모션|팬미팅|shorts?\b|teaser|trailer|behind|reaction|making[ -]?(?:of|film)|interview|vlog|challenge|logo\s*motion|unboxing|gameplay|dance\s*(?:practice|cover)|댄스\s*커버|\bQ\s*&\s*A\b',re.I)
EXPLICIT_SINGING = re.compile(r'vocal|performance|라이브|보컬|퍼포먼스|live|music\s+special|음악\s*스페셜',re.I)

def parse(title, names, performers, keys, evidence=frozenset()):
    """Accept complete, structured format titles, not category or keyword hits.

    An unqualified 'Special Clip' additionally needs a known song by the same
    credited artists (catalog, or official MV/audio in the same channel listing).
    """
    title=' '.join(unicodedata.normalize('NFKC',title).split())
    if not title or len(title)>320 or NO.search(title) or re.search(r'[<>#\x00-\x1f]',title):return None
    for typ,kind,marker in MARKERS:
        hit=marker.search(title)
        if not hit:continue
        prefix=title[:hit.start()].strip().rstrip('|:–—-').rstrip()
        m=WORK.fullmatch(prefix)
        if not m:return None
        work=m['work'].strip();credit=m['credit'];mids=list(names) if re.fullmatch(GROUP,credit,re.I) else performers(credit)
        if not mids:return None
        if work[:1] in PAIRS:
            if len(work)<3 or work[-1]!=PAIRS[work[0]]:return None
            name=work[1:-1].strip()
            if any(q in name for q in ('‘','’','“','”','「','」','[',']')):return None
        elif re.match(r'^\s*[-–—|:]\s*',prefix[m.end('credit'):]):
            name=work
        else:return None
        if not name or len(name)>140 or not any(c.isalnum() for c in name):return None
        if typ=='music_clip' and not EXPLICIT_SINGING.search(hit[0]) and not (keys(name,mids)&evidence):return None
        return {'title':name,'members':mids,'type':typ,'kind':kind}
    return None

# Public Atom metadata actually observed, not a date guessed from the title or album.
# Only used with a current matching official video tile AND independent oEmbed/thumbnail
# checks when the watch page withholds its timestamp. Never overrides a conflicting ID.
OBSERVED_ATOM = {('UCmblbE_WxTaFWcMEGFJ_97w','lFgCjRoFjyU','ISEGYE IDOL (이세계아이돌) ‘Across Dimensions’ HIGHLIGHT MEDLEY'):'2026-11-02T09:00:14+00:00'}
