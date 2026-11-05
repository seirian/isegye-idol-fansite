"""Bounded factual highlights from an explicitly permitted public official page.

Never mirror full articles, account-only content, images or fan comments.
"""
import re
from html import unescape

TERMS=re.compile(r'일시|응모|기간|접수|일정|시간|장소|판매처|특전|당첨|발매|팬사인회|영상통화|신청|취소|변경|참여|진행|공지',re.I)
PRIVATE=re.compile(r'연락처|생년월일|전화번호|이메일|주민등록|주소 입력|결제정보|비밀번호|개인정보|계좌번호|건강상의 이유|진단|치료|비밀번호|응모자 이름|디스코드|인증번호|계정정보')

def highlights(content,title=''):
    if not isinstance(content,str) or len(content)>180000:return []
    results=[];seen=set()
    for raw in content.splitlines():
        line=re.sub(r'\s+',' ',unescape(raw)).strip(' -•·\t')
        if not 8<=len(line)<=170 or '<' in line or '>' in line or not TERMS.search(line) or PRIVATE.search(line):continue
        if re.sub(r'\W+','',line)==re.sub(r'\W+','',title):continue
        if re.search(r'로그인|회원가입|검색|공유하기|댓글|푸터|새 소식|커뮤니티 홈|목록으로|좋아요',line):continue
        if line in seen:continue
        seen.add(line);results.append(line)
        if len(results)==6:break
    return results
