"""Exercise the real local TLS/session gate with synthetic identities only."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/review_host_browser.py').read_text()
assert hashlib.sha256(source.encode()).hexdigest()=='fbce2b92873b3b1d2b6594bff00e3f9d0bc242642d00c580d2e1bb48b00cfb79', 'Reviewed fixture changed'
source=source.replace('review-1st-dist','fanmade-dist').replace('review-1st','review-fanmade').replace('deploy_review_1st','deploy_fanmade').replace("test-results/review-host","test-results/fanmade-host")
source=source.replace('오늘의 이세돌','팬메이드')
old="""            op.locator('#header-query').fill('릴파 11월 3일');op.locator('#header-query').press('Enter')
            expect(op.locator('#global-query')).to_have_value('릴파 11월 3일')
            check('authorized review search finds restored notice','오늘은 휴방입니다!' in op.locator('#main').inner_text())"""
new="""            op.locator('#query').fill('작은 무대');op.locator('#query').press('Enter')
            expect(op.locator('[data-work]')).to_have_count(1)
            op.locator('.card-link').click()
            expect(op.locator('h1')).to_have_text('손으로 만든 작은 무대')
            op.locator('.detail-actions [data-save]').click()
            check('fanmade save through protected gate',op.locator('#saved-count').inner_text()=='1')"""
assert source.count(old)==1
source=source.replace(old,new)
source=source.replace("count()==6","count()==8").replace('#/home','#/fanmade')
# Verify the previously published previews still resolve after the new hook.
marker='    signing=base/\'signing.pem\';cert=base/\'cert.pem\'""")'
extra="""    for name,owner in [('review-1st',b'isegye-first-review:v1'+bytes([10])),('review-2nd',b'isegye-second-review:v1'+bytes([10])),('review-albums',b'isegye-albums-review:v1'+bytes([10]))]:
        folder=base/('.'+name);folder.mkdir(mode=0o700);rel='p'+'1'*12
        target=folder/'releases'/rel;target.mkdir(parents=True)
        content=('PRESERVED_'+name).encode();metadata=b'{}'
        (folder/'.owner').write_bytes(owner)
        (folder/'active.json').write_text(json.dumps({'release':rel,'sha256':hashlib.sha256(content).hexdigest(),'metadataSha256':hashlib.sha256(metadata).hexdigest(),**({'dataSha256':hashlib.sha256(b'{}').hexdigest()} if name=='review-albums' else {})}))
        (target/'review.html').write_bytes(content);(target/'build-info.json').write_bytes(metadata)
        if name=='review-albums':(target/'insights.json').write_bytes(b'{}')
"""
assert source.count(marker)==1
source=source.replace(marker,extra+marker)
anchor="            check('production root remains separate'"
index=source.index(anchor)
source=source[:index]+"""            for name in ('review-1st','review-2nd','review-albums'):
                response=owner.request.get(url+'/'+name+'/')
                check('existing preview preserved '+name,response.status==200 and response.body()==('PRESERVED_'+name).encode())
            check('existing albums data preserved',owner.request.get(url+'/review-albums/api/insights').body()==b'{}')
"""+source[index:]
# The inner auth fixture needs hashlib for its synthetic preview files.
source=source.replace('    import sys\n','    import sys,hashlib\n')
exec(compile(source,str(ROOT/'tests/review_host_browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/review_host_browser.py')})
