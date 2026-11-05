"""Run the existing auth suite for review 2 and verify review 1 stays accessible."""
from pathlib import Path
import hashlib
ROOT=Path(__file__).resolve().parents[1]
source=(ROOT/'tests/review_host_browser.py').read_text()
assert hashlib.sha256(source.encode()).hexdigest()=='fbce2b92873b3b1d2b6594bff00e3f9d0bc242642d00c580d2e1bb48b00cfb79', 'Host test base changed'
source=source.replace('review-1st','review-2nd').replace('review_1st','review_2nd').replace("ROOT/'test-results/review-host'","ROOT/'test-results/review2-host'").replace('count()==6','count()==7')
lines=source.splitlines(keepends=True)
edits=[(27, 27, "    first_preview=base/'.review-1st';first_preview.mkdir(mode=0o700)\n    first_html=b'<!doctype html><title>FIRST_REVIEW_PRESERVED</title>'\n    first_release='p'+'1'*12\n    first_target=first_preview/'releases'/first_release;first_target.mkdir(parents=True)\n    (first_target/'review.html').write_bytes(first_html)\n    (first_target/'build-info.json').write_bytes(b'{}')\n    import hashlib\n    (first_preview/'.owner').write_bytes(b'isegye-first-review:v1\\\\n')\n    (first_preview/'active.json').write_text(json.dumps({'release':first_release,'sha256':hashlib.sha256(first_html).hexdigest(),'metadataSha256':hashlib.sha256(b'{}').hexdigest()}))\n"), (37, 37, "            check('existing first review still works',owner.request.get(url+'/review-1st/').body()==first_html)\n            check('first review also requires administrator',guest.request.get(url+'/review-1st/').status==503)\n")]
for start,end,replacement in reversed(edits):lines[start:end]=[replacement]
source=''.join(lines)
assert hashlib.sha256(source.encode()).hexdigest()=='9b92462c179107929790c19523ce9186c8229d6cbd7625c90eb4a2814be82155', 'Host test transformation changed'
exec(compile(source,str(ROOT/'tests/review_2nd_host_browser.py'),'exec'),{'__name__':'__main__','__file__':str(ROOT/'tests/review_2nd_host_browser.py')})
