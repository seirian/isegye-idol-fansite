from pathlib import Path
import hashlib, json

def sub(path, old, new, *, count=1):
    p = Path(path); text = p.read_text(); hits = text.count(old)
    if hits != count: raise RuntimeError(f'{path}: {old[:90]!r}: expected {count}, got {hits}')
    p.write_text(text.replace(old, new))

def replace_line(path, part, newline):
    text=Path(path).read_text(); lines=[s for s in text.splitlines() if part in s]
    if len(lines)!=1: raise ValueError((path,part,lines))
    sub(path,lines[0],newline)

# The shared strip is generated once. Keep the announcement above the header.
f='scripts/build_home_review.py'
strip='<div class="preview-strip"><b>멤버·음악 개선 검토</b><span>읽기 편하게, 더 가까이</span><a href="#/about">사이트 소개 ${icon(\'arrow\')}</a></div>'
replace_line(f,"'<b>홈 구성 검토</b><span>",f'    app=replace_once(app,{strip!r},\'\')')
f='scripts/build_release_home.py'; new_anchor='href="#/about">사이트소개</a>'
sub(f,"'<b>홈 구성 검토</b>', 'function homeSimpleView()'",repr(new_anchor)+", 'function homeSimpleView()'")
sub(f,"    text = text.replace('<b>홈 구성 검토</b><span>방송은 그대로, 탐색은 간단하게</span>',\n                        '<b>공개 베타</b><span>방송부터 새 영상, 음악까지</span>')", "    if '<div class=\"preview-strip\">' in text:\n        raise RuntimeError('Retired site-wide banner is present')")
# Four destinations share the existing tabs and the actual About content.
f='legal/ui.js';sub(f,"['guide','팬가이드']]","['guide','팬가이드'],['about','사이트소개']]")
sub(f,'function legalDocumentView(kind){', '''function legalAboutView(){
 return `<div class="legal-shell legal-in-site legal-about">${legalNavigation('about')}${aboutView()}</div>`;
}
function legalDocumentView(kind){''')
f='scripts/compose_legal_documents.py';sub(f,"    app=once(app,'guide:guideView','guide:legalGuideView')", "    app=once(app,'guide:guideView','guide:legalGuideView')\n    app=once(app,'about:aboutView','about:legalAboutView')")
f='scripts/compose_footer_navigation.py';sub(f,'<a href="#/guide">팬가이드</a></div>', '<a href="#/guide">팬가이드</a><a href="#/about">사이트소개</a></div>');sub(f,"['terms','privacy','guide']","['terms','privacy','guide','about']")
f='auth/View.php';sub(f,"        $tabs .= '</nav>';",'''        $tabs .= '<a href="/#/guide">팬가이드</a><a href="/#/about">사이트소개</a></nav>';'''); sub(f,'<a href="/#/guide">팬가이드</a></nav></footer>', '<a href="/#/guide">팬가이드</a><a href="/#/about">사이트소개</a></nav></footer>')
f='auth/legal.css'; p=Path(f);p.write_text(p.read_text()+'\n/* Keep space between the header and the first tab row without a banner. */\n.legal-in-site{padding-block-start:clamp(14px,2vw,24px)}\n')
# Keep immutable historical release checks intact. Change expectations for the current build only.
f='tests/test_home_release.py';sub(f,'<b>홈 구성 검토</b><span>방송은 그대로, 탐색은 간단하게</span>',new_anchor);sub(f,"self.assertIn('공개 베타', (out / 'src/app.js').read_text())", "self.assertNotIn('preview-strip', (out / 'src/app.js').read_text())");sub(f,"self.assertIn('홈 구성 검토', (src / 'src/app.js').read_text())", "self.assertIn('사이트소개', (src / 'src/app.js').read_text())")
f='tests/test_legal_shell.py';sub(f,'guide:guideView,privacy:privacyView','guide:guideView,about:aboutView,privacy:privacyView');sub(f,"  self.assertIn('guide:legalGuideView',out)","  self.assertIn('guide:legalGuideView',out)\n  self.assertIn('about:legalAboutView',out)")
for f in ('tests/legal_shell_browser.py','tests/schedule_toolbar_browser.py','tests/release_v04_browser.py','tests/auth/production_browser.py'):
    p=Path(f);t=p.read_text(); old="['이용약관','개인정보처리방침','팬가이드']";assert old in t,f
    t=t.replace(old,"['이용약관','개인정보처리방침','팬가이드','사이트소개']").replace("URL+'#/guide']","URL+'#/guide',URL+'#/about']").replace("page.locator('.footer-links a').count()==3","page.locator('.footer-links a').count()==4").replace('footer three links','footer four links').replace('footer remains three links','footer remains four links').replace('guide three buttons','guide four buttons');p.write_text(t)
f='tests/release_v04_browser.py';replace_line(f,"check('public beta not review label'", "            check('retired common banner absent from release',page.locator('.preview-strip').count()==0)")
f='tests/legal_shell_browser.py';anchor="  check('guide tabs precede original heading'";t=Path(f).read_text();assert t.count(anchor)==1
new='''  # Visit each information page through real links; each has one selected tab.
  for dest in ('about','terms','privacy','guide'):
   page.locator(f'.legal-tabs a[href="#/{dest}"]').click();settle(page)
   check(dest+' overview and tabs',page.url==URL+'#/'+dest and page.locator('.legal-tabs a').all_text_contents()==['이용약관','개인정보처리방침','팬가이드','사이트소개'])
   check(dest+' current destination',page.locator('.legal-tabs [aria-current="page"]').count()==1 and page.locator('.legal-tabs [aria-current="page"]').get_attribute('href')=='#/'+dest)
   check(dest+' no announcement strip',page.locator('.preview-strip').count()==0 and page.locator('.announcement').count()==1)
   if dest=='about':
    check('existing about content preserved',page.locator('#main .about-grid').count()==1)
    page.screenshot(path=str(OUT/'about-navigation-dark-desktop.png'),full_page=False)
    page.set_viewport_size({'width':320,'height':844});settle(page)
    check('all four about tabs fit on mobile',all(a.is_visible() for a in page.locator('.legal-tabs a').all()) and page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.screenshot(path=str(OUT/'about-navigation-dark-mobile.png'),full_page=False)
    page.set_viewport_size({'width':1440,'height':1000})
  page.locator('.footer-links a[href="#/about"]').click();settle(page)
  check('About reachable from footer',page.url.endswith('#/about'))
  page.locator('.legal-tabs a[href="#/guide"]').click();settle(page)
''';Path(f).write_text(t.replace(anchor,new+anchor))
f='review/home-release.json';p=Path(f);meta=json.loads(p.read_text()); changed=('scripts/build_home_review.py','scripts/compose_footer_navigation.py','scripts/compose_legal_documents.py','legal/ui.js','auth/legal.css','auth/View.php');assert all(k in meta['sourceHashes'] for k in changed)
for k in changed:meta['sourceHashes'][k]=hashlib.sha256(Path(k).read_bytes()).hexdigest()
if 'scripts/build_release_home.py' in meta['sourceHashes']:meta['sourceHashes']['scripts/build_release_home.py']=hashlib.sha256(Path('scripts/build_release_home.py').read_bytes()).hexdigest()
p.write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
