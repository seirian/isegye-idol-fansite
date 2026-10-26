/** Build the selected photocard design; deployment remains main-only. */
import {spawnSync} from 'node:child_process';
import {resolve} from 'node:path';
import {RECORDS,SOURCES,MEMBERS} from '../src/data.js';
import {validateContent} from '../src/lib.js';
const errors=validateContent(RECORDS,SOURCES,MEMBERS);
if(errors.length) throw new Error(errors.join('\n'));
const result=spawnSync(process.env.PYTHON||'python3',['scripts/build_release_home.py'],{
  cwd:resolve(import.meta.dirname,'..'),env:process.env,stdio:'inherit'
});
if(result.error) throw result.error;
if(result.status!==0) throw new Error(`Approved simple home release build failed (${result.status??result.signal})`);
