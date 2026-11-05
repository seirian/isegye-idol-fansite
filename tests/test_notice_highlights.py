import sys,unittest,copy,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from notice_highlights import highlights
import schedule_feed
ROOT=Path(__file__).resolve().parents[1]

class PublicNoticeDetailTests(unittest.TestCase):
 def test_musicart_public_event_facts(self):
  s='''네이버 메뉴
[안내] 이세계아이돌 팬사인회
일시: 2026년 11월 15일 15:00 KST
응모 기간: 2026년 11월 4일 ~ 6일 23:59
판매처: 뮤직아트
비밀번호 1234
응모자 이름 (Name)
디스코드 연락처 입력
당첨자 특전: 사인 앨범과 포토카드
'''
  a=highlights(s,'[안내] 이세계아이돌 팬사인회')
  self.assertIn('일시: 2026년 11월 15일 15:00 KST',a)
  self.assertIn('응모 기간: 2026년 11월 4일 ~ 6일 23:59',a)
  self.assertTrue(all('비밀번호' not in z and '이름' not in z for z in a))
 def test_bounded_and_no_markup(self):
  a=highlights(('모집기간 2026년 11월 6일 23:59\n'*300)+'<script>확정 일시</script>')
  self.assertLessEqual(len(a),6)
  self.assertTrue(all('<' not in v for v in a))
 def test_reject_unverified_source_and_html(self):
  d=json.loads((ROOT/'schedule/seed.json').read_text())
  now=d['generatedAt'];row=copy.deepcopy(d['news'][0]);row.update(contentHighlights=['행사 일시 2026-11-15 15:00'],contentCheckedAt=now)
  d['news']=[row]
  with self.assertRaises(schedule_feed.FeedError):schedule_feed.validate(d)
 def test_keep_verified_lines_after_temporary_detail_failure(self):
  raw=json.loads((ROOT/'schedule/seed.json').read_text());raw['news']=[]
  item=schedule_feed.public_item('berriz-notice','https://berriz.in/ko/isegyeidol/notice/2742/','앨범 팬사인회 안내','2026-11-04T00:00:00+09:00','2026-11-05T02:00:00Z')
  item.update(id='berriz-notice-2742',contentHighlights=['행사 일시 2026년 11월 15일 오후 3시'],contentCheckedAt='2026-11-05T02:00:00Z')
  old={**raw,'generatedAt':'2026-11-05T02:01:00Z','news':[item]}
  new={**raw,'generatedAt':'2026-11-05T03:01:00Z','news':[{**item,'checkedAt':'2026-11-05T03:00:00Z'}]}
  new['news'][0].pop('contentHighlights');new['news'][0].pop('contentCheckedAt')
  merged=schedule_feed.merge(old,new)
  self.assertEqual(merged['news'][0]['contentHighlights'],item['contentHighlights'])
  self.assertEqual(merged['news'][0]['contentCheckedAt'],item['contentCheckedAt'])

if __name__=='__main__': unittest.main()
