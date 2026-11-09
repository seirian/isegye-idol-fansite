"""Bounded public source diagnostics only; never print credentials or page bodies."""
from pathlib import Path
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.parse import urlparse,urljoin
from bs4 import BeautifulSoup
import json,re
ROOT=Path(__file__).resolve().parents[1]
HOSTS={'www.music-flo.com','cdn.music-flo.com','www.melon.com','www.genie.co.kr','music.bugs.co.kr'}
class Redirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,url):
        if urlparse(url).scheme!='https' or urlparse(url).hostname not in HOSTS:raise ValueError('Redirect refused')
        return super().redirect_request(req,fp,code,msg,headers,url)
def fetch(url):
    if urlparse(url).scheme!='https' or urlparse(url).hostname not in HOSTS:raise ValueError('Host refused')
    with build_opener(Redirect).open(Request(url,headers={'User-Agent':'ISEGYE-Archive-Review/1.1'}),timeout=15) as r:
        raw=r.read(8000001)
        if len(raw)>8000000:raise ValueError('Oversized response')
        return raw.decode('utf-8',errors='replace')
if __name__=='__main__':
    out=ROOT/'test-results/albums-domestic';out.mkdir(parents=True,exist_ok=True);report={}
    for host in ('www.music-flo.com','www.melon.com','www.genie.co.kr','music.bugs.co.kr'):
        try:(out/(host+'-robots.txt')).write_text(fetch('https://'+host+'/robots.txt'))
        except Exception as exc:report[host]=type(exc).__name__
    try:
        html=fetch('https://www.music-flo.com/');soup=BeautifulSoup(html,'html.parser')
        src=next(n['src'] for n in soup.select('script[src]') if n['src'].endswith('/main.js'))
        text=fetch(urljoin('https://www.music-flo.com/',src));(out/'flo-client.js').write_text(text);report['floClient']=src
        if '/chart/track/' in text:
            for name,url in [('flo-chart','https://www.music-flo.com/api/meta/v1/chart/track/1'),('flo-search','https://www.music-flo.com/api/search/v2/search?keyword=ISEGYE%20IDOL&searchType=TRACK&size=50')]:
                try:
                    body=fetch(url);json.loads(body);(out/(name+'.json')).write_text(body);report[name]='json_received'
                except Exception as exc:report[name]=type(exc).__name__
    except Exception as exc:report['flo']=type(exc).__name__
    (out/'public-source-check.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report))
