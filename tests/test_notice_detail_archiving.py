"""External notice detail integration regression."""
import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from compose_notice_details import adapt_app,DETAILS_JS
class NoticeDetailTests(unittest.TestCase):
 def test_scoped(self):
  t=chr(96)+'<p class="detail-copy">'+chr(36)+'{esc(r.summary)}</p>'+chr(96)
  original=('function noticeView(id){return '+t+';}\n'
            'function eventView(id){return '+t+';}\n'
            'function albumCard(a){return "";}\n')
  patched=adapt_app(original)
  self.assertIn('공지 상세 내용',patched)
  self.assertIn(chr(36)+'{archiveNoticeDetails(r)}',patched)
  self.assertIn('D.notices.find(n=>n.sourceUrl===r.sourceUrl',patched)
  self.assertNotIn('fetch(',DETAILS_JS)
  self.assertIn('row.contentHighlights',DETAILS_JS)
  self.assertIn("['berriz-notice','parable-web']",DETAILS_JS)
 def test_missing_anchor(self):
  with self.assertRaises(ValueError):adapt_app('function noticeView(id){}function eventView(id){}function albumCard(a){}')
 def test_build(self):
  self.assertIn('archive_details.adapt_app(', (ROOT/'scripts/promote_review_2nd.py').read_text())
 def test_escaped(self):
  self.assertNotIn('innerHTML=',DETAILS_JS)
  self.assertNotIn('iframe',DETAILS_JS)
  self.assertIn('esc(line)',DETAILS_JS)
if __name__=='__main__':unittest.main()
