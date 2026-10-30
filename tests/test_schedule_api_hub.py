"""Regression checks for NAVER API HUB migration. No live credentials or network."""
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
import copy, io, json, os, sys, unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import schedule_feed as f
import publish_schedule_feed as pub
NOW='2026-10-30T04:23:19Z'
ENV={'ISEGYE_NAVER_CLIENT_ID':'fixture-client','ISEGYE_NAVER_CLIENT_SECRET':'fixture-secret'}

class Hub(unittest.TestCase):
    def test_all_queries_use_hub_contract(self):
        calls=[]
        def fetch(url,headers):
            calls.append((url,headers))
            return b'{"items":[]}'
        with patch.dict(os.environ,ENV),patch.object(f.time,'sleep'):
            self.assertEqual(f.naver_search(fetch,NOW),[])
        self.assertEqual(len(calls),8)
        for url,headers in calls:
            p=urlsplit(url)
            self.assertEqual(p.scheme+'://'+p.netloc+p.path,f.NAVER_SEARCH_URL)
            self.assertEqual(headers,{'X-NCP-APIGW-API-KEY-ID':'fixture-client','X-NCP-APIGW-API-KEY':'fixture-secret'})
            self.assertEqual(parse_qs(p.query)['format'],['json'])
            self.assertEqual(parse_qs(p.query)['display'],['20'])
            self.assertEqual(parse_qs(p.query)['start'],['1'])
            self.assertEqual(parse_qs(p.query)['sort'],['date'])
            self.assertNotIn('fixture',url)
    def test_legacy_and_wrong_destinations_rejected_before_network(self):
        urls=['https://openapi.naver.com/v1/search/cafearticle.json',
              'https://naverapihub.apigw.ntruss.com/search/v1/blog',
              'https://naverapihub.apigw.ntruss.com.evil.invalid/search/v1/cafearticle',
              f.NAVER_SEARCH_URL.replace('https:','http:'),
              f.NAVER_SEARCH_URL.replace('.com/','.com:444/'),
              f.NAVER_SEARCH_URL+'#fragment',
              f.NAVER_SEARCH_URL.replace('https://','https://user:pass@')]
        with patch.object(f,'build_opener') as opener:
            for url in urls:
                with self.subTest(url=url),self.assertRaises(f.FeedError):f.request(url)
            opener.assert_not_called()
    def test_auth_headers_never_sent_to_parable(self):
        with patch.object(f,'build_opener') as opener,self.assertRaises(f.FeedError):
            f.request('https://parable-asia.com/newsroom/',headers=dict(zip(f.NAVER_SEARCH_HEADER_NAMES,('id','secret'))))
        opener.assert_not_called()
    def test_legacy_headers_rejected(self):
        with patch.object(f,'build_opener') as opener,self.assertRaises(f.FeedError):
            f.request(f.NAVER_SEARCH_URL,headers={'X-Naver-Client-Id':'id','X-Naver-Client-Secret':'secret'})
        opener.assert_not_called()
    def test_exact_endpoint_request(self):
        with patch.object(f,'build_opener') as opener:
            response=opener.return_value.open.return_value.__enter__.return_value
            response.status=200;response.read.return_value=b'{"items":[]}'
            self.assertEqual(f.request(f.NAVER_SEARCH_URL),b'{"items":[]}')
            args=opener.call_args.args
            self.assertTrue(any(x is f.NoRedirect for x in args))
    def test_no_redirect(self):
        self.assertIsNone(f.NoRedirect().redirect_request(None,None,302,'redirect',{},'https://elsewhere.invalid'))
    def test_nested_gateway_error_is_sanitized(self):
        payload={'error':{'errorCode':'200','message':'fixture-secret','details':'fixture-client'}}
        err=HTTPError(f.NAVER_SEARCH_URL,401,'error',{},io.BytesIO(json.dumps(payload).encode()))
        with patch.object(f,'build_opener') as opener:
            opener.return_value.open.side_effect=err
            with self.assertRaisesRegex(f.FeedError,'^http_401_api_200$'):f.request(f.NAVER_SEARCH_URL)
    def test_flat_search_error_is_sanitized(self):
        err=HTTPError(f.NAVER_SEARCH_URL,400,'error',{},io.BytesIO(b'{"errorCode":"SE01","errorMessage":"fixture-secret"}'))
        with patch.object(f,'build_opener') as opener:
            opener.return_value.open.side_effect=err
            with self.assertRaisesRegex(f.FeedError,'^http_400_api_SE01$'):f.request(f.NAVER_SEARCH_URL)
    def test_unknown_error_body_not_copied(self):
        for raw in (b'private raw body',b'{"errorCode":"fixture-secret"}',b'[]'):
            err=HTTPError(f.NAVER_SEARCH_URL,403,'error',{},io.BytesIO(raw))
            with patch.object(f,'build_opener') as opener:
                opener.return_value.open.side_effect=err
                with self.assertRaisesRegex(f.FeedError,'^http_403$'):f.request(f.NAVER_SEARCH_URL)
    def test_missing_or_invalid_credentials_make_no_request(self):
        for changes in ({'ISEGYE_NAVER_CLIENT_SECRET':''},{'ISEGYE_NAVER_CLIENT_SECRET':'bad\nheader'}):
            with patch.dict(os.environ,{**ENV,**changes}),patch.object(f,'request') as fetch,self.assertRaises(f.FeedError):f.naver_search(fetch,NOW)
            fetch.assert_not_called()
    def test_api_failure_has_no_legacy_fallback_or_retry_storm(self):
        calls=[]
        def failed(url,**kw):calls.append(url);raise f.FeedError('http_401_api_200')
        with patch.dict(os.environ,ENV),self.assertRaises(f.FeedError):f.naver_search(failed,NOW)
        self.assertEqual(len(calls),1);self.assertTrue(calls[0].startswith(f.NAVER_SEARCH_URL+'?'))
    def test_bad_success_schema_rejected(self):
        for payload in ([],{}, {'items':{}},{'items':[None]}, {'items':[{}]*101}):
            with patch.dict(os.environ,ENV),patch.object(f.time,'sleep'),self.assertRaises(f.FeedError):
                f.naver_search(lambda *a,**k:json.dumps(payload).encode(),NOW)
    def test_dedup_restriction_no_author_or_date_inference(self):
        payload={'lastBuildDate':NOW,'items':[
            {'title':'아이네 <b>오늘 방송</b>','link':'https://cafe.naver.com/steamindiegame/991','description':'not stored'},
            {'title':'아이네 오늘 방송','link':'https://m.cafe.naver.com/steamindiegame/991'},
            {'title':'아이네 방송','link':'https://cafe.naver.com/othercafe/123'}]}
        with patch.dict(os.environ,ENV),patch.object(f.time,'sleep'):
            rows=f.naver_search(lambda *a,**k:json.dumps(payload).encode(),NOW)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['sourceId'],'naver-search')
        self.assertIsNone(rows[0]['publishedAt']);self.assertNotIn('date',rows[0]);self.assertNotIn('description',rows[0])
        self.assertNotIn('<b>',rows[0]['title'])
    def test_search_failure_preserves_last_good_news_and_success_time(self):
        old=json.loads((ROOT/'schedule/seed.json').read_text())
        item=f.public_item('naver-search','https://cafe.naver.com/steamindiegame/991','아이네 소식',None,NOW)
        old['news'].append(item)
        next(x for x in old['sources'] if x['id']=='naver-search')['lastSuccessAt']=NOW
        with patch.dict(os.environ,ENV):
            result=f.collect(old,fetch=lambda *a,**kw:(_ for _ in ()).throw(f.FeedError('http_429')),now='2026-10-30T05:23:19Z')
        row=next(x for x in result['news'] if x['id']==item['id'])
        self.assertEqual(row['checkedAt'],NOW)
        status=next(x for x in result['sources'] if x['id']=='naver-search')
        self.assertEqual(status['state'],'error');self.assertEqual(status['lastSuccessAt'],NOW)
    def test_publication_reports_only_aggregate_source_counts(self):
        from test_schedule_feed import FeedRemote,seed
        value=seed();value['news'].append(f.public_item('naver-search','https://cafe.naver.com/steamindiegame/991','아이네 소식',None,NOW))
        result=pub.publish(FeedRemote(),lambda **kw:value)
        self.assertEqual(result['naverSearchProvider'],'NAVER API HUB')
        self.assertEqual(result['newsCountsBySource']['naver-search'],1)
        self.assertEqual(sum(result['newsCountsBySource'].values()),result['counts']['news'])
        self.assertFalse(result['accountStoreReadOrWritten']);self.assertTrue(result['protectedFilesUnchanged'])
        self.assertNotIn('아이네 소식',json.dumps(result,ensure_ascii=False))

if __name__=='__main__':unittest.main()
