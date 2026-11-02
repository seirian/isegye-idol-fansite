import json
from pathlib import Path
import cafe_batch as cb

def pack(d,f,c):
    d=dict(d);rows=f.get('verified',[])
    if rows and (f.get('from')!=d['from'] or f.get('seriesReference')!=22137397 or f.get('state')!='verified_series_articles'):raise ValueError('wrong series provenance')
    d['fanSeries']=rows;d['fanCheckedAt']=f.get('checkedAt',d['checkedAt']);d['fanCards']=c.get('cards',{});d['cardCheckedAt']=c['checkedAt'];d['fanWindowComplete']=False
    if not set(d['fanCards'])<={str(r['articleId']) for r in rows}:raise ValueError('cards from unreviewed article')
    return cb.validate(d)
if __name__=='__main__':
    read=lambda n:json.loads(Path(n).read_text());out=pack(read('cafe-review.json'),read('fan-review.json'),read('fan-cards.json'))
    Path('cafe-window.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'boards':out['boards'],'series':len(out['fanSeries']),'memberSections':sum(len(v) for v in out['fanCards'].values())}))
