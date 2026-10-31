"""Owner-requested final-shell navigation, with historical build stages preserved."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def compose(app,css,meta):
    anchor='${NAV.map(n=>'
    if app.count(anchor)!=1:raise ValueError('Primary navigation anchor changed')
    app=app.replace(anchor,"${NAV.filter(n=>n.id!=='guide').map(n=>",1)
    old='<div class="footer-links"><a href="https://isegye-idol.kr/auth/terms">이용약관</a><a href="https://isegye-idol.kr/auth/privacy"><strong>개인정보처리방침</strong></a></div>'
    new=old.replace('</div>','<a href="#/guide">팬가이드</a><a href="#/about">사이트소개</a></div>')
    if app.count(old)!=1:raise ValueError('Legal footer anchor changed')
    app=app.replace(old,new,1)
    css+='\n'+(ROOT/'home-review/footer.css').read_text()
    meta['navigationPresentation']={'primaryCount':6,'fanGuideInPrimary':False,
        'footerLinks':['terms','privacy','guide','about'],'fanGuideRoutePreserved':True}
    return app,css
