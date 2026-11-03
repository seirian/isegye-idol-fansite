"""Music-only rules for the mixed @waktaverse publisher; no network or inferred artists."""
import re
from official_channel_music import GROUP, NO, parse as official_parse
NONMUSIC = re.compile(NO.pattern + r'|댄스\s*퍼포먼스|안무|노래방|직캠|다시보기|\bAI\b|instrumental|karaoke|fancam|BGM', re.I)
FEATURE = re.compile(r'\((?:ft\.?|feat\.?|featuring)\s*([^()]+)\)', re.I)
MUSIC = re.compile(r'm/?v\b|뮤비|뮤직|official|cover|커버|original|오리지널|오리지날|자작곡|고멤가요제|CM송|theme\s*song|페스티벌.*(?:실황|ver)|jazz|재즈|싸이퍼|cypher', re.I)
def parse(title, names, performers, keys, evidence=frozenset()):
    """Whole-title patterns with explicit artist credits, not keyword-only acceptance."""
    if not title or len(title)>320 or NONMUSIC.search(title) or re.search(r'[<>#\x00-\x1f]',title):return None
    all_members=list(names)
    def row(work,mids,typ='official_track',kind='official_video',**extra):
        work=work.strip().strip('‘’\'"').strip()
        if not work or len(work)>140 or not mids or not any(c.isalnum() for c in work):return None
        return dict(title=work,members=mids,type=typ,kind=kind,**extra)
    source=re.sub(r'\s*\([^()]*\bOST\)\s*$','',title,flags=re.I)
    parsed=official_parse(source,names,performers,keys,evidence)
    if parsed:return parsed
    rev=re.fullmatch(rf'(.+?)\s+(?:Official\s+)?M/?V\s*[-–—|]\s*({GROUP})',source,re.I)
    if rev:return row(rev[1],all_members,kind='official_mv')
    festival=re.fullmatch(rf'{GROUP}\s*(?:[-–—:]\s*)?[‘\'\"]?(.+?)[’\'\"]?\s+(이세계\s*페스티벌(?:\s+20\d{{2}})?)\s*(?:실황|Ver\.)',title,re.I)
    if festival:
        work=festival[1].strip('‘’\'" ');event=re.sub(r'이세계\s*페스티벌','이세계 페스티벌',festival[2])
        return row(work+' · '+event,all_members,'performance',context='festival')
    festival=re.fullmatch(r'이세계\s*페스티벌\s*[-–—]\s*(.+)',title,re.I)
    if festival and keys(festival[1],all_members)&evidence:return row(festival[1]+' · 이세계 페스티벌',all_members,'performance',context='festival')
    jazz=re.fullmatch(rf'(.+?)\s*\(Jazz\.?\s*ver\.?\)\s*[-–—]\s*{GROUP}\s*(?:리와인드\s*)?재즈\s*버전',title,re.I)
    if jazz and keys(jazz[1],all_members)&evidence:return row(jazz[1]+' · 재즈 버전',all_members,'performance')
    cm=re.fullmatch(rf'{GROUP}\s+(.+?\s*CM송)',title,re.I)
    if cm:return row(cm[1],all_members,context='collab',credits='이세계아이돌')
    theme=re.fullmatch(rf'{GROUP}\s*[-–—]\s*(.+?)\s*\([^()]+THEME SONG\)',title,re.I)
    if theme:return row(theme[1],all_members)
    if re.fullmatch(r'이세돌 싸이퍼\s*[-–—]\s*ISEGYE IDOL CYPHER',title,re.I):return row('이세돌 싸이퍼',all_members,'original')
    feat=FEATURE.search(title)
    if feat:
        mids=performers(feat[1])
        if not mids:return None
        if re.match(r'^\[Original Song\]\s*',title,re.I):
            rest=re.sub(r'^\[Original Song\]\s*','',title,flags=re.I)
            match=re.fullmatch(r'(.+?)\s+[-–—]\s+(.+?)\s*\((?:ft\.?|feat\.?)\s*[^()]+\)',rest,re.I)
            if match:return row(match[2],mids,'original',context='collab',credits=match[1]+' '+feat[0])
        match=re.fullmatch(r'(.+?)\s+[-–—]\s+(\([^()]+\)\s*\((?:ft\.?|feat\.?)\s*[^()]+\))\s+[-–—]\s+고멤가요제\s+[^<>]+',title,re.I)
        if match:return row(match[1],mids,context='collab',credits=match[2])
        return None
    duo=re.fullmatch(r'(.+?)\s+[-–—]\s+(.+?)\s+(?:Official\s+)?M/?V',source,re.I)
    if duo and '&' in duo[1] and performers(duo[1]):return row(duo[2],performers(duo[1]),kind='official_mv',context='collab',credits=duo[1])
    return None
