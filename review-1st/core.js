/* Pure review utilities. No network, account, or production writes. */
export function esc(value=''){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
export function normalized(value=''){return String(value).normalize('NFKC').toLocaleLowerCase('ko').replace(/[^\p{L}\p{N}]/gu,'');}
export function initials(value=''){const cho='ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ';return [...value].map(c=>{const n=c.charCodeAt(0)-44032;return n>=0&&n<11172?cho[Math.floor(n/588)]:c;}).join('');}
export function safeExternal(value){try{const u=new URL(value);return u.protocol==='https:'&&!u.username&&!u.password?u.href:'';}catch{return '';}}
export function kstDay(value){if(/^\d{4}-\d{2}-\d{2}$/.test(String(value)))return value;const n=Date.parse(value);return Number.isFinite(n)?new Date(n+32400000).toISOString().slice(0,10):'';}
export function validDay(value){if(!/^20\d{2}-\d{2}-\d{2}$/.test(value||''))return false;const d=new Date(value+'T00:00:00Z');return Number.isFinite(+d)&&d.toISOString().slice(0,10)===value;}
export function queryParts(query,year=new Date().getFullYear()){
 const dates=[];let text=String(query||'').trim().slice(0,180);
 text=text.replace(/(?:(20\d{2})\s*년\s*)?(\d{1,2})\s*월\s*(\d{1,2})\s*일/g,(_,y,m,d)=>{const day=`${y||year}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;if(validDay(day)){dates.push(day);return ' ';}return _;});
 text=text.replace(/(20\d{2})[-./](\d{1,2})[-./](\d{1,2})/g,(_,y,m,d)=>{const day=`${y}-${m.padStart(2,'0')}-${d.padStart(2,'0')}`;if(validDay(day)){dates.push(day);return ' ';}return _;});
 return {dates,tokens:text.split(/\s+/).map(normalized).filter(Boolean)};
}
export function matchesQuery(row,query,names={},year){
 const q=queryParts(query,year),identity=[row.title,row.channelName,...(row.tags||[]),...(row.members||[]).flatMap(x=>[x,names[x]||''])].join(' ');
 const body=normalized(identity+' '+(row.summary||'')+' '+(row.date||'')+' '+(row.type||''));
 const cho=normalized(initials(identity));
 return q.dates.every(d=>row.date===d)&&q.tokens.every(t=>/^[\u1100-\u115f\u3131-\u314e]+$/.test(t)?cho.includes(t):body.includes(t));
}
export function memberMatches(row,selected,mode='any'){if(!selected.length)return true;const ids=row.members||[];return mode==='all'?selected.every(x=>ids.includes(x)):selected.some(x=>ids.includes(x));}
export function calendarDays(month){if(!/^20\d{2}-(0[1-9]|1[0-2])$/.test(month))return [];const [y,m]=month.split('-').map(Number),first=new Date(Date.UTC(y,m-1,1)),count=new Date(Date.UTC(y,m,0)).getUTCDate();return [...Array(first.getUTCDay()).fill(null),...Array.from({length:count},(_,i)=>`${month}-${String(i+1).padStart(2,'0')}`)];}
export function icsEscape(s){return String(s||'').replace(/\\/g,'\\\\').replace(/\r?\n/g,'\\n').replace(/;/g,'\\;').replace(/,/g,'\\,');}
export function makeCalendar(event){
 if(event.kind!=='event'||event.certainty!=='confirmed'||event.status==='cancelled'||!validDay(event.date))throw Error('확정 일정만 저장할 수 있습니다.');
 if(event.time&&!/^(?:[01]\d|2[0-3]):[0-5]\d$/.test(event.time))throw Error('유효하지 않은 일정 시각입니다.');
 const day=event.date.replaceAll('-','');let dateLines;
 if(event.time&&/^\d\d:\d\d$/.test(event.time)){const start=new Date(`${event.date}T${event.time}:00+09:00`),end=event.endAt?new Date(event.endAt):null;dateLines=['DTSTART:'+start.toISOString().replace(/[-:]/g,'').replace('.000','')];if(end&&+end>+start)dateLines.push('DTEND:'+end.toISOString().replace(/[-:]/g,'').replace('.000',''));}
 else {const next=new Date(event.date+'T00:00:00Z');next.setUTCDate(next.getUTCDate()+1);dateLines=['DTSTART;VALUE=DATE:'+day,'DTEND;VALUE=DATE:'+next.toISOString().slice(0,10).replaceAll('-','')];}
 const lines=['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//ISEGYE FAN ARCHIVE//REVIEW 1ST//KO','CALSCALE:GREGORIAN','BEGIN:VEVENT','UID:'+icsEscape(event.key)+'@review.isegye-idol.kr','DTSTAMP:'+new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,''),...dateLines,'SUMMARY:'+icsEscape(event.title),'DESCRIPTION:'+icsEscape('비공식 팬 아카이브에서 내보낸 확인 당시 일정입니다. 자동 동기화되지 않으므로 변경·취소는 공식 원문을 확인하세요. '+(event.time?'':'시간을 명시하지 않은 날짜 항목입니다. ')),'URL:'+safeExternal(event.url),'END:VEVENT','END:VCALENDAR'];
 const enc=new TextEncoder();return lines.map(line=>{let out='',chunk='';for(const ch of line){if(enc.encode(chunk+ch).length>73){out+=chunk+'\r\n ';chunk=ch;}else chunk+=ch;}return out+chunk;}).join('\r\n')+'\r\n';
}
