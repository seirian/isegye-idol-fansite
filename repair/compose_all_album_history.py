"""Isolated review composer; only its explicit generated files may be promoted."""
from pathlib import Path
import hashlib,json
R=Path(__file__).resolve().parents[1]
def once(text,old,new):
    if text.count(old)!=1:raise ValueError('Composition anchor changed: '+old[:80])
    return text.replace(old,new,1)

p=R/'albums/flow.js';s=p.read_text()
if 'function albumArchiveWindow' in s:raise ValueError('Already composed')
p.write_text(s+(R/'repair/archive-helpers.js').read_text())
p=R/'albums/flow-view.js';s=p.read_text()
s=once(s,"const p=route().params, hours=aiHours(), kind=albumFlowKind(p.get('metric'),aiData(s.id),hours);\n  const demo=p.get('demo')==='1', end=Date.now();\n  const historical=demo?null:albumHistoricalReference(aiData(s.id),kind);", "const p=route().params, item=aiData(s.id), window=albumArchiveWindow(item,p);\n  const hours=window.hours, end=window.end, kind=albumFlowKind(p.get('metric'),item,hours,end);\n  const demo=p.get('demo')==='1';\n  const historical=demo?null:(albumArchiveReference(item,kind)||albumHistoricalReference(item,kind));")
s=once(s,'albumDemoSeries(hours,end):aiHistory(s,kind)','albumDemoSeries(hours,end):albumArchiveRows(item,kind,aiHistory(s,kind))')
s=once(s,'aria-current="${hours===h}"','aria-current="${!window.enabled&&hours===h}"')
s=once(s,"</a>`).join('')}</div></div>${demo?", "</a>`).join('')}${window.available?`<a href=\"${esc(patch({range:'history',metric:kind,demo:null}))}\" aria-current=\"${window.enabled}\">발매 이후</a>`:''}</div></div>${window.available&&window.enabled?`<form class=\"ai-history-controls\" data-album-history-form><label>과거 기록 종료일 <input type=\"date\" name=\"historyEnd\" min=\"${esc(window.minDate)}\" max=\"${esc(window.maxDate)}\" value=\"${esc(window.date)}\" required></label><button type=\"submit\">30일 구간 보기</button><p class=\"ai-footnote\">발매 시각부터 확보한 기록입니다. 종료일을 바꾸어 과거 구간을 볼 수 있습니다. HOT100은 발매 후 100일 대상 차트이며, 빈칸을 차트 밖으로 단정하지 않습니다.</p></form>`:''}${demo?")
s=once(s,"최근 ${hours===24?'24시간':hours===168?'7일':'30일'}", "${window.enabled?'발매 이후 기록 · 선택한 30일':`최근 ${hours===24?'24시간':hours===168?'7일':'30일'}`}")
s=once(s,"${historical?'멜론 직접 수집 및 가이섬 과거 기록':'멜론 원본 수집값'}", "${historical?'기존 검증 기록 및 가이섬 과거 기록':'멜론 원본 수집값'}")
s=once(s,"${kind==='melon_top100'?'11/10 16:00은 원자료 불완전으로 미확인':'02~06시는 원자료에 시간별 차트가 없는 구간'}", "${historical.archive?'원자료로 확인한 시점만 표시 · 미확인 구간은 추정하지 않음':kind==='melon_top100'?'11/10 16:00은 원자료 불완전으로 미확인':'02~06시는 원자료에 시간별 차트가 없는 구간'}")
s+="\n// Local date navigation never requests the third-party source from visitors.\ndocument.addEventListener('submit',event=>{\n  const form=event.target;\n  if(!form.matches?.('[data-album-history-form]'))return;\n  event.preventDefault();\n  const date=new FormData(form).get('historyEnd');\n  if(typeof date==='string'&&/^\\d{4}-\\d{2}-\\d{2}$/.test(date))location.hash=patch({range:'history',historyEnd:date,demo:null});\n});\n"
p.write_text(s)
p=R/'albums/flow.css';p.write_text(p.read_text()+'\n.ai-history-controls{display:flex;align-items:center;flex-wrap:wrap;gap:.75rem;margin:1rem 0}.ai-history-controls label{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}.ai-history-controls input,.ai-history-controls button{font:inherit;padding:.5rem .75rem;border:1px solid var(--line);border-radius:.5rem;background:var(--surface);color:inherit}.ai-history-controls .ai-footnote{flex-basis:100%;margin:0}\n')
p=R/'scripts/daily_albums.py';s=p.read_text();target="    data['scope'] = 'production album observations; hourly refresh outside KST 01:00-06:59'"
s=once(s,target,"    # Permanent compact history plus recent repair; no third-party requests.\n    from album_history_backfill import apply as repair_catalog, CUTOFF as archive_cutoff\n    if clock(data['generatedAt']) >= archive_cutoff:\n        repair_catalog(data, previous=previous, at=clock(data['generatedAt']), strict=False)\n"+target);p.write_text(s)
p=R/'scripts/promote_albums.py';s=p.read_text();s=once(s,'${graphic}${demo?"":albumFlowFreshness(kind)}','${graphic}${(demo||window.enabled)?"":albumFlowFreshness(kind)}');p.write_text(s)
p=R/'albums/accepted.json';d=json.loads(p.read_text());names=['albums/flow.js','albums/flow-view.js','albums/flow.css'];old={n:d['sourceHashes'][n] for n in names};new={n:hashlib.sha256((R/n).read_bytes()).hexdigest() for n in names};d['sourceHashes'].update(new);d['amendments'].append({'id':'catalog-history-20261116','scope':'Owner-requested release-to-cutoff history for the 16 registered albums/works; add dated history controls and source attribution; preserve recent UI and collection schedules.','previousSourceHashes':old,'sourceHashes':new});p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
p=R/'tests/albums_production_browser.py';s=p.read_text();s=once(s,"  check('no JavaScript exceptions',not errors)",(R/'repair/browser-history-checks.txt').read_text()+"  check('no JavaScript exceptions',not errors)");p.write_text(s)
print('Explicit historical UI and retention amendments composed locally; no deployment')
