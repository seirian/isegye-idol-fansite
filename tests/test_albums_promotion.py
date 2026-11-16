"""Production composition boundaries; no live requests."""
from pathlib import Path
import importlib.util,os,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import promote_albums as p
class PromotionTests(unittest.TestCase):
 def test_exact_approved_sources(self):self.assertEqual(p.approval()['acceptedCommit'],p.ACCEPTED)
 def test_snapshot_has_only_melon_charts(self):self.assertEqual(set(p.snapshot()['domesticCharts']),{'melon_top100','melon_hot100'})
 def test_seed_complete_and_pinned(self):
  from prepare_album_release import prepare
  self.assertTrue(prepare().is_file())
 def test_production_adaptation_keeps_home_and_preferences(self):
  app="const D=REVIEW_DATA;const keep='isegye:archive:prefs:v1';"+''.join('function '+n+'(){return 0;}\n' for n in ('musicView','songView','albumView','albumCard'))+"if(!location.hash)history.replaceState(null,'','#/home');render();"
  result=p.adapt(app)
  self.assertIn("'#/home'",result);self.assertIn('isegye:archive:prefs:v1',result)
  self.assertIn("function aiBanner() { return ''; }",result)
  self.assertIn("fetch('/api/albums'",result)
  self.assertNotIn('/review-albums/api',result)
  self.assertIn('albumAcceptRuntime(next)',result)
  self.assertNotIn('next.generatedAt!==albumInsights.generatedAt',result)
  self.assertNotIn('관리자 검토 전용',result)
 def test_missing_build_anchor_fails_closed(self):
  with self.assertRaises(ValueError):p.adapt('function songView(){}')
 def test_existing_schedules_unchanged(self):
  text=(ROOT/'.github/workflows/production.yml').read_text();self.assertNotIn('schedule:',text)
  self.assertIn('branches: [main]',text)
 def test_production_includes_all_preview_gateways(self):
  text=(ROOT/'.github/workflows/production.yml').read_text();self.assertIn('scripts/build_albums_host.py',text)
 def test_default_build_promotes_approved_albums(self):self.assertIn('scripts/promote_albums.py',(ROOT/'scripts/build.mjs').read_text())
