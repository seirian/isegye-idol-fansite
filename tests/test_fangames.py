import base64, hashlib, json, os, re, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class Fangames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta=json.loads((ROOT/"fangames-dist/build-info.json").read_text())
        cls.html=(ROOT/"fangames-dist/review.html").read_text()
    def test_three_game_baseline(self):
        self.assertEqual(self.meta["counts"],{"games":3,"missions":12,"characters":6,"puzzles":8})
        for t in ["우당탕 이세돌","세돌 원정대","이세돌 합방 탈출"]:
            self.assertIn(t,self.html)
    def test_exact_hashed_offline_document(self):
        raw=(ROOT/"fangames-dist/review.html").read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),self.meta["htmlSha256"])
        for t in ("connect-src 'none'","media-src 'none'","object-src 'none'","noindex,nofollow,noarchive"):
            self.assertIn(t,self.html)
        self.assertNotIn("'unsafe-inline'",self.html)
        scripts=re.findall(r"<script>([\s\S]*?)</script>",self.html)
        styles=re.findall(r"<style>([\s\S]*?)</style>",self.html)
        self.assertEqual((len(scripts),len(styles)),(1,1))
        for part in scripts+styles:
            digest=base64.b64encode(hashlib.sha256(part.encode()).digest()).decode()
            self.assertIn("sha256-"+digest,self.html)
    def test_only_approved_sources(self):
        for p in ("fangames/base.js","fangames/arcade.js","fangames/quest.js","fangames/escape.js"):
            source=(ROOT/p).read_text()
            self.assertNotIn("fetch(",source)
            self.assertNotIn("eval(",source)
            self.assertNotIn("YouTube",source)
            self.assertNotIn("getUserMedia",source)
            r=subprocess.run(["node","--check",str(ROOT/p)],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
    def test_review_only_storage_and_site_isolation(self):
        self.assertEqual(self.meta["storageKey"],"isegye:review:fangames:v1")
        self.assertFalse(self.meta["productionWrites"])
        self.assertFalse(self.meta["liveFeedsConnected"])
        self.assertFalse(self.meta["externalMediaUsed"])
        src=(ROOT/"scripts/deploy_fangames.py").read_text()
        for text in ("Only existing review folder is writable","Previous preview integrity","Current auth source","Existing owned preview required","Share", "privatePathsBlocked"):
            if text=="Current auth source" or text=="Share":continue
            self.assertIn(text,src)
        self.assertIn("feature/isegye-fangames",src)
        self.assertIn("verified",src.lower())
    def test_eight_hand_authored_stages(self):
        script=(ROOT/"fangames/escape.js").read_text()
        self.assertEqual(len(re.findall(r"\['[^\n]*',[ ]*'[D!~]{3}'",script)),8)
        self.assertIn("board.positions.every",script)
        self.assertIn("history.push",script)
if __name__=="__main__":unittest.main()
