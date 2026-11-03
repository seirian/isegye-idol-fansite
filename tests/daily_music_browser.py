from pathlib import Path
import json,os
from playwright.sync_api import sync_playwright
url=os.environ['DAILY_TEST_URL']; out=Path(os.environ['DAILY_OUT']);out.mkdir(parents=True,exist_ok=True)
checks=[]
def check(name,test):
    checks.append({'name':name,'passed':bool(test)})
    if not test:raise AssertionError(name)
row=dict(videoId='TESTmusic_1',channelKey='c14',members=['lilpa'],title='일배치 검증용 곡',type='cover',kind='official_video',publishedAt='2026-11-01T18:15:00Z',checkedAt='2026-11-02T10:00:00Z')
medley=dict(row, videoId='lFgCjRoFjyU',channelKey='c2',members=['ine','jingburger','lilpa','jururu','gosegu','viichan'],title='Across Dimensions',type='album_medley',publishedAt='2026-11-02T09:00:14Z'); clip=dict(medley,videoId='CLIPmusic_1',type='music_clip',title='검증용 스페셜클립')
with sync_playwright() as p:
    b=p.chromium.launch(executable_path=os.getenv('CHROMIUM_PATH') or None)
    for w in (390,1440):
        c=b.new_context(viewport={'width':w,'height':900},locale='ko-KR');page=c.new_page();err=[];page.on('pageerror',lambda x:err.append(str(x)))
        page.route('**/api/music',lambda r:r.fulfill(json={'schemaVersion':1,'feed':'daily-music','generatedAt':row['checkedAt'],'rows':[row,row,medley,medley,clip]}))
        page.goto(url+'#/music?q=일배치');card=page.locator('[data-song="daily-TESTmusic_1"]');card.wait_for(timeout=15000);check(str(w)+' exactly one card',card.count()==1)
        card.locator('a').first.click();page.locator('.catalog-song-detail').wait_for();check('public upload date not album date','영상 공개일' in page.locator('.catalog-facts').inner_text());check('fixed video link',page.locator('.catalog-song-detail a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v=TESTmusic_1');check('credited artist','릴파' in page.locator('.catalog-profile-description').inner_text())
        for sample,label in ((medley,'앨범 하이라이트 메들리'),(clip,'음악 스페셜클립')):
            page.goto(url+'#/music?type='+sample['type']);card=page.locator('[data-song="daily-'+sample['videoId']+'"]');card.wait_for();check(f'{w} {sample["type"]} unique card',card.count()==1 and label in card.inner_text());card.locator('a').first.click();page.locator('.catalog-song-detail').wait_for();link=page.locator('.catalog-song-detail a.button.primary');check('correct media type and canonical destination',label in link.inner_text() and link.get_attribute('href')=='https://www.youtube.com/watch?v='+sample['videoId']);check('date means public video upload','영상 공개일' in page.locator('.catalog-facts').inner_text())
        page.goto(url+'#/song/rewind');check('original record still accessible',page.locator('.catalog-song-detail a.button.primary').get_attribute('href')=='https://www.youtube.com/watch?v=fgSXAKsq-Vo');check('no JS error',not err);c.close()
    b.close()
(out/'result.json').write_text(json.dumps({'passed':sum(x['passed'] for x in checks),'total':len(checks),'checks':checks},ensure_ascii=False))
