"""RPG artifact checks use a private fixture and never publish or create sessions."""
import base64
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_rpg as b


class RPGBuilderTests(unittest.TestCase):
    def setUp(self):
        # Fixtures exercise review packaging even when the runner is on main.
        # The dedicated branch guard test overrides these values explicitly.
        environment = patch.dict(os.environ, {"GITHUB_REF": "refs/heads/feature/ipari-rpg", "DEPLOY_ENV": "review"})
        environment.start()
        self.addCleanup(environment.stop)
        self.temporary = tempfile.TemporaryDirectory(prefix="rpg-build-test-")
        self.root = Path(self.temporary.name).resolve()
        self.addCleanup(self.temporary.cleanup)
        self.write("rpg/index.html", '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
                   '<meta name="robots" content="noindex,nofollow,noarchive">'
                   '<!--CSP--><!--STYLE--></head><body><main>' + "모험 기록 " * 1400
                   + '</main><!--SCRIPT--></body></html>')
        self.write("rpg/styles.css", "body { color: #eee; background: #111; }")
        self.write("rpg/content.js", "export const CHAPTERS = [{ id: 'first' }];\n")
        self.write("rpg/engine.js", "import { CHAPTERS } from './content.js';\n"
                   "export const SAVE_KEY = 'isegye:rpg:v1';\n"
                   "export function createGame() { return {chapter: CHAPTERS[0].id}; }\n")
        self.write("rpg/app.js", "import { createGame, SAVE_KEY } from './engine.js';\n"
                   "document.body.dataset.game = createGame().chapter;\n")
        self.write("visuals/history.json", json.dumps({"checkedAt": "2026-10-23", "events": []}))
        self.write("catalog/album-releases.json", "[]")
        self.write("rpg/art-source/PROMPTS.md", "Original fantasy game artwork prompts.\n")
        for name in b.ART_NAMES:
            self.write(f"rpg/assets/{name}.webp", b"RIFF" + (2040).to_bytes(4, "little") + b"WEBP" + b"\x00" * 2040)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value if isinstance(value, bytes) else value.encode())

    def mutate(self, relative, old, new):
        path = self.root / relative
        path.write_text(path.read_text().replace(old, new))

    def test_bundle_hashes_and_art_round_trip(self):
        raw, metadata = b.assemble(self.root)
        text = raw.decode()
        self.assertEqual(metadata["htmlSha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(metadata["htmlBytes"], len(raw))
        self.assertEqual(metadata["storageKey"], "isegye:rpg:v1")
        self.assertFalse(metadata["productionWrites"])
        self.assertFalse(metadata["playtime"]["humanMeasured"])
        self.assertTrue(metadata["sourceReady"])
        self.assertIn("connect-src 'none'", text)
        self.assertNotIn("'unsafe-inline'", text)
        self.assertNotIn("'unsafe-eval'", text)
        self.assertNotIn("import {", text)
        for tag, opening in (("script", '<script type="module">'), ("style", "<style>")):
            blocks = re.findall(re.escape(opening) + r"([\s\S]*?)</" + tag + ">", text)
            self.assertEqual(len(blocks), 1)
            self.assertIn("sha256-" + b.hash64(blocks[0]), text)
        packed = re.search(r"const RPG_ART = Object.freeze\((\{[^\n]+\})\);", text)
        art = json.loads(packed[1])
        self.assertEqual(set(art), set(b.ART_NAMES))
        for name, value in art.items():
            decoded = base64.b64decode(value.split(",", 1)[1], validate=True)
            self.assertEqual(metadata["sourceHashes"][f"rpg/assets/{name}.webp"], b.digest(decoded))

    def test_build_is_deterministic_and_isolated(self):
        original = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with patch.dict(os.environ, {"GITHUB_REF": "refs/heads/feature/ipari-rpg", "DEPLOY_ENV": "review"}), contextlib.redirect_stdout(io.StringIO()):
            first = b.build(root=self.root)
            second = b.build(root=self.root)
        out = self.root / "rpg-dist"
        self.assertEqual(first["htmlSha256"], second["htmlSha256"])
        self.assertEqual((out / "index.html").read_bytes(), (out / "review.html").read_bytes())
        self.assertEqual(json.loads((out / "build-info.json").read_text())["htmlSha256"], second["htmlSha256"])
        self.assertEqual(set(out.iterdir()), {out / name for name in ("index.html", "review.html", "build-info.json")})
        for relative, raw in original.items():
            self.assertEqual((self.root / relative).read_bytes(), raw)

    def test_missing_artwork_fails_without_output(self):
        (self.root / "rpg/assets/cast.webp").unlink()
        with self.assertRaisesRegex(ValueError, "source"):
            b.build(root=self.root)
        self.assertFalse((self.root / "rpg-dist").exists())

    def test_invalid_artwork_fails(self):
        self.write("rpg/assets/cast.webp", b"not a WebP" * 400)
        with self.assertRaisesRegex(ValueError, "WebP"):
            b.assemble(self.root)

    def test_symlinked_artwork_fails(self):
        path = self.root / "rpg/assets/cast.webp"
        path.unlink()
        path.symlink_to(self.root / "rpg/assets/worlds.webp")
        with self.assertRaisesRegex(ValueError, "unsafe"):
            b.assemble(self.root)

    def test_symlinked_output_fails_before_any_write(self):
        output = self.root / "rpg-dist"
        output.mkdir()
        victim = self.root / "existing-page.html"
        victim.write_text("existing page")
        (output / "review.html").symlink_to(victim)
        with self.assertRaisesRegex(ValueError, "output symlink"):
            b.build(root=self.root)
        self.assertEqual(victim.read_text(), "existing page")
        self.assertFalse((output / "index.html").exists())

    def test_preview_cannot_target_operating_branch(self):
        for settings in ({"GITHUB_REF": "refs/heads/main"}, {"GITHUB_REF": "refs/heads/develop"}, {"DEPLOY_ENV": "production"}):
            with self.subTest(settings=settings), patch.dict(os.environ, settings), self.assertRaisesRegex(ValueError, "operating release"):
                b.build(root=self.root)

    def test_module_dependency_order_is_checked(self):
        with self.assertRaisesRegex(ValueError, "dependency order"):
            b.flatten_modules({"rpg/app.js": "import { game } from './engine.js';\n"})

    def test_unsupported_module_loading_is_rejected(self):
        for source in ("import { x } from 'https://example.com/x.js';\n", "import('./engine.js');\n", "import * as Engine from './engine.js';\n", "import { x as y } from './engine.js';\n"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                b.flatten_modules({"rpg/engine.js": "export const x=1;\n", "rpg/app.js": source})

    def test_closing_tags_and_null_bytes_are_rejected(self):
        for injected in ("\n// </script><script>alert(1)</script>", "\n// </STYLE>", "\x00"):
            with self.subTest(injected=injected):
                self.write("rpg/app.js", "// fixture" + injected)
                with self.assertRaisesRegex(ValueError, "Unsafe inline"):
                    b.assemble(self.root)

    def test_shell_resource_and_inline_handlers_are_rejected(self):
        for markup in ('<script src="https://example.com/x.js"></script>', '<link rel="stylesheet" href="https://example.com/x.css">', '<button onclick="alert(1)">x</button>', '<img src="https://example.com/a.webp">', '<main style="display:none">x</main>'):
            with self.subTest(markup=markup):
                self.write("rpg/index.html", '<meta name="robots" content="noindex,nofollow,noarchive">'
                           + "".join(b.MARKERS) + markup)
                with self.assertRaisesRegex(ValueError, "Unexpected"):
                    b.assemble(self.root)

    def test_css_external_resources_are_rejected(self):
        for css in ('@import "https://example.com/font.css";', 'body{background:url(https://example.com/a.png)}'):
            with self.subTest(css=css):
                self.write("rpg/styles.css", css)
                with self.assertRaisesRegex(ValueError, "CSS resources"):
                    b.assemble(self.root)

    def test_duplicate_markers_are_rejected(self):
        self.mutate("rpg/index.html", "<!--SCRIPT-->", "<!--SCRIPT--><!--SCRIPT-->")
        with self.assertRaisesRegex(ValueError, "one RPG build marker"):
            b.assemble(self.root)


if __name__ == "__main__":
    unittest.main()
