"""Server role checks and shared read projections; synthetic local sessions only."""
from pathlib import Path
import copy,json,subprocess,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from compose_admin_visibility import project,POLICY,javascript_projection
PHP=r'''
umask(0077);
require $argv[1].'/auth/Store.php';require $argv[1].'/auth/Session.php';require $argv[1].'/auth/View.php';require $argv[1].'/auth/Gateway.php';
$root=$argv[2];$case=json_decode($argv[3],true);$id=str_repeat('a',64);$admin=str_repeat('b',64);
$accounts=$case['role']==='admin'?[$admin=>'admin']:($case['role']==='member'?[$id=>'member']:[]);
$administrator=($case['role']==='admin'||($case['maintenance']??false))?$admin:null;
if($administrator!==null)$accounts[$administrator]='admin';
file_put_contents($root.'/.auth-private/accounts.json',json_encode(['schema'=>1,'administrator'=>$administrator,'accounts'=>(object)$accounts]));
if($case['role']!=='guest'){
 Isegye\Access\Session::start($root.'/.auth-private/sessions');Isegye\Access\Session::login($case['role']==='admin'?$admin:$id);
 if($case['expired']??false)$_SESSION['activity']=time()-7200;
 $_COOKIE['__Host-ISEGYE']=session_id();session_write_close();
}
$_SERVER['HTTP_HOST']='isegye-idol.kr';$_SERVER['HTTPS']='on';$_SERVER['SERVER_PORT']='443';$_SERVER['REQUEST_URI']=$case['path'];$_SERVER['REQUEST_METHOD']=$case['method']??'GET';
$config=['origin'=>'https://isegye-idol.kr','clientId'=>'123456789-fixture.apps.googleusercontent.com','siteKey'=>base64_encode(str_repeat('x',32)),'adminEmailDigest'=>str_repeat('d',64)];
ob_start();(new Isegye\Access\Gateway($root,$argv[1].'/auth',$config))->run();$body=ob_get_clean();if(session_status()===PHP_SESSION_ACTIVE)session_write_close();
echo json_encode(['status'=>http_response_code()?:200,'body'=>$body]);
'''
class AdminVisibility(unittest.TestCase):
 def probe(self,role='guest',path='/src/admin-operations.js',**options):
  with tempfile.TemporaryDirectory(prefix='isegye-visibility-') as tmp:
   root=Path(tmp);private=root/'.auth-private';private.mkdir(mode=0o700);(private/'sessions').mkdir(mode=0o700);(private/'accounts.lock').touch();(private/'accounts.lock').chmod(0o600)
   app=root/'_isegye_releases/r123456abcdef';(app/'src').mkdir(parents=True)
   (root/'.htaccess').write_text('# ISEGYE-AUTH-ROOT-V1 r123456abcdef\n')
   for name,text in {'index.html':'PUBLIC_FIXTURE','build-info.json':'ADMIN_BUILD','src/admin-operations.js':'ADMIN_OPERATIONS','src/data.js':'ADMIN_DIAGNOSTICS','src/public-data.js':'PUBLIC_CATALOG','src/albums-data.js':'ADMIN_ALBUMS','src/public-albums-data.js':'PUBLIC_ALBUMS'}.items():(app/name).write_text(text)
   if options.pop('missing_projection',False):(app/'src/public-data.js').unlink()
   result=subprocess.run(['php','-r',PHP,str(ROOT),tmp,json.dumps(dict(role=role,path=path,**options))],text=True,capture_output=True,timeout=10)
   self.assertEqual(result.stderr,'')
   return json.loads(result.stdout)
 def test_guest_and_member_cannot_download_admin_resources(self):
  for role,status in [('guest',401),('member',403)]:
   for path in POLICY['protectedPaths']:
    with self.subTest(role=role,path=path):
     result=self.probe(role,path);self.assertEqual(result['status'],status);self.assertNotIn('ADMIN_',result['body'])
 def test_role_from_query_string_cannot_grant_access(self):
  for suffix in ('?admin=true','?role=admin&administrator=true','?demo=1','?__Host-ISEGYE=admin'):
   self.assertEqual(self.probe('member','/src/admin-operations.js'+suffix)['status'],403)
 def test_encoded_route_does_not_bypass_authorization(self):
  self.assertEqual(self.probe('member','/src/%61dmin-operations.js')['status'],403)
 def test_admin_has_read_access_but_no_write_endpoint(self):
  for path,body in [('/src/admin-operations.js','ADMIN_OPERATIONS'),('/build-info.json','ADMIN_BUILD')]:
   self.assertEqual(self.probe('admin',path),{'status':200,'body':body})
   self.assertEqual(self.probe('admin',path,method='HEAD')['body'],'')
   self.assertEqual(self.probe('admin',path,method='POST')['status'],405)
 def test_expired_admin_is_denied(self):
  self.assertEqual(self.probe('admin',expired=True)['status'],401)
 def test_public_projection_and_admin_original_selected_by_server(self):
  for path,normal,admin in [('/src/data.js','PUBLIC_CATALOG','ADMIN_DIAGNOSTICS'),('/src/albums-data.js','PUBLIC_ALBUMS','ADMIN_ALBUMS')]:
   for role in ('guest','member'):self.assertEqual(self.probe(role,path)['body'],normal)
   self.assertEqual(self.probe('admin',path)['body'],admin)
 def test_missing_projection_never_falls_back_to_private_file(self):
  response=self.probe('member','/src/data.js',missing_projection=True)
  self.assertEqual(response['status'],404);self.assertNotIn('ADMIN_',response['body'])
 def test_maintenance_gate_is_unchanged(self):
  for role in ('guest','member'):self.assertEqual(self.probe(role,'/',maintenance=True)['status'],503)
  self.assertEqual(self.probe('admin','/')['status'],200)
 def test_python_php_projections_match(self):
  original={'schemaVersion':1,'generatedAt':'2026-11-16T00:00:00Z','sources':[{'id':'berriz-notice','label':'공식 공지','url':'https://berriz.in/ko/isegyeidol/notice/','kind':'official','lastSuccessAt':'2026-11-16T00:00:00Z','lastAttemptAt':'PRIVATE_ATTEMPT','state':'ok','detail':'PRIVATE_DETAIL'}],'channels':[{'key':'official','name':'공식','url':'https://youtube.com','status':'PRIVATE_STATUS','coverageComplete':True}], 'scope':{'collectionHealth':{'state':'PRIVATE_HEALTH'},'videoCoverageComplete':22},'providers':{'youtube':{'state':'missing_key','errors':['PRIVATE_ERROR']}},'tracks':{'rewind':{'charts':{'melon_top100':[{'status':'ranked','rank':6}]},'metadata':{'title':'RE:WIND','artist':'이세계아이돌'},'source':'https://www.melon.com','checkedAt':'2026-11-16T00:00:00Z'}},'publication':{'runId':123},'assets':{'covers':{'a':{'sha256':'a'*64,'path':'albums/asset-cache/a.webp'}}}}
  untouched=copy.deepcopy(original);raw=json.dumps(original,ensure_ascii=False)
  php="require $argv[1];echo \\Isegye\\Access\\Visibility::json(stream_get_contents(STDIN),$argv[2]==='admin'?'admin':null);"
  for role in ('member','admin'):
   result=subprocess.check_output(['php','-r',php,str(ROOT/'auth/Visibility.php'),role],input=raw.encode())
   parsed=json.loads(result);self.assertEqual(parsed,original if role=='admin' else project(original))
   if role=='admin':self.assertEqual(result.decode(),raw)
   else:self.assertNotIn('PRIVATE_',result.decode());self.assertEqual(parsed['tracks'],original['tracks']);self.assertEqual(parsed['assets'],original['assets'])
  self.assertEqual(original,untouched)
 def test_public_projection_preserves_channel_videos_and_provenance(self):
  source={'title':'Official video','url':'https://www.youtube.com/watch?v=y-klhPVFblg','consultedUrl':'https://www.youtube.com','documentUpdatedAt':'2026-11-16','basis':'official'}
  video={'id':'y-klhPVFblg','title':'REBELS','publishedAt':'2026-11-03T09:00:00Z','durationSeconds':192}
  original={'source':source,'channels':[{'key':'official','title':'이세계아이돌','videos':[video],'status':'stale','fullPages':4}], 'sources':[{'id':'collector','state':'ok','lastAttemptAt':'internal','lastSuccessAt':'2026-11-16T00:00:00Z'}]}
  result=project(original)
  self.assertEqual(result['source'],source);self.assertEqual(result['channels'][0]['videos'],[video]);self.assertEqual(result['channels'][0]['title'],'이세계아이돌')
  self.assertNotIn('status',result['channels'][0]);self.assertNotIn('fullPages',result['channels'][0]);self.assertNotIn('state',result['sources'][0])
  php="require $argv[1];echo \\Isegye\\Access\\Visibility::json(stream_get_contents(STDIN),null);"
  actual=subprocess.check_output(['php','-r',php,str(ROOT/'auth/Visibility.php')],input=json.dumps(original,ensure_ascii=False).encode())
  self.assertEqual(json.loads(actual),result)
 def test_complete_channel_catalog_survives_public_projection(self):
  original=json.loads((ROOT/'catalog/videos.json').read_text())
  public=project(original)
  self.assertEqual(len(public['channels']),len(original['channels']))
  for before,after in zip(original['channels'],public['channels']):self.assertEqual(after['videos'],before['videos'])
 def test_projection_preserves_empty_objects_and_unchanged_bytes(self):
  php="require $argv[1];echo \\Isegye\\Access\\Visibility::json(stream_get_contents(STDIN),null);"
  raw='{ "providers": {}, "tracks": {}, "sources": [] }'
  result=subprocess.check_output(['php','-r',php,str(ROOT/'auth/Visibility.php')],input=raw.encode());self.assertEqual(result.decode(),raw)
 def test_script_projection_is_json_only(self):
  code='const CATALOG={"providers":{"youtube":{"state":"secret"}},"title":"<MV>"};\nconst X=()=>1;\n'
  result=javascript_projection(code);self.assertIn('const X=()=>1;',result);self.assertNotIn('secret',result);self.assertIn('\\u003cMV>',result)
 def test_admin_module_uses_explicit_dependencies_and_live_feed(self):
  from compose_admin_visibility import admin_module,function
  private=admin_module(function((ROOT/'albums/flow-view.js').read_text(),'albumProviderPanel'),function((ROOT/'albums/runtime.js').read_text(),'albumFlowFreshness'))
  js=r'''
const vm=require('node:vm'),fs=require('node:fs');
const factory=vm.runInNewContext(fs.readFileSync(0,'utf8').replace('export function createViews','function createViews')+';createViews;',Object.create(null));
let insights={providers:{},domesticCharts:{melon_top100:{state:'ok'}}},apiState='first';
const context={D:{sources:[{id:'official',label:'<private>',state:'ok',lastSuccessAt:'time',lastAttemptAt:'attempt',detail:'<detail>'}],scope:{videoCoverageComplete:22,videoChannelCount:22,historyCheckedAt:'time'}},
 esc:s=>String(s??'').replaceAll('<','&lt;').replaceAll('>','&gt;'),stamp:s=>String(s),badge:s=>'BADGE:'+s,sourceNames:{},
 FeedValidators:{scheduleCollectionMessage:()=>''},patch:()=> '#/song/test?demo=1',
 aiData:()=>({melon:{state:'ok',checkedAt:'time'}}),albumFreeServiceStatus:()=>({state:'ok',label:'연결됨',detail:'API fixture'}),
 albumFreshness:data=>({state:'current',missing:0,chartAt:null,collectedAt:null,publishedAt:null}),
 get albumInsights(){return insights;},get albumApiState(){return apiState;}};
const views=factory(context),results={};
for(const name of Object.keys(views))results[name]=String(name==='providers'?views[name]({id:'rewind'}):name==='flow'?views[name]('melon_top100'):name==='demoLink'?views[name](false,'melon_top100'):views[name]());
if(Object.values(results).some(value=>typeof value!=='string'))throw Error('Invalid view');
if(!results.status.includes('&lt;private&gt;')||results.status.includes('<private>'))throw Error('Escaping lost');
if(!results.providers.includes('곡 정보·멜론 차트 확인'))throw Error('Missing current feed');
insights={providers:{},domesticCharts:{}};apiState='second';
if(!views.providers({id:'rewind'}).includes('차트 재확인 필요')||!views.flow('melon_top100').includes('second'))throw Error('Stale captured feed');
console.log(JSON.stringify({views:Object.keys(views).length,liveFeed:true,isolated:true}));
'''
  result=subprocess.run(['node','-e',js],input=private,text=True,capture_output=True,timeout=10)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(json.loads(result.stdout),{'views':10,'liveFeed':True,'isolated':True})
 def test_role_waits_preserve_strict_page_csp(self):
  for name in ('admin_visibility_browser.py','albums_production_browser.py'):
   text=(ROOT/'tests'/name).read_text()
   self.assertNotIn('page.wait_for_function(',text)
   self.assertIn('time.monotonic()+10',text)
   self.assertIn('page.evaluate(',text)
 def test_no_session_policy_change(self):
  text=(ROOT/'auth/Session.php').read_text();self.assertIn('>= 7200',text);self.assertIn('>= 43200',text)
 def test_bundle_and_feed_reuse_existing_access_role(self):
  self.assertIn("'Visibility.php'",(ROOT/'scripts/build_auth_bundle.py').read_text())
  self.assertIn("AlbumsFeed::serve($this->root, $path, $access['role'])",(ROOT/'scripts/build_albums_host.py').read_text())
  self.assertIn('Visibility::json($raw, $role)',(ROOT/'albums/hosting/AlbumsFeed.php').read_text())

class DeploymentVisibility(unittest.TestCase):
 def test_publisher_checks_role_specific_public_files(self):
  from unittest.mock import patch
  import deploy_google_access as deploy
  payload={'index.html':b'<head></head>APP','src/data.js':b'PRIVATE_DATA','src/public-data.js':b'PUBLIC_DATA','src/admin-operations.js':b'PRIVATE_MODULE','build-info.json':b'PRIVATE_BUILD'}
  def response(url):
   path=url.removeprefix(deploy.d.ORIGIN)
   if path in POLICY['protectedPaths'] or path in ('/ops/batches','/ops/batches/','/ops/batches/data.json','/ops/batches/monitor.js','/ops/batches/monitor.css'):return (401,b'Administrator access required')
   key=path.lstrip('/')
   return (200,deploy.a.public_html(payload[key]) if key=='index.html' else payload[POLICY['publicFiles'].get(key,key)])
  with patch.object(deploy,'status',return_value={'maintenance':False}),patch.object(deploy.d,'http',side_effect=response):
   report={};deploy.verify_public(payload,report);self.assertTrue(report['anonymousAdminDiagnosticsBlocked']);self.assertTrue(report['batchMonitorAnonymousUIAndAPIDenied'])
  with patch.object(deploy,'status',return_value={'maintenance':False}),patch.object(deploy.d,'http',return_value=(200,b'PRIVATE_DATA')):
   with self.assertRaises(deploy.d.Stop):deploy.verify_public(payload,{})
 def test_maintenance_and_admin_diagnostics_remain_distinct(self):
  from unittest.mock import patch
  import deploy_google_access as deploy
  def response(url):
   path=url.removeprefix(deploy.d.ORIGIN)
   return (401,b'Administrator access required') if path in POLICY['protectedPaths'] or path in ('/ops/batches','/ops/batches/','/ops/batches/data.json','/ops/batches/monitor.js','/ops/batches/monitor.css') else (503,'현재 사이트는 공사중입니다.'.encode())
  with patch.object(deploy,'status',return_value={'maintenance':True}),patch.object(deploy.d,'http',side_effect=response):
   report={};deploy.verify_public({},report)
   self.assertTrue(report['anonymousMaintenanceVerified']);self.assertTrue(report['anonymousAdminDiagnosticsBlocked'])
