#!/usr/bin/env python3
"""Import a verified one-time public listing artifact, without executing its data."""
from pathlib import Path
import hashlib,json,sys,zipfile
import notice_policy
ROOT=Path(__file__).resolve().parents[1]

def main():
    bundle=Path(sys.argv[1]);expected=sys.argv[2]
    if hashlib.sha256(bundle.read_bytes()).hexdigest()!=expected:raise ValueError('history artifact checksum differs')
    with zipfile.ZipFile(bundle) as z:
        if set(z.namelist())!={'notices.json','coverage.json'}:raise ValueError('unexpected archive entries')
        if any(x.file_size>12*1024*1024 for x in z.infolist()):raise ValueError('history too large')
        data=notice_policy.validate_archive(json.loads(z.read('notices.json')))
        report=json.loads(z.read('coverage.json'))
    if report.get('acceptedCount')!=len(data['notices']) or report.get('authenticated') is True or report.get('loginUsed') is not False or report.get('articleBodiesRead') is not False:
        raise ValueError('history evidence differs')
    if report.get('checkedAt')!=data['checkedAt']:raise ValueError('observation timestamp differs')
    if report.get('complete') is True and not (len(report['boards'])==2 and all(b.get('finished') is True for b in report['boards'])):
        raise ValueError('false complete flag')
    # Save only publicly reviewed, allowlisted metadata. No bodies, member IDs, headers or cookies.
    (ROOT/'schedule/approved-notices.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':'))+'\n')
    (ROOT/'schedule/notice-history-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    approval=ROOT/'review/home-release.json';value=json.loads(approval.read_text())
    for path in value['sourceHashes']:
        value['sourceHashes'][path]=hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    approval.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'imported':len(data['notices']),'completePublicListings':report['complete'],'bodiesReviewed':False,'checksumVerified':True}))

if __name__=='__main__':main()
