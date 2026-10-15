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
 // Canonical points only at the approved production root. Hash-route SEO is a later milestone.
 html=html.replace('</head>','  <link rel="canonical" href="https://isegye-idol.kr/">\n</head>');
 await writeFile(resolve(out,'index.html'),html);
 await writeFile(resolve(out,'robots.txt'),'User-agent: *\nAllow: /\n');
}
await writeFile(resolve(out,'build-info.json'),JSON.stringify({version:SITE.version,mode:production?'production':'preview',commit:process.env.GITHUB_SHA||'local',builtAt:new Date().toISOString(),contentReviewedAt:SITE.reviewedAt,publicRecords:RECORDS.length},null,2)+'\n');
console.log(`Built ${production?'production':'preview'} static site in dist/. No application dependencies or server runtime required.`);
