import {createServer} from 'node:http';
import {readFile,stat} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
const root=resolve(import.meta.dirname,'..',process.argv.includes('--dist')?'dist':'.');
const port=Number(process.env.PORT||4173),host=process.env.HOST||'127.0.0.1';
if(!Number.isInteger(port)||port<1||port>65535)throw new Error('Invalid PORT');
const types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.svg':'image/svg+xml','.webp':'image/webp','.png':'image/png','.jpg':'image/jpeg','.json':'application/json; charset=utf-8','.txt':'text/plain; charset=utf-8'};
createServer(async(req,res)=>{
 res.setHeader('X-Content-Type-Options','nosniff');res.setHeader('Cache-Control','no-store');res.setHeader('Referrer-Policy','strict-origin-when-cross-origin');
 if(!['GET','HEAD'].includes(req.method)){res.writeHead(405,{Allow:'GET, HEAD'});res.end();return;}
 try{
  const path=decodeURIComponent(new URL(req.url,'http://localhost').pathname);
  if(path.includes('\0')||path.split('/').some(p=>p.startsWith('.')&&p!=='.nojekyll'))throw new Error('Invalid path');
  const file=resolve(root,'.'+(path==='/'?'/index.html':path));
  if(!file.startsWith(root+sep))throw new Error('Outside root');
  if(!(await stat(file)).isFile())throw new Error('Not a file');
  const data=await readFile(file);res.writeHead(200,{'Content-Type':types[extname(file)]||'application/octet-stream'});res.end(req.method==='HEAD'?undefined:data);
 }catch{res.writeHead(404,{'Content-Type':'text/plain; charset=utf-8'});res.end('Not found');}
}).listen(port,host,()=>console.log(`Review server: http://${host}:${port} (${root})`));
