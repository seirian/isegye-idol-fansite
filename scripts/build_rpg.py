#!/usr/bin/env python3
"""Build the RPG review as one offline HTML file, without changing the live site.

The deliberately small bundler accepts named, relative imports of preceding game
modules. It does not fetch dependencies, execute application code, or need npm.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "feature/ipari-rpg"
GAME = "ipari-chronicle"
STORAGE_KEY = "isegye:rpg:v1"
SOURCES = ("rpg/content.js", "rpg/engine.js", "rpg/app.js")
ART_NAMES = ("worlds", "members", "cast")
MAX_ART_BYTES = 4 * 1024 * 1024
MAX_HTML_BYTES = 8 * 1024 * 1024
MARKERS = ("<!--CSP-->", "<!--STYLE-->", "<!--SCRIPT-->")


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def hash64(value: str) -> str:
    return base64.b64encode(hashlib.sha256(value.encode()).digest()).decode()


def source_bytes(root: Path, relative: str) -> bytes:
    """Reject symlinked inputs rather than packing data from outside this project."""
    path = root / relative
    if not path.is_file() or any(part.is_symlink() for part in (path, *path.parents) if part != root.parent):
        raise ValueError("Missing or unsafe RPG source: " + relative)
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("RPG source escaped its root: " + relative)
    return path.read_bytes()


IMPORT = re.compile(
    r"^[ \t]*import\s*\{(?P<names>[^}]+)\}\s*from\s*['\"](?P<path>[^'\"]+)['\"]\s*;[ \t]*(?:\n|$)",
    re.MULTILINE,
)


def flatten_modules(modules: dict[str, str]) -> str:
    """Strip only supported local imports, preserving ES exports for unit tests."""
    available: set[str] = set()
    sections: list[str] = []
    for relative, source in modules.items():
        def strip_import(match: re.Match) -> str:
            imported = match.group("path")
            if imported not in ("./content.js", "./engine.js"):
                raise ValueError("Unsupported RPG import: " + imported)
            dependency = (Path(relative).parent / imported).as_posix()
            if dependency not in available:
                raise ValueError("RPG modules must follow dependency order: " + imported)
            names = [name.strip() for name in match.group("names").split(",") if name.strip()]
            if not names or any(not re.fullmatch(r"[$A-Za-z_][$\w]*", name) for name in names):
                raise ValueError("Only unaliased named RPG imports are supported")
            return ""

        body = IMPORT.sub(strip_import, source)
        if re.search(r"\bimport\b\s*(?:\(|['\"{*]|[A-Za-z_$])", body):
            raise ValueError("Unbundled or dynamic import in " + relative)
        if re.search(r"\bexport\s*(?:\*|\{[^}]*\}\s*from\b|default\b)", body):
            raise ValueError("Unsupported RPG re-export or default export in " + relative)
        available.add(relative)
        sections.append("// " + relative + "\n" + body.rstrip() + "\n")
    return "\n".join(sections)


class ShellAudit(HTMLParser):
    """The shell contains presentation markup only; the builder owns resources."""
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "base", "iframe", "object", "embed", "link", "audio", "video", "form"):
            raise ValueError("Unexpected resource tag in RPG shell: " + tag)
        for key, value in attrs:
            if key.startswith("on") or key in ("src", "srcset", "style"):
                raise ValueError("Unexpected inline resource or handler in RPG shell: " + key)
            if key in ("href", "action") and value and not (value.startswith(("#", "/", "https://"))):
                raise ValueError("Unsafe navigation link in RPG shell")


def assemble(root: Path = ROOT) -> tuple[bytes, dict]:
    """Return reproducible HTML and its source manifest without writing output."""
    root = Path(root).resolve()
    data: dict[str, bytes] = {}
    for relative in ("rpg/index.html", "rpg/styles.css", *SOURCES, "visuals/history.json", "catalog/album-releases.json"):
        data[relative] = source_bytes(root, relative)
    shell = data["rpg/index.html"].decode()
    for marker in MARKERS:
        if shell.count(marker) != 1:
            raise ValueError("Expected one RPG build marker: " + marker)
    if "noindex,nofollow,noarchive" not in shell:
        raise ValueError("RPG review must be excluded from search indexing")
    ShellAudit().feed(shell)
    history = json.loads(data["visuals/history.json"])
    if not isinstance(history.get("events"), list) or not history.get("checkedAt"):
        raise ValueError("Expected the existing dated activity archive")
    css = data["rpg/styles.css"].decode()
    if re.search(r"@import\b|url\s*\(", css, re.I):
        raise ValueError("RPG CSS resources must be supplied by packed artwork")
    art: dict[str, str] = {}
    for name in ART_NAMES:
        relative = f"rpg/assets/{name}.webp"
        raw = source_bytes(root, relative)
        if not (1000 < len(raw) < MAX_ART_BYTES) or raw[:4] != b"RIFF" or raw[8:12] != b"WEBP":
            raise ValueError("Unexpected RPG WebP format or size: " + name)
        data[relative] = raw
        art[name] = "data:image/webp;base64," + base64.b64encode(raw).decode()
    prompt_path = "rpg/art-source/PROMPTS.md"
    if (root / prompt_path).exists() or (root / prompt_path).is_symlink():
        data[prompt_path] = source_bytes(root, prompt_path)
    modules = {relative: data[relative].decode() for relative in SOURCES}
    js = "const RPG_ART = Object.freeze(" + json.dumps(art, separators=(",", ":")) + ");\n"
    js += flatten_modules(modules)
    if STORAGE_KEY not in js:
        raise ValueError("RPG save namespace missing")
    if "\x00" in shell + css + js or re.search(r"</(?:script|style)", css + "\n" + js, re.I):
        raise ValueError("Unsafe inline RPG source")
    csp = (
        "default-src 'none'; script-src 'sha256-" + hash64(js) + "'; style-src 'sha256-" + hash64(css)
        + "'; connect-src 'none'; img-src data:; media-src 'none'; font-src 'none'; "
        "base-uri 'none'; form-action 'none'; object-src 'none'"
    )
    html = (shell.replace("<!--CSP-->", '<meta http-equiv="Content-Security-Policy" content="' + csp + '">')
            .replace("<!--STYLE-->", "<style>" + css + "</style>")
            .replace("<!--SCRIPT-->", '<script type="module">' + js + "</script>"))
    raw = html.encode()
    if not 10000 < len(raw) <= MAX_HTML_BYTES:
        raise ValueError("RPG HTML must be between 10 KiB and 8 MiB")
    metadata = {
        "review": "ipari-rpg", "branch": BRANCH, "commit": os.getenv("GITHUB_SHA", "local"),
        "mode": "rpg-preview", "game": GAME, "version": 1,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "htmlSha256": digest(raw), "htmlBytes": len(raw), "storageKey": STORAGE_KEY,
        "generatedArtwork": True, "artworkPacked": len(art), "artworkKeys": list(ART_NAMES),
        "productionWrites": False, "liveFeedsConnected": False, "externalMediaUsed": False,
        "sourceReady": True, "historyCheckedAt": history["checkedAt"],
        "playtime": {"targetMinutes": [30, 60], "humanMeasured": False},
        "fiction": "Fan-created story, dialogue, skills and battles; real activity dates are archival records.",
        "sourceHashes": {relative: digest(value) for relative, value in data.items()},
    }
    return raw, metadata


def output_file(directory: Path, name: str) -> Path:
    if directory.is_symlink() or (directory / name).is_symlink():
        raise ValueError("Unsafe RPG build output symlink")
    return directory / name


def build(output: Path | None = None, root: Path = ROOT) -> dict:
    if os.getenv("DEPLOY_ENV") == "production" or os.getenv("GITHUB_REF") in ("refs/heads/main", "refs/heads/develop"):
        raise ValueError("RPG review builder cannot publish an operating release")
    raw, metadata = assemble(root)
    directory = Path(output) if output is not None else Path(root) / "rpg-dist"
    for name in ("index.html", "review.html", "build-info.json"):
        output_file(directory, name)
    directory.mkdir(parents=True, exist_ok=True)
    output_file(directory, "index.html").write_bytes(raw)
    output_file(directory, "review.html").write_bytes(raw)
    output_file(directory, "build-info.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": "built", "game": GAME, "bytes": len(raw), "sha256": digest(raw)}, ensure_ascii=False))
    return metadata


if __name__ == "__main__":
    build()
