"""Transport regression tests use no network or credentials."""
import sys,stat,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import inour_sftp as d
from deploy_verified_albums import VerifiedTransferRemote
class TransferTests(unittest.TestCase):
 def make(self,data=b'a',mode=stat.S_IFREG|0o644,uid=d.UID,size=None):
  s=MagicMock();s.lstat.return_value=SimpleNamespace(st_mode=mode,st_uid=uid,st_size=len(data) if size is None else size)
  h=s.open.return_value.__enter__.return_value;h.read.return_value=data
  return VerifiedTransferRemote(s),s,h
 def test_small_read_does_not_prefetch(self):
  r,s,h=self.make();self.assertEqual(r.read('p'),b'a');h.prefetch.assert_not_called()
 def test_large_read_is_bounded(self):
  r,s,h=self.make(b'a'*65536);self.assertEqual(len(r.read('p')),65536);h.prefetch.assert_called_once_with(file_size=65536,max_concurrent_requests=16)
 def test_symlink_refused(self):
  r,s,h=self.make(mode=stat.S_IFLNK|0o777)
  with self.assertRaises(d.Stop):r.read('p')
  s.open.assert_not_called()
 def test_wrong_owner_refused(self):
  r,s,h=self.make(uid=0)
  with self.assertRaises(d.Stop):r.read('p')
 def test_oversize_refused(self):
  r,s,h=self.make(size=10*1024*1024)
  with self.assertRaises(d.Stop):r.read('p')
 def test_truncation_refused(self):
  r,s,h=self.make(size=2)
  with self.assertRaises(d.Stop):r.read('p')
 def test_existing_file_never_overwritten(self):
  r,s,h=self.make()
  with patch.object(r,'parents'):
   with self.assertRaises(d.Stop):r.new(d.ROOT+'/sample',b'new')
  s.open.assert_not_called()
 def test_pipeline_closes_before_readback(self):
  r,s,h=self.make();s.lstat.return_value=None
  with patch.object(r,'parents'),patch.object(r,'read',return_value=b'data') as read:
   r.new(d.ROOT+'/sample',b'data');h.set_pipelined.assert_called_once_with(True);read.assert_called_once()
   s.open.assert_called_once_with(d.ROOT+'/sample','wx')
 def test_bad_readback_refused(self):
  r,s,h=self.make();s.lstat.return_value=None
  with patch.object(r,'parents'),patch.object(r,'read',return_value=b'bad'):
   with self.assertRaises(d.Stop):r.new(d.ROOT+'/sample',b'data')
 def test_close_error_not_swallowed(self):
  r,s,h=self.make();s.lstat.return_value=None;s.open.return_value.__exit__.side_effect=OSError('fixture')
  with patch.object(r,'parents'),patch.object(r,'read') as read:
   with self.assertRaises(OSError):r.new(d.ROOT+'/sample',b'data')
   read.assert_not_called();s.chmod.assert_not_called()
 def test_inherited_scope_guard(self):
  r,s,h=self.make()
  with self.assertRaises(d.Stop):r.new('/web/other',b'data')
  s.open.assert_not_called()
 def test_original_deployer_not_modified(self):
  import deploy_google_access as access
  text=Path(access.__file__).read_text();self.assertIn("os.getenv('GITHUB_REF') == 'refs/heads/main'",text)
  self.assertIn('Host key mismatch; credential not sent',text)
