import {cp,mkdir,readFile,writeFile,rm} from 'node:fs/promises';
import {resolve} from 'node:path';
import {RECORDS,SOURCES,MEMBERS,SITE} from '../src/data.js';
import {validateContent} from '../src/lib.js';
const errors=validateContent(RECORDS,SOURCES,MEMBERS);
if(errors.length)throw new Error(errors.join('\n'));
const root=resolve(import.meta.dirname,'..'),out=resolve(root,'dist');
const production=process.env.DEPLOY_ENV==='production';
if(production&&process.env.GITHUB_REF&&process.env.GITHUB_REF!=='refs/heads/main')throw new Error('Production builds are restricted to main.');
await rm(out,{recursive:true,force:true});await mkdir(out,{recursive:true});
for(const name of ['index.html','src','assets','robots.txt','.nojekyll'])await cp(resolve(root,name),resolve(out,name),{recursive:true});
if(production){
 let html=await readFile(resolve(out,'index.html'),'utf8');
 html=html.replace('content="noindex,nofollow"','content="index,follow"');
 html=html.replace('</head>','  <link rel="canonical" href="https://isegye-idol.kr/">\n</head>');
 await writeFile(resolve(out,'index.html'),html);
 await writeFile(resolve(out,'robots.txt'),'User-agent: *\nAllow: /\n');
 // Only the production bundle changes wording; develop remains a noindex review.
 let app=await readFile(resolve(out,'src/app.js'),'utf8');
 const wording=[
  ['1차 검토 버전','공개 베타'],
  ['검토판에 등록된 음반 6건입니다.','현재 등록된 음반 6건입니다.'],
  ['첫 검토판에는','공개 베타에는'],
  ['검토판은 noindex 설정입니다. 운영 도메인과 호스팅 연결은 별도 확인이 필요합니다.','이세돌 전용 호스팅에서 제공하는 공개 베타입니다. 기능·자료 범위는 이 페이지의 안내를 확인해 주세요.'],
  ['초기 검토판으로','초기 공개 베타로'],
  ['/commits/develop/','/commits/main/'],
  ['검토판에는 비공개 접수 서버가 없습니다.','현재 비공개 접수 서버는 없습니다.'],
  ['현재 검토판의 구현 범위','현재 공개 베타의 구현 범위']
 ];
 for(const [before,after] of wording){
  if(!app.includes(before))throw new Error(`Production wording target missing: ${before}`);
  app=app.replaceAll(before,after);
 }
 await writeFile(resolve(out,'src/app.js'),app);
}
await writeFile(resolve(out,'build-info.json'),JSON.stringify({version:SITE.version,mode:production?'production':'preview',commit:process.env.GITHUB_SHA||'local',builtAt:new Date().toISOString(),contentReviewedAt:SITE.reviewedAt,publicRecords:RECORDS.length},null,2)+'\n');
console.log(`Built ${production?'production':'preview'} static site in dist/. No application dependencies or server runtime required.`);
