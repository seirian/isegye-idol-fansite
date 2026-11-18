#!/usr/bin/env python3
"""Build a single offline fan-game review document with strict hash CSP."""
from pathlib import Path
import base64, hashlib, json, os, re
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
BRANCH="feature/isegye-fangames"
SOURCES=["fangames/base.js","fangames/arcade-scenes.js","fangames/arcade.js","fangames/quest.js","fangames/escape.js"]
CSS=["fangames/styles.css","fangames/arcade-art.css"]
PORTRAITS={"ine":"ine","jing":"jingburger","lilpa":"lilpa","jururu":"jururu","gosegu":"gosegu","viichan":"viichan"}
def digest(b):return hashlib.sha256(b).hexdigest()
def sha64(s):return base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
def build():
    if os.getenv("DEPLOY_ENV")=="production" or os.getenv("GITHUB_REF") in ("refs/heads/main","refs/heads/develop"):
        raise ValueError("Preview only; operating branches may not run this build")
    src=(ROOT/"fangames/index.html").read_text()
    assert src.count("<!--CSP-->")==1 and src.count("<!--STYLE-->")==1 and src.count("<!--SCRIPT-->")==1
    css="\n".join((ROOT/f).read_text() for f in CSS)
    portraits={}
    for key,name in PORTRAITS.items():
        file=ROOT/"review"/"portraits"/(name+".webp")
        if not file.is_file() or file.is_symlink():raise ValueError("Missing approved member portrait "+name)
        raw=file.read_bytes()
        if not (1000<len(raw)<120000) or raw[:4]!=b"RIFF" or raw[8:12]!=b"WEBP":raise ValueError("Unexpected portrait format")
        portraits[key]="data:image/webp;base64,"+base64.b64encode(raw).decode()
    visual_js="const FAN_GAME_ART=Object.freeze("+json.dumps(portraits,ensure_ascii=False,separators=(',',':'))+");\n"
    js=visual_js+"\n".join((ROOT/f).read_text() for f in SOURCES)+"\nF.render();\n"
    if re.search(r"</(?:script|style)",css+"\n"+js,re.I):raise ValueError("Unexpected HTML close marker")
    for t in [css,js]:
        if "\x00" in t:raise ValueError("NUL in payload")
    csp=("default-src 'none'; script-src 'sha256-"+sha64(js)+"'; style-src 'sha256-"+sha64(css)+
         "'; connect-src 'none'; img-src data:; media-src 'none'; font-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'")
    html=(src.replace("<!--CSP-->",'<meta http-equiv="Content-Security-Policy" content="'+csp+'">')
         .replace("<!--STYLE-->","<style>"+css+"</style>").replace("<!--SCRIPT-->","<script>"+js+"</script>"))
    raw=html.encode()
    if not (25000<len(raw)<850000):raise ValueError("Unexpected page size")
    out=ROOT/"fangames-dist"
    if out.is_symlink():raise ValueError("Unsafe dist symlink")
    out.mkdir(exist_ok=True)
    for name in ["index.html","review.html"]:(out/name).write_bytes(raw)
    meta=dict(review="isegye-fangames",branch=BRANCH,commit=os.getenv("GITHUB_SHA","local"),
              mode="fangames-preview",builtAt=datetime.now(timezone.utc).isoformat(),
              counts=dict(games=3,missions=12,characters=6,puzzles=8),
              portraitsPacked=len(portraits),artworkSource="existing reviewed member portrait assets and original vector scene art",
              htmlSha256=digest(raw),htmlBytes=len(raw),
              productionWrites=False,liveFeedsConnected=False,externalMediaUsed=False,
              storageKey="isegye:review:fangames:v1",
              referenceScope="Direct public browser inspection; no assets/code copied from references",
              sourceHashes={p:digest((ROOT/p).read_bytes()) for p in ["fangames/index.html",*SOURCES,*CSS,*["review/portraits/"+m+".webp" for m in PORTRAITS.values()]]})
    (out/"build-info.json").write_text(json.dumps(meta,indent=2,ensure_ascii=False)+"\n")
    print(json.dumps(dict(status="built",bytes=len(raw),sha256=digest(raw),counts=meta["counts"]),ensure_ascii=False))
    return meta
if __name__=="__main__":build()
