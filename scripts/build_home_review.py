#!/usr/bin/env python3
"""Home proposal only. Read the generated v0.4 preview; never touch release sources."""
from pathlib import Path
import base64, hashlib, json, os, re, shutil, subprocess
import home_soop_profiles
import compose_schedule
import compose_footer_navigation
import compose_legal_documents
ROOT=Path(__file__).resolve().parents[1]

def replace_once(text, before, after):
    if text.count(before)!=1:raise RuntimeError('Unexpected preview anchor: '+before[:60])
    return text.replace(before,after,1)

def main():
    if os.getenv('DEPLOY_ENV')=='production' or os.getenv('GITHUB_REF')=='refs/heads/main':
        raise RuntimeError('This home proposal must not build for production')
    source=Path(os.getenv('HOME_SOURCE_DIR',str(ROOT/'dist'))).resolve()
    out=ROOT/'home-dist'
    if source==out.resolve() or out.is_symlink():raise RuntimeError('Unsafe review path')
    meta=json.loads((source/'build-info.json').read_text())
    if meta.get('mode')!='preview' or meta.get('catalog',{}).get('songs')!=154:
        raise RuntimeError('Expected generated v0.4 preview')
    if out.exists():shutil.rmtree(out)
    shutil.copytree(source,out)
    shortcut_profiles=home_soop_profiles.build(out)
    app=(out/'src/app.js').read_text();original=app
    a=app.index('function homeView(){');b=app.index('function membersView()',a)
    app=app[:a]+'function homeView(){return homeSimpleView();}\n'+app[b:]
    core=re.sub(r'^export ', '', (ROOT/'home-review/core.js').read_text(), flags=re.M)
    app=replace_once(app,'shell();render();',core+'\nconst HOME_SOOP_PROFILES='+json.dumps(shortcut_profiles)+';\n'+(ROOT/'home-review/ui.js').read_text()+'\nshell();render();')
    app=replace_once(app,"document.getElementById('main').innerHTML=html;","document.documentElement.dataset.homeActive=String(page==='home');\n document.getElementById('main').innerHTML=html;")
    app=replace_once(app,'<b>멤버·음악 개선 검토</b><span>읽기 편하게, 더 가까이</span>','<b>홈 구성 검토</b><span>방송은 그대로, 탐색은 간단하게</span>')
    app=app.replace('어떤 순간을 찾고 있나요?','멤버·음악 검색')
    app=replace_once(app,'<h2>함께 채우는 기록</h2><p>잘못된 정보나 빠진 기록을 발견하셨나요? 공개된 근거와 함께 알려주세요. 확인한 뒤 수정하겠습니다.</p><a class="text-link" href="#/report">정보 제보 · 정정 요청 ${icon(\'arrow\')}</a>',
      '<h2>자료와 출처</h2><p>공개된 원문을 바탕으로 정보를 정리합니다. 각 기록에서 출처와 확인한 내용을 살펴볼 수 있습니다.</p><a class="text-link" href="#/history">활동 기록 보기 ${icon(\'arrow\')}</a>')
    app=replace_once(app,"'지니뮤직')}</p>","'지니뮤직')} · ${external('https://www.sooplive.com/','SOOP')}</p>")
    for name in ('liveHomeView','liveView','liveMount','livePaint'):
        pattern=r'^function '+name+r'\([^\n]*'
        if re.findall(pattern,original,re.M)!=re.findall(pattern,app,re.M):raise RuntimeError('LIVE contract changed: '+name)
    css=(out/'src/styles.css').read_text()+'\n'+(ROOT/'home-review/theme.css').read_text()
    app,css=compose_schedule.compose(app,css,out,meta)
    app,css=compose_footer_navigation.compose(app,css,meta)
    app,css=compose_legal_documents.compose(app,css,meta)
    html=(out/'index.html').read_text()
    if 'content="noindex,nofollow"' not in html:raise RuntimeError('Preview must remain noindex')
    html=re.sub(r'<title>.*?</title>','<title>ISEGYE! · 심플 홈 검토</title>',html)
    html=html.replace('<html ','<html data-home-review="true" ',1)
    (out/'src/app.js').write_text(app);(out/'src/styles.css').write_text(css);(out/'index.html').write_text(html)
    meta.update(commit=os.getenv('GITHUB_SHA',meta['commit']),branch='feature/home-simple',review='home-simple',operatorApprovedDeployment=False)
    meta['homeReview']={'livePreserved':True,'communitySubmissionBanner':False,'videoRefresh':'build-time snapshot, not a new crawler','baseCommit':os.getenv('HOME_BASE_SHA',meta['commit']),'sections':['live','members','recent-videos','music','schedule-history']}
    meta['homeShortcutProfiles']={'source':'SOOP','count':6,'scope':'home-member-shortcuts-only','upperLiveAndMemberProfilesUnchanged':True}
    (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
    parts=[]
    for name in ('data.js','lib.js','portraits.js','app.js'):
        text=(out/'src'/name).read_text();text=re.sub(r'^import .*;\r?\n','',text,flags=re.M)
        parts.append(re.sub(r'^export ','',text,flags=re.M))
    inline='const e=escapeHtml;\n'+'\n'.join(parts)
    portraits={p.stem:'data:image/webp;base64,'+base64.b64encode(p.read_bytes()).decode() for p in (out/'assets/portraits').glob('*.webp')}
    shortcut_inline={p.stem:'data:image/webp;base64,'+base64.b64encode(p.read_bytes()).decode() for p in (out/'assets/soop-profiles').glob('*.webp')}
    inline='const INLINE_SOOP_PROFILES='+json.dumps(shortcut_inline)+';\n'+inline
    inline=inline.replace('src="./assets/soop-profiles/${m.id}.webp?v=${profile.version}"','src="${INLINE_SOOP_PROFILES[m.id]}"')
    inline='const INLINE_PORTRAITS='+json.dumps(portraits)+';\n'+inline
    inline=inline.replace('src="./assets/portraits/${m.id}.webp?v=${PORTRAITS[m.id].version}"','src="${INLINE_PORTRAITS[m.id]}"')
    inline=re.sub(r'\./assets/isegye-group-hero.webp\?v=[0-9a-f]+','data:image/webp;base64,'+base64.b64encode((out/'assets/isegye-group-hero.webp').read_bytes()).decode(),inline)
    offline=html.replace('<link rel="stylesheet" href="./src/styles.css">','<style>'+css+'</style>').replace('<script type="module" src="./src/app.js"></script>','<script type="module">'+inline+'</script>')
    offline=offline.replace('href="./assets/favicon.svg"','href="data:image/svg+xml;base64,'+base64.b64encode((out/'assets/favicon.svg').read_bytes()).decode()+'"')
    for kind,text in [('script',inline),('style',css)]:
        digest=base64.b64encode(hashlib.sha256(text.encode()).digest()).decode()
        offline=offline.replace(kind+"-src 'self'",kind+"-src 'self' 'sha256-"+digest+"'")
    (out/'review.html').write_text(offline)
    subprocess.run(['node','--check',str(out/'src/app.js')],check=True)
    print(json.dumps({'homeReview':True,'commit':meta['commit'],'liveRendererUnchanged':True}))
if __name__=='__main__':main()
