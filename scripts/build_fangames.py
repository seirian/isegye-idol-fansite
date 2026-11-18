#!/usr/bin/env python3
"""Build one image-backed courier game as a self-contained, hash-CSP preview."""
from pathlib import Path
import base64, hashlib, json, os, re
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
BRANCH="feature/isegye-fangames"
SOURCES=["fangames/engine.js","fangames/app.js"]
CSS=["fangames/styles.css"]
REQUIRED_ART=("characters","plaza","items")
OPTIONAL_ART=("cover",)
MAX_HTML_BYTES=8*1024*1024  # Existing read-only PHP handler permits 9 MiB.
STORAGE_KEY="isegye:review:courier:v2"

def digest(b):return hashlib.sha256(b).hexdigest()
def sha64(s):return base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()

def build():
    if os.getenv("DEPLOY_ENV")=="production" or os.getenv("GITHUB_REF") in ("refs/heads/main","refs/heads/develop"):
        raise ValueError("Preview only; operating branches may not run this build")
    src=(ROOT/"fangames/index.html").read_text()
    for marker in ("<!--CSP-->","<!--STYLE-->","<!--SCRIPT-->"):
        if src.count(marker)!=1:raise ValueError("Expected one build marker: "+marker)
    css="\n".join((ROOT/f).read_text() for f in CSS)
    art={};asset_paths=[]
    for name in (*REQUIRED_ART,*OPTIONAL_ART):
        path="fangames/assets/"+name+".webp"
        file=ROOT/path
        if name in OPTIONAL_ART and not file.exists() and not file.is_symlink():continue
        if not file.is_file() or file.is_symlink():raise ValueError("Missing generated artwork: "+name)
        raw=file.read_bytes()
        if not (1000<len(raw)<4*1024*1024) or raw[:4]!=b"RIFF" or raw[8:12]!=b"WEBP":
            raise ValueError("Unexpected artwork format or size: "+name)
        art[name]="data:image/webp;base64,"+base64.b64encode(raw).decode()
        asset_paths.append(path)
    visual_js="const COURIER_ART=Object.freeze("+json.dumps(art,ensure_ascii=False,separators=(',',':'))+");\n"
    js=visual_js+"\n".join((ROOT/f).read_text() for f in SOURCES)+"\n"
    if re.search(r"</(?:script|style)",css+"\n"+js,re.I):raise ValueError("Unexpected HTML close marker")
    if "\x00" in css+js:raise ValueError("NUL in payload")
    csp=("default-src 'none'; script-src 'sha256-"+sha64(js)+"'; style-src 'sha256-"+sha64(css)+
         "'; connect-src 'none'; img-src data:; media-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'")
    html=(src.replace("<!--CSP-->",'<meta http-equiv="Content-Security-Policy" content="'+csp+'">')
         .replace("<!--STYLE-->","<style>"+css+"</style>").replace("<!--SCRIPT-->","<script>"+js+"</script>"))
    raw=html.encode()
    if not (30000<len(raw)<=MAX_HTML_BYTES):raise ValueError("Unexpected page size; maximum is 8 MiB")
    out=ROOT/"fangames-dist"
    if out.is_symlink():raise ValueError("Unsafe dist symlink")
    out.mkdir(exist_ok=True)
    for name in ("index.html","review.html"):(out/name).write_bytes(raw)
    meta=dict(review="isegye-fangames",branch=BRANCH,commit=os.getenv("GITHUB_SHA","local"),
              mode="fangames-preview",game="starlight-courier",version=2,
              builtAt=datetime.now(timezone.utc).isoformat(),
              counts=dict(games=1,characters=6,stages=3),
              generatedArtwork=True,artworkPacked=len(art),
              artworkSource="New original generated member characters, delivery items, plaza scenery and optional cover",
              htmlSha256=digest(raw),htmlBytes=len(raw),
              productionWrites=False,liveFeedsConnected=False,externalMediaUsed=False,
              storageKey=STORAGE_KEY,
              referenceScope="Public fan-game structure and presentation study; no reference code or artwork copied",
              sourceHashes={p:digest((ROOT/p).read_bytes()) for p in ["fangames/index.html",*SOURCES,*CSS,*asset_paths]})
    metadata=json.dumps(meta,indent=2,ensure_ascii=False)+"\n"
    if len(metadata.encode())>7500:raise ValueError("Metadata leaves insufficient hosting envelope")
    (out/"build-info.json").write_text(metadata)
    print(json.dumps(dict(status="built",bytes=len(raw),sha256=digest(raw),counts=meta["counts"]),ensure_ascii=False))
    return meta

if __name__=="__main__":build()
