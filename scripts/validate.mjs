import {RECORDS,SOURCES,MEMBERS} from '../src/data.js';
import {validateContent} from '../src/lib.js';
const errors=validateContent(RECORDS,SOURCES,MEMBERS);
if(errors.length){console.error(errors.join('\n'));process.exit(1);}
console.log(`Validated ${RECORDS.length} public records, ${Object.keys(SOURCES).length} sources, ${MEMBERS.length} members.`);
