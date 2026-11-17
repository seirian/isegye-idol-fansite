from pathlib import Path
import hashlib,json,shutil,sys,zipfile
ROOT=Path.cwd()
def replace(name,old,new):
 p=ROOT/name;s=p.read_text()
 if s.count(old)!=1:raise ValueError('Changed integration anchor: '+name)
 p.write_text(s.replace(old,new))
for src,dst in {
 'guyso-collector.py':'scripts/collect_album_peak_fallback.py',
 'guyso-publisher.py':'scripts/migrate_guyso_peaks.py',
 'guyso-parser-tests.py':'tests/test_albums_peak_fallback.py',
 'guyso-migration-tests.py':'tests/test_guyso_peak_migration.py',
 'guyso-browser.py':'tests/guyso_peaks_browser.py',
 'guyso-frontend.js':'albums/peak-fallback.js',
 'guyso-js-tests.js':'tests/albums-peak-fallback.test.js',
 'guyso-migration-workflow.yml':'.github/workflows/guyso-peaks-migration.yml',
 'guyso-reference-doc.md':'docs/GUYSO_PEAK_REFERENCE_20261118.md',
}.items():shutil.copyfile(ROOT/'repair'/src,ROOT/dst)
p=ROOT/'albums/ui.js';s=p.read_text();a=s.index('function aiPeaks(s) {');b=s.index('function aiStreaming(s) {',a)
s=s[:a]+(ROOT/'repair/guyso-peaks-view.js').read_text()+s[b:];p.write_text(s)
replace('scripts/collect_album_records.py',"    if url == 'https://isegyechart.com/api/song-selector-list': return url\n",'')
replace('scripts/prepare_album_release.py','    return path\n',"    from collect_album_peak_fallback import apply_reviewed\n    data=json.loads(path.read_text());apply_reviewed(data)\n    path.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\\n')\n    return path\n")
for name,python in (('.github/workflows/ci.yml','/tmp/release-tools/bin/python'),('.github/workflows/production.yml','/tmp/archive-browser-tests/bin/python')):
 old='          '+python+' tests/albums_production_browser.py\n'
 replace(name,old,old+'          '+python+' tests/guyso_peaks_browser.py\n')
replace('tests/albums_browser.py',"""        origin=record.get('melonPeaks',{});secondary=record.get('melonPeakFallback',{})
        if key=='daily' and type(origin.get('dailyBestRank')) is int:
          expected.append(str(origin['dailyBestRank'])+'위');sources.append('melon_original')
        else:
          rank=secondary.get('records',{}).get(key,{}).get('rank')
          expected.append(str(rank)+'위' if type(rank) is int else '—');sources.append('secondary_observation' if type(rank) is int else 'unknown')
""","""        secondary=record.get('melonPeakFallback',{})
        rank=secondary.get('records',{}).get(key,{}).get('rank')
        expected.append(str(rank)+'위' if type(rank) is int else '—');sources.append('guyso_observation' if secondary else 'unknown')
""")
replace('tests/albums_production_browser.py',"""    rank=item.get('melonPeaks',{}).get('dailyBestRank') if key=='daily' else None
    if type(rank) is not int:rank=item.get('melonPeakFallback',{}).get('records',{}).get(key,{}).get('rank')
""","""    rank=item.get('melonPeakFallback',{}).get('records',{}).get(key,{}).get('rank')
""")
old="   check(sid+' seven peaks match snapshot',page.locator('.ai-peak strong').all_text_contents()==values)\n"
replace('tests/albums_production_browser.py',old,old+"""   check(sid+' no per-card source links',page.locator('.ai-peak a, .ai-peak-source').count()==0)
   details=page.locator('.ai-peaks details');expect(details.locator('summary')).to_have_text('최고 성적 출처와 확인 시각')
   details.locator('summary').click()
   if item.get('melonPeakFallback'):
    check(sid+' Guyso attribution only in details',details.locator('tbody a').count()==7 and '이세계차트' not in page.locator('.ai-peaks').inner_text())
""")
p=ROOT/'albums/accepted.json';d=json.loads(p.read_text());names=['albums/ui.js','albums/peak-fallback.js'];old={n:d['sourceHashes'][n] for n in names};new={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in names}
d['sourceHashes'].update(new);d['amendments'].append({'id':'guyso-peaks-20261118','scope':'Owner-requested removal of per-card source labels, preserved expandable provenance, and real seven-category Guyso reference migration for all linked songs. No chart-history changes.','previousSourceHashes':old,'sourceHashes':new})
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
sys.path.insert(0,str(ROOT/'scripts'));import collect_album_peak_fallback as c
raw=Path('guyso-source-evidence.zip').read_bytes();digest='d5e96d12958d874d9fa5cf0263ffb46cd8724c638b46807a845f1d00bbab005a'
if hashlib.sha256(raw).hexdigest()!=digest:raise ValueError('Changed source archive')
with zipfile.ZipFile('guyso-source-evidence.zip') as z:
 report=json.loads(z.read('report.json'))
 dataset={'schemaVersion':1,'sourceType':c.TYPE,'evidenceRun':44121379741,'evidenceArchiveSha256':digest,'tracks':{},'excluded':report['excluded']}
 for sid,entry in report['tracks'].items():
  page=z.read(sid+'.html')
  if entry['state']!='ok' or hashlib.sha256(page).hexdigest()!=entry['sha256']:raise ValueError('Changed source page')
  m=entry['identity'];reference=c.parse_reference(page,m,m['trackId'],entry['checkedAt'])
  dataset['tracks'][sid]={'identity':m,'reference':reference}
 out=(json.dumps(dataset,ensure_ascii=False,separators=(',',':'))+'\n').encode()
 if hashlib.sha256(out).hexdigest()!=c.REVIEW_SHA256:raise ValueError('Dataset differs from local review')
 c.REVIEW_PATH.parent.mkdir(parents=True,exist_ok=True);c.REVIEW_PATH.write_bytes(out)
print(json.dumps({'tracks':len(dataset['tracks']),'rankCount':sum(v['rank'] is not None for e in dataset['tracks'].values() for v in e['reference']['records'].values()),'datasetSha256':c.REVIEW_SHA256}))
