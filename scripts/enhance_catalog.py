"""Enhance only the LIVE preview with sourced profiles and music metadata."""
from pathlib import Path
import json,re,csv
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[1]

def once(text,old,new):
 if text.count(old)!=1:raise RuntimeError('Catalog template anchor mismatch: '+old[:80])
 return text.replace(old,new,1)

def load_music():
 music=json.loads((ROOT/'catalog/music.json').read_text())
 for row in csv.reader((ROOT/'catalog/covers.tsv').read_text().splitlines(),delimiter='\t'):
  if not row or row[0].startswith('#'):continue
  if len(row)!=7:raise ValueError('Invalid cover row')
  vid,title,members,scope,date,original,context=row
  if not re.fullmatch(r'[A-Za-z0-9_-]{11}',vid):raise ValueError('Invalid video ID')
  item={'id':'cover-'+vid,'title':title,'type':'cover','scope':scope,'members':members.split(','),'date':date,'dateKind':'영상 공개일','format':'커버 영상','videoId':vid,'url':'https://www.youtube.com/watch?v='+vid,'context':context,'sources':['covers']}
  if original:item['originalReference']='https://namu.wiki/w/'+quote(original,safe='/#')
  music['songs'].append(item)
 return music

def enhance(out,app,css,html):
 profiles=json.loads((ROOT/'catalog/members.json').read_text())
 music=load_music()
 videos=json.loads((ROOT/'catalog/videos.json').read_text())
 assert len(profiles['members'])==6
 assert len({s['id'] for s in music['songs']})==len(music['songs'])
 expected={c['key']:c for m in profiles['members'] for c in m['channels']}
 assert len(expected)==21 and set(expected)=={c['key'] for c in videos['channels']}
 for c in videos['channels']:
  assert c['channelId']==expected[c['key']]['channelId'] and len(c['videos'])<=3
  assert all(re.fullmatch(r'[A-Za-z0-9_-]{11}',v['id']) for v in c['videos'])
 data=(out/'src/data.js').read_text().replace("name:'입문·멤버'","name:'멤버 소개'")
 # Existing unrelated records stay intact; the preview owns the new catalog views.
 (out/'src/data.js').write_text(data)
 a=app.index('function membersView()');b=app.index('function memberOptions(',a)
 app=app[:a]+"function membersView(){return catalogMembersView();}\nfunction musicView(params){return catalogMusicView(params);}\n"+app[b:]
 app=once(app,'function detailView(id){','function detailView(id){if(catalogProfiles.has(id))return catalogMemberView(id);')
 app=once(app,"if(page==='record'){","if(page==='song'){html=catalogSongView(parts[1]);title=catalogSongs.get(parts[1])?.title||'곡 없음';active='music';}\n else if(page==='record'){")
 app=app.replace('입문·멤버','멤버 소개').replace('입문 · 멤버','멤버 소개')
 app=app.replace('처음 오셨나요?','멤버 만나기').replace('class="nav-note" href="#/record/getting-started"','class="nav-note" href="#/members"')
 app=app.replace('LIVE 기능 검토','멤버·음악 개선 검토')
 app=app.replace('공식 출처와 GitHub를 방문하면 해당 서비스의 정책이 적용됩니다.','멤버 상세에서는 YouTube 영상의 썸네일을 불러오며 이때 이미지 제공 서버에 IP 주소 등의 접속 정보가 전달될 수 있습니다. 영상은 클릭한 뒤 YouTube에서 재생됩니다. 공식 출처와 GitHub를 방문하면 해당 서비스의 정책이 적용됩니다.')
 payload={'members':profiles['members'],'music':music,'videos':videos}
 embedded=json.dumps(payload,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
 core=re.sub(r'^export ','',(ROOT/'catalog/core.js').read_text(),flags=re.M)
 app=once(app,'shell();render();','const CATALOG='+embedded+';\n'+core+'\n'+(ROOT/'catalog/ui.js').read_text()+'\nshell();render();')
 css+='\n'+(ROOT/'catalog/theme.css').read_text()
 html=once(html,"img-src 'self' data:","img-src 'self' data: https://i.ytimg.com")
 html=once(html,'<html ','<html data-catalog-review="true" ')
 html=re.sub(r'<title>.*?</title>','<title>ISEGYE! · 멤버 소개와 음악 검토</title>',html)
 (out/'src/app.js').write_text(app);(out/'src/styles.css').write_text(css);(out/'index.html').write_text(html)
 meta=json.loads((out/'build-info.json').read_text())
 meta['catalog']={'members':6,'channels':21,'videos':sum(len(c['videos']) for c in videos['channels']),'songs':len(music['songs']),'sourceCheckedAt':music['checkedAt'],'videosCheckedAt':videos['checkedAt'],'videoRefresh':'build-time-public-Atom-feed','types':{k:sum(s['type']==k for s in music['songs']) for k in ('original','cover','remake')}}
 (out/'build-info.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
 return app,css,html
