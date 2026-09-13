import importlib.util, json, shutil, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('commerce_guard', ROOT/'scripts/validate_commerce.py'); guard=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(guard)
class CommerceConsistencyTests(unittest.TestCase):
    def test_live_repository_is_consistent(self):
        result=guard.validate(); self.assertEqual(result['products'],3); self.assertEqual(result['feed_records'],3)
    def test_price_drift_fails_closed(self):
        original=guard.ROOT
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); shutil.copytree(original/'agent',root/'agent'); shutil.copytree(original/'feeds',root/'feeds')
            path=root/'agent/purchase.json'; data=json.loads(path.read_text()); data['offers'][0]['price_usd']=30; path.write_text(json.dumps(data))
            guard.ROOT=root
            try:
                with self.assertRaisesRegex(AssertionError,'agent price drift'): guard.validate()
            finally: guard.ROOT=original
    def test_feed_hash_drift_fails_closed(self):
        original=guard.ROOT
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); shutil.copytree(original/'agent',root/'agent'); shutil.copytree(original/'feeds',root/'feeds')
            manifest=root/'feeds/feed-manifest.json'; data=json.loads(manifest.read_text()); data['sha256_uncompressed']='0'*64; manifest.write_text(json.dumps(data))
            guard.ROOT=root
            try:
                with self.assertRaisesRegex(AssertionError,'SHA-256 drift'): guard.validate()
            finally: guard.ROOT=original
if __name__=='__main__': unittest.main(verbosity=2)
