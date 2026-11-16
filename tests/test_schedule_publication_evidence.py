"""Unit-test publication reporting with an in-memory transport.

Only dependency/transport boundaries are mocked. The repository's actual
publish() implementation, byte comparison, ordering and report are executed.
No external source, SFTP host, authentication or production data is accessed.
"""
import copy
from datetime import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]

class Stop(RuntimeError):pass

def require(value,message):
    if not value:raise Stop(message)


def load_publisher():
    d=types.ModuleType('inour_sftp')
    d.ROOT='/web/unit-test';d.OWNER=b'unit-owner';d.require=require;d.Stop=Stop
    d.digest=lambda raw:hashlib.sha256(raw).hexdigest()
    feed=types.ModuleType('schedule_feed')
    feed.collect=lambda **kw: {}
    feed.validate=lambda value:copy.deepcopy(value)
    routing=types.ModuleType('auth_routing')
    routing.release_of=lambda raw:('unit-release',True)
    policy=types.ModuleType('notice_policy')
    policy.clean_snapshot=lambda value:value
    policy.EXCLUDED_URLS=set()
    health=types.ModuleType('schedule_health')
    health.assess=lambda value:{'state':'complete','sources':{}}
    modules={m.__name__:m for m in (d,feed,routing,policy,health)}
    spec=importlib.util.spec_from_file_location('_publication_evidence_unit',ROOT/'scripts/publish_schedule_feed.py')
    module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,modules):spec.loader.exec_module(module)
    return module


class MemoryRemote:
    def __init__(self,publisher):
        self.p=publisher;self.writes=[];self.corrupt=False;self.published=False
        self.files={publisher.d.ROOT+'/.isegye-owner':publisher.d.OWNER,
                    publisher.d.ROOT+'/.htaccess':b'router',
                    publisher.d.ROOT+'/_isegye_releases/unit-release/build-info.json':b'{"scheduleFeed":{"schemaVersion":1}}',
                    publisher.path('.owner'):publisher.MARKER}
        self.s=types.SimpleNamespace(chmod=lambda *a:None)
    def directory(self,path):pass
    def info(self,path):return {} if path==self.p.FOLDER or path in self.files else None
    def read(self,path):
        if self.corrupt and self.published and path==self.p.path('current.json'):return b'corrupted'
        return self.files.get(path)
    def snapshot(self):return {'protected':b'unchanged'}
    def new(self,path,raw):
        require(path not in self.files,'already exists')
        self.files[path]=raw;self.writes.append(path)
    def replace(self,path,raw,old):
        require(self.files.get(path)==old,'concurrent change')
        self.files[path]=raw;self.writes.append(path)
        if path==self.p.path('current.json'):self.published=True
    def remove_own(self,path,raw):
        require(self.files.get(path)==raw,'foreign lock')
        del self.files[path]


class PublicationEvidence(unittest.TestCase):
    def setUp(self):
        self.p=load_publisher();self.remote=MemoryRemote(self.p)
        self.value={'generatedAt':'2026-11-15T05:19:32+00:00',
                    'events':[],'news':[],'forecasts':[],'sources':[]}
    def collect(self,**kw):return copy.deepcopy(self.value)

    def test_readback_success_has_explicit_flag_timestamps_and_matching_hash(self):
        result=self.p.publish(self.remote,self.collect)
        self.assertEqual(result['status'],'published')
        self.assertIs(result['verifiedReadback'],True)
        published=datetime.fromisoformat(result['publishedAt'])
        readback=datetime.fromisoformat(result['readbackAt'])
        self.assertIsNotNone(published.tzinfo)
        self.assertGreaterEqual(readback,published)
        raw=self.remote.files[self.p.path('current.json')]
        self.assertEqual(hashlib.sha256(raw).hexdigest(),result['sha256'])
        self.assertNotIn(self.p.path('.lock'),self.remote.files)
        self.assertTrue(all(path.startswith(self.p.FOLDER+'/') for path in self.remote.writes))

    def test_readback_failure_cannot_report_success(self):
        self.remote.corrupt=True
        with self.assertRaisesRegex(Stop,'Feed bytes differ'):
            self.p.publish(self.remote,self.collect)
        self.assertNotIn(self.p.path('.lock'),self.remote.files)

    def test_foreign_lock_is_preserved_and_no_publication_occurs(self):
        self.remote.files[self.p.path('.lock')]=b'foreign-unit-lock'
        with self.assertRaisesRegex(Stop,'Existing feed lock'):
            self.p.publish(self.remote,self.collect)
        self.assertEqual(self.remote.files[self.p.path('.lock')],b'foreign-unit-lock')
        self.assertFalse(self.remote.published)

    def test_authentication_gate_remains_required(self):
        self.p.auth_routing.release_of=lambda raw:('unit-release',False)
        with self.assertRaisesRegex(Stop,'Authentication router required'):
            self.p.publish(self.remote,self.collect)
        self.assertFalse(self.remote.published)

    def test_new_report_fields_do_not_modify_stored_feed_schema(self):
        self.p.publish(self.remote,self.collect)
        stored=json.loads(self.remote.files[self.p.path('current.json')])
        self.assertNotIn('verifiedReadback',stored)
        self.assertNotIn('publishedAt',stored)
        self.assertEqual(stored['generatedAt'],self.value['generatedAt'])
        self.assertEqual(stored['events'],[])

    def test_existing_feed_backup_and_counts_are_preserved(self):
        self.remote.files[self.p.path('current.json')]=json.dumps(self.value).encode()
        result=self.p.publish(self.remote,self.collect)
        self.assertEqual(result['counts'],{'events':0,'news':0,'forecasts':0})
        self.assertTrue(result['previousSnapshotSanitized'])
        self.assertEqual(json.loads(self.remote.files[self.p.path('previous.json')]),self.value)


if __name__=='__main__':unittest.main()
