"""Bounded 30-day hourly feed capacity, including duplicated legacy histories."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import album_hourly as hourly
from test_albums_daily import complete_data

class HourlyCapacity(unittest.TestCase):
    def test_thirty_day_hourly_capacity_and_boundary(self):
        from daily_albums import validate, MAX_BYTES
        data=complete_data()
        at=hourly.slot(datetime.now(timezone.utc))
        times=[at-timedelta(hours=i) for i in range(30*24) if hourly.allowed(at-timedelta(hours=i))]
        for sid,item in data['tracks'].items():
            ident=item.get('melon',{}).get('trackId')
            if not ident:continue
            for kind in hourly.KINDS:
                rows=[{'at':t.isoformat(),'trackId':ident,'rank':None,'status':'out'} for t in times]
                item.setdefault('charts',{})[kind]=rows
                item['melon'][kind.replace('melon_','')+'History']=deepcopy(rows)
            item['youtubeHistory']=[{'at':t.isoformat(),'videoId':'abcdefghijk','views':1000000,'likes':10000,'comments':1000} for t in times]
        raw=json.dumps(data,ensure_ascii=False,separators=(',', ':')).encode()
        self.assertGreater(len(raw),2_000_000)
        self.assertLess(len(raw),MAX_BYTES)
        validate(data,exact=True,fresh=True)
        data['padding']='x'*MAX_BYTES
        with self.assertRaises(ValueError):validate(data)
        php=(ROOT/'albums/hosting/AlbumsFeed.php').read_text()
        self.assertIn("self::read($folder.'/current.json', 8000000)",php)
        self.assertIn("'text.length>2000000', 'text.length>8000000'", (ROOT/'scripts/promote_albums.py').read_text())

if __name__=='__main__': unittest.main()
