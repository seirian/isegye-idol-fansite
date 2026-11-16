"""Add weekly-feed support at build time; keep approved visual source bytes intact."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
WEEKLY_HELPERS = """function historyWeekEnd(value){
 historyMonthEnd(value); // Require an explicit, valid timezone just like legacy data.
 const kst=new Date(Date.parse(value)+9*3600000);
 return new Date(Date.UTC(kst.getUTCFullYear(),kst.getUTCMonth(),kst.getUTCDate()-kst.getUTCDay()-1)).toISOString().slice(0,10);
}
function historyPeriodEnd(value,cadence='monthly'){
 if(cadence==='monthly')return historyMonthEnd(value);
 if(cadence==='weekly')return historyWeekEnd(value);
 throw Error('Invalid history cadence');
}
"""

def once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('History cadence anchor changed: ' + old[:90])
    return text.replace(old, new, 1)

def validator(text):
    text = once(text, 'function validHistoryDay(value)', WEEKLY_HELPERS + 'function validHistoryDay(value)')
    text = once(text, 'feed.through!==historyMonthEnd(feed.generatedAt)', 'feed.through!==historyPeriodEnd(feed.generatedAt,feed.cadence)')
    return once(text,
        'HISTORY.monthly={generatedAt:feed.generatedAt,through:feed.through,partial:feed.coverage?.partial===true};',
        "HISTORY.monthly={generatedAt:feed.generatedAt,through:feed.through,cadence:feed.cadence??'monthly',partial:feed.coverage?.partial===true};")

def ui(text):
    return once(text, 'class="history-monthly-status">월간 갱신 ',
        'class="history-monthly-status">${HISTORY.monthly.cadence===\'weekly\'?\'주간\':\'월간\'} 갱신 ')

if __name__ == '__main__':
    # Emit the exact compiled validator for Node unit tests; no network or writes.
    if len(sys.argv) != 2 or sys.argv[1] != 'validator':
        raise SystemExit('Usage: history_cadence.py validator')
    print(validator((ROOT / 'visuals/monthly-history.js').read_text()), end='')
