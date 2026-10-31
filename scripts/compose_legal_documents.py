"""Render unchanged canonical policy bodies inside the normal application shell."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1]

def once(text,before,after):
    if text.count(before)!=1:raise ValueError('Legal shell anchor changed: '+before[:60])
    return text.replace(before,after,1)

def compose(app,css,meta):
    bodies={kind:(ROOT/'auth'/f'{kind}.html').read_text() for kind in ('terms','privacy')}
    for kind,body in bodies.items():
        if '<script' in body.lower() or f'id="{kind}-01"' not in body:raise ValueError('Unexpected policy source')
    app=once(app,'guide:guideView','guide:legalGuideView')
    app=once(app,'privacy:privacyView}',"privacy:()=>legalDocumentView('privacy'),terms:()=>legalDocumentView('terms')}")
    app=once(app,"privacy:'개인정보 안내'","privacy:'개인정보처리방침',terms:'이용약관'")
    # Canonical links remain useful with a new tab or without JavaScript. Normal
    # clicks are routed locally; no iframe or authenticated endpoint is opened.
    payload=json.dumps(bodies,ensure_ascii=False).replace('</','<\\/')
    app=once(app,'shell();render();','const LEGAL_DOCUMENTS='+payload+';\n'+(ROOT/'legal/ui.js').read_text()+'\nshell();render();')
    anchor="if(focus)document.getElementById('main').focus({preventScroll:true});"
    app=once(app,anchor,anchor+"\n if(page==='terms'||page==='privacy')queueMicrotask(legalDocumentMount);")
    css+='\n'+(ROOT/'auth/legal.css').read_text()
    meta['legalPresentation']={'inSiteRoutes':['terms','privacy'],'sharedSiteTheme':True,
        'canonicalBodiesUnchanged':True,'publicDisclosureRetained':True,
        'sourceHashes':{k:hashlib.sha256(v.encode()).hexdigest() for k,v in bodies.items()}}
    return app,css
