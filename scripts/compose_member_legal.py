"""Keep public disclosures independent; reuse the operating shell for signed-in readers.

No identity, protected catalog, feed or storage values are included in the
member-only document bundle. Both presentations use auth/{terms,privacy}.html.
"""
from pathlib import Path
import hashlib
import json
import re
import subprocess
from review_2nd_polish import one

ROOT = Path(__file__).resolve().parents[1]


def documents():
    return {kind: (ROOT / 'auth' / (kind + '.html')).read_text() for kind in ('terms', 'privacy')}


def adapt_legacy(code):
    # Change only the promoted production adapter; archived review sources stay exact.
    for kind in ('terms', 'privacy'):
        code = code.replace('https://isegye-idol.kr/auth/' + kind, '#/' + kind)
    payload = json.dumps(documents(), ensure_ascii=False).replace('</', '<\\/')
    helper = '''
const MEMBER_LEGAL_DOCUMENTS=PAYLOAD;
function operatingLegal(kind){
 if(!Object.hasOwn(MEMBER_LEGAL_DOCUMENTS,kind))return '';
 let body=MEMBER_LEGAL_DOCUMENTS[kind];
 body=body.replace(/href="#(terms-\\d{2}|privacy-\\d{2}|document-top)"/g,(_,id)=>`href="#/${kind}?section=${id}"`)
  .replace(/href="(?:https:\\/\\/isegye-idol\\.kr)?\\/auth\\/(terms|privacy)"/g,(_,id)=>`href="#/${id}"`);
 return wrap(kind,`<div class="legal-shell legal-in-site" id="document-top">${legalNavigation(kind)}<article class="legal-document" data-policy="${kind}" data-version="1.0">${body}</article></div>`);
}
'''.replace('PAYLOAD', payload)
    code = one(code, 'const wrap=(page,html)=>', helper + '\nconst wrap=(page,html)=>')
    return one(code, 'return {record:id=>', 'return {legal:operatingLegal,record:id=>')


def adapt_app(code):
    code = one(code, "else if(root==='guide')html=guideView(r.params);",
               "else if(root==='terms'||root==='privacy')html=ProductionUI.legal(root);else if(root==='guide')html=guideView(r.params);")
    code = one(code, 'mountGallery();ProductionUI.mount(root);',
               'mountGallery();ProductionUI.mount(root);LegalDocuments.mount();')
    return (ROOT / 'site/legal-documents.js').read_text() + '\n' + code


def line(source, prefix):
    rows = [x for x in source.splitlines() if x.startswith(prefix)]
    if len(rows) != 1:
        raise ValueError('Shared shell anchor changed: ' + prefix)
    return rows[0]


def member_bundle(app, legacy, output):
    # Execute only existing pure chrome renderers, never the application/data scripts.
    footer = '\n'.join(line(legacy, p) for p in ('const drawings=', 'const icon=', 'function operatingFooter('))
    chrome = '\n'.join(line(app, p) for p in ('const paths=', 'const icon=', 'const nav=', 'function activeMenu()', 'function shell()'))
    node = ("const esc=x=>String(x), prefs={theme:'dark',favorites:[]}, registry=new Map();\n"
            "const route=()=>({parts:['terms'],params:new URLSearchParams()});\n"
            'const ProductionUI=(()=>{\n' + footer + '\nreturn {footer:operatingFooter};})();\n' + chrome + '\nprocess.stdout.write(shell());')
    shell = subprocess.check_output(['node', '--input-type=module', '-e', node], text=True)
    shell = shell.replace('href="#/terms"', 'href="/account/terms"').replace('href="#/privacy"', 'href="/account/privacy"')
    shell = shell.replace('href="#/', 'href="/#/')
    # The empty saved count is populated locally; no user's list is in this artifact.
    shell = shell.replace('<span class="saved-dot" data-save-count>0</span>', '<span class="saved-dot" data-save-count hidden></span>')
    pages = {}
    for kind, body in documents().items():
        for other in ('terms', 'privacy'):
            body = body.replace('href="/auth/' + other + '"', 'href="/account/' + other + '"')
        tabs = '<nav class="legal-tabs" aria-label="이용 안내 문서">'
        for tab, label in [('terms', '이용약관'), ('privacy', '개인정보처리방침'), ('guide', '팬가이드'), ('about', '사이트소개')]:
            href = '/account/' + tab if tab in ('terms', 'privacy') else '/#/' + tab
            tabs += '<a href="' + href + '"' + (' aria-current="page"' if tab == kind else '') + '>' + label + '</a>'
        tabs += '</nav>'
        content = ('<div class="production-ui" data-operating-page="' + kind + '"><div class="legal-shell legal-in-site" id="document-top">' + tabs
                   + '<article class="legal-document" data-policy="' + kind + '" data-version="1.0">' + body + '</article></div></div>')
        page = one(shell, '<main id="main" class="wrap" tabindex="-1"></main>', '<main id="main" class="wrap" tabindex="-1">' + content + '</main>')
        title = '이용약관' if kind == 'terms' else '개인정보처리방침'
        pages[kind] = ('<!doctype html><html lang="ko" data-theme="dark"><head><meta charset="utf-8">'
                       '<meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">'
                       '<title>' + title + ' · ISEGYE 팬 아카이브</title><script src="/account/legal.js"></script>'
                       '<link rel="stylesheet" href="/account/legal.css"><link rel="stylesheet" href="/auth/account.css"></head><body>'
                       '<div id="app">' + page + '</div><a class="isegye-account-link" href="/auth/login">계정 관리</a>'
                       '<div id="legal-status" class="sr-only" role="status" aria-live="polite"></div></body></html>')
    result = {'schemaVersion': 1, 'documents': pages,
              'sourceHashes': {k: hashlib.sha256(v.encode()).hexdigest() for k, v in documents().items()}}
    (output / 'member-legal.json').write_text(json.dumps(result, ensure_ascii=False) + '\n')
    (output / 'member-legal.js').write_bytes((ROOT / 'site/member-legal.js').read_bytes())
