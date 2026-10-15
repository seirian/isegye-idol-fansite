/** Produce a single-file offline review without imports, external media, or unsafe-inline CSP. */
import {readFile,writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {createHash} from 'node:crypto';
const root=resolve(import.meta.dirname,'..');
const read=path=>readFile(resolve(root,path),'utf8');
const favicon='data:image/svg+xml;base64,'+Buffer.from(await read('assets/favicon.svg')).toString('base64');
let js=(await Promise.all(['src/data.js','src/lib.js','src/app.js'].map(read))).map(s=>s.replace(/^import .*;\r?\n/gm,'').replace(/^export /gm,'')).join('\n');
js='const e=escapeHtml;\n'+js.replace('src="./assets/favicon.svg"',`src="${favicon}"`);
const css=(await read('src/styles.css'))+'\n'+(await read('src/refinements.css'));
const digest=text=>createHash('sha256').update(text).digest('base64');
let html=await read('index.html');
html=html.replace('<link rel="stylesheet" href="./src/styles.css">',`<style>${css}</style>`).replace('  <link rel="stylesheet" href="./src/refinements.css">\n','').replace('<script type="module" src="./src/app.js"></script>',`<script type="module">${js}</script>`).replace('href="./assets/favicon.svg"',`href="${favicon}"`).replace("script-src 'self'",`script-src 'self' 'sha256-${digest(js)}'`).replace("style-src 'self'",`style-src 'self' 'sha256-${digest(css)}'`);
await writeFile(resolve(root,'dist/review.html'),html);
console.log('Created dist/review.html — standalone offline review, no web server required.');
