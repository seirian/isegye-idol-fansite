"""Source-backed history validation and fail-closed build contracts."""
import copy
import json
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from enhance_visual_history import validate_history,once
class VisualHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.history=json.loads((ROOT/'visuals/history.json').read_text())
    def test_valid_history(self):validate_history(self.history)
    def test_all_years_covered(self):self.assertEqual({r['date'][:4] for r in self.history['events']},{str(n) for n in range(2021,2027)})
    def test_no_duplicate_ids(self):self.assertEqual(len(self.history['events']),len({r['id'] for r in self.history['events']}))
    def test_first_record_is_recruitment(self):self.assertEqual(min(r['date'] for r in self.history['events']),'2021-06-22')
    def test_unsafe_source_rejected(self):
        h=copy.deepcopy(self.history);h['sources']['group']['url']='http://namu.wiki/';self.assertRaises(ValueError,validate_history,h)
    def test_future_event_rejected(self):
        h=copy.deepcopy(self.history);h['events'][0]['date']='2027-01-01';self.assertRaises(ValueError,validate_history,h)
    def test_missing_source_rejected(self):
        h=copy.deepcopy(self.history);h['events'][0]['sources']=[];self.assertRaises(ValueError,validate_history,h)
    def test_unretrieved_cafe_link_not_evidence_by_itself(self):
        h=copy.deepcopy(self.history);h['events'][0]['sources']=['cafe-apply'];self.assertRaises(ValueError,validate_history,h)
    def test_other_artist_rejected(self):
        h=copy.deepcopy(self.history);h['events'][0]['members']=['other'];self.assertRaises(ValueError,validate_history,h)
    def test_ambiguous_patch_rejected(self):self.assertRaises(ValueError,once,'a a','a','b')
    def test_exact_patch(self):self.assertEqual(once('abc','b','d'),'adc')
if __name__=='__main__':unittest.main()
