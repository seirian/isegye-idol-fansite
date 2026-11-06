"""Two presentation-only follow-ups: common headings and the operating footer/guide.

No data, ingestion, authentication, LIVE logic or accepted content views change.
The operating UI fragments come from the pinned production build, never a copy
rewritten by hand. Detailed guide documents keep their operational destinations.
"""
import re
from pathlib import Path
import tinycss2


def one(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Polish anchor changed: ' + old[:80])
    return text.replace(old, new, 1)


def between(text, start, end):
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('Operating fragment changed: ' + start)
    return text[text.index(start):text.index(end, text.index(start))]


def adapter(code, operating):
    footer = re.findall(r'<footer class="footer">.*?</footer>', operating)
    if len(footer) != 1:
        raise ValueError('Expected one operating footer')
    helpers = between(operating, 'function guideView()', 'function detailView(')
    # Replace outdated initial-preview introduction with the current site map.
    about=(Path(__file__).resolve().parents[1]/'site/about-current.js').read_text()
    if about.count('function aboutView()')!=1 or 'function privacyView(' in about:
        raise ValueError('Invalid current site introduction')
    helpers += about+'\\n'

    helpers += between(operating, 'function legalNavigation(', 'function legalGuideView(')
    # The canonical public policy endpoints already render the operating documents.
    # Guide record detail routes are also served by production, not the discarded
    # first-review member router. No new document/editor/storage implementation.
    helpers += '''
function operatingGuideLinks(html){
 return html.replaceAll('href="#/record/','href="/#/record/')
  .replaceAll('href="#/terms"','href="https://isegye-idol.kr/auth/terms"')
  .replaceAll('href="#/privacy"','href="https://isegye-idol.kr/auth/privacy"');
}
function operatingGuide(){return wrap('guide',operatingGuideLinks(`<div class="legal-shell legal-in-site legal-guide">${legalNavigation('guide')}${guideView()}</div>`));}
function operatingAbout(){return wrap('about',operatingGuideLinks(`<div class="legal-shell legal-in-site legal-about">${legalNavigation('about')}${aboutView()}</div>`));}
'''
    helpers += 'function operatingFooter(home){return `<div class="production-ui production-footer wrap" data-production-footer><div class="layout" data-home-active="${home}">' + footer[0] + '</div></div>`;}\n'
    code = one(code, 'const wrap=(page,html)=>', helpers + '\nconst wrap=(page,html)=>')
    return one(code, 'return {home:()=>wrap(', 'return {footer:operatingFooter,guide:operatingGuide,about:operatingAbout,home:()=>wrap(')


def app(code):
    footer = re.findall(r'<footer class="footer">.*?</footer>', code)
    if len(footer) != 1:
        raise ValueError('Expected one review footer')
    code = one(code, footer[0], "${ProductionUI.footer(route().parts[0]==='home')}")
    guide = between(code, 'function guideView(p)', 'function settingsView()')
    code = one(code, guide, 'function guideView(){return ProductionUI.guide();}\n')
    return one(code, "else if(root==='review'||root==='about')html=reviewView();",
               "else if(root==='about')html=ProductionUI.about();else if(root==='review')html=reviewView();")


def without_review_footer(css):
    """Remove only discarded review footer selectors, including responsive rules.

    Otherwise those unscoped rules still affect the operating fragment even when
    its original CSS is restored. All non-footer declarations remain unchanged.
    """
    def render(items):
        out = []
        for rule in items:
            if rule.type == 'qualified-rule':
                selectors = tinycss2.serialize(rule.prelude)
                if '.footer' in selectors:
                    groups = [s for s in selectors.split(',') if '.footer' not in s]
                    if groups:
                        out.append(','.join(groups) + '{' + tinycss2.serialize(rule.content) + '}')
                else:
                    out.append(tinycss2.serialize([rule]))
            elif rule.type == 'at-rule' and rule.content is not None and rule.lower_at_keyword in ('media', 'supports', 'layer'):
                out.append('@' + rule.at_keyword + ' ' + tinycss2.serialize(rule.prelude) + '{' +
                           render(tinycss2.parse_rule_list(rule.content)) + '}')
            else:
                out.append(tinycss2.serialize([rule]))
        return ''.join(out)
    return render(tinycss2.parse_stylesheet(css))
