/** The selected builder produces the reviewed, self-contained offline file. */
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
const html=await readFile(resolve(import.meta.dirname,'../dist/review.html'),'utf8');
if(!html.includes('data:image/webp;base64,')||!html.includes('noindex,nofollow')) {
  throw new Error('Build the selected preview before requesting an offline review');
}
console.log('Verified dist/review.html — second design, embedded portraits, no web server required.');
