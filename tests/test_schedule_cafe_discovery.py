from pathlib import Path
import sys,json,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import cafe_batch_discovery as c
class Discovery(unittest.TestCase):
 def test_only_safe_aggregate(self):
  calls=[]
  def fetch(u,headers):
   self.assertTrue(u.startswith(c.f.NAVER_SEARCH_URL+'?'));calls.append(u);return json.dumps({'items':[{'title':'[11/3(화)] 이세돌 뱅온정보','link':c.cb.PREFIX+'99999991'},{'title':'다른 팬','link':c.cb.PREFIX+'99999992'}]}).encode()
  result=c.discover(fetch,{'ISEGYE_NAVER_CLIENT_ID':'fixture','ISEGYE_NAVER_CLIENT_SECRET':'fixture'});self.assertEqual(len(calls),3);self.assertEqual(result['fan-roundup']['unverifiedHints'],1);self.assertNotIn('9999999',json.dumps(result));self.assertNotIn('fixture',json.dumps(result))
 def test_not_checked_is_not_zero(self):
  self.assertTrue(all(v=={'state':'needs_setup'} for v in c.discover(env={}).values()))
