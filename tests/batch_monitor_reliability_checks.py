"""Render stale, failed and partial inspections under the exact protected gateway."""
from datetime import datetime, timedelta, timezone
from playwright.sync_api import expect
import copy
import batch_monitor_snapshot as m
from batch_monitor_health import inspection_health


def verify(check, page, install, fixture, out):
    now=datetime.now(timezone.utc)
    old=fixture(now-timedelta(hours=2))
    install(old);page.locator('#refresh').click()
    expect(page.locator('#health')).to_contain_text('모니터링 갱신 지연')
    check('monitor stale historical success remains visible',page.locator('#rows').get_by_text('마지막 반영 완료',exact=True).count()>0)
    check('monitor stale current success count is zero',page.locator('#summary [data-state="healthy"] strong').inner_text()=='0')
    check('monitor stale has explicit per-row check delay',page.locator('#rows .freshness').get_by_text('최신 점검 지연',exact=True).count()==8)
    check('monitor stale retains dated verification',page.locator('#rows .last-verified').filter(has_text='정상 반영 확인').count()>0)
    page.screenshot(path=str(out/'reliability-stale-desktop.png'),full_page=True)

    broken=fixture(now)
    for row in broken['batches']:
        row.update(dataState='unknown',state='unknown',listingComplete=False,
                   inspectionError='execution_query_failed',lastVerifiedResult=None)
    broken['collectorHealth']=inspection_health(broken)
    m.merge_observations(old,broken)
    install(broken);page.locator('#refresh').click()
    expect(page.locator('#health')).to_contain_text('모니터링 점검 실패')
    check('monitor inspection failure count is explicit','조회 실패 8' in page.locator('#inspection-info').inner_text())
    check('monitor failed inspection preserves historical verification',page.locator('#rows .last-verified').filter(has_text='정상 반영 확인').count()>0)
    page.get_by_role('button',name='음반 · 멜론 차트 상세',exact=True).click()
    check('monitor last verified evidence has separate detail section',page.locator('#detail-body').get_by_text('마지막으로 검증된 정상 결과',exact=True).count()==1)
    page.keyboard.press('Escape')
    page.locator('#theme').select_option('dark');page.screenshot(path=str(out/'reliability-failed-dark.png'),full_page=True)
    page.set_viewport_size({'width':390,'height':844})
    check('monitor failed inspection mobile readable',page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    page.screenshot(path=str(out/'reliability-failed-mobile.png'),full_page=True)
    page.set_viewport_size({'width':1440,'height':1000});page.locator('#theme').select_option('light')

    current=fixture(datetime.now(timezone.utc))
    album=current['batches'][0];album['nextDueAt']=(now-timedelta(minutes=1)).isoformat()
    install(current);page.locator('#refresh').click()
    expect(page.locator('#rows .freshness').get_by_text('새 회차 확인 대기',exact=True)).to_have_count(1)
    check('monitor next slot does not erase preceding verified publication',page.locator('#rows tr').filter(has_text='음반 · 멜론 차트').get_by_text('마지막 반영 완료',exact=True).count()==1)

    observed_failure=fixture(datetime.now(timezone.utc))
    for row in observed_failure['batches']:row.update(dataState='attention',state='attention',listingComplete=True)
    observed_failure['collectorHealth']=inspection_health(observed_failure)
    install(observed_failure);page.locator('#refresh').click()
    expect(page.locator('#health')).to_contain_text('모니터링 자료 수집 완료')
    check('monitor actual batch failures not called inspector outage',page.locator('#rows').get_by_text('반영 확인 필요',exact=True).count()==8)
    install(fixture(datetime.now(timezone.utc)));page.locator('#refresh').click();expect(page.locator('#refresh')).to_be_enabled()
