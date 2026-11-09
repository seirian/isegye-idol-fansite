#!/usr/bin/env python3
"""Collect the isolated review only. No production data or scheduler writes."""
from pathlib import Path
import json
from collect_album_insights import collect
from collect_album_domestic import collect as domestic_collect
from collect_album_records import collect as records_collect
ROOT=Path(__file__).resolve().parents[1]
if __name__=='__main__':
    path=ROOT/'albums/snapshot.json'
    try: previous=json.loads(path.read_text()) if path.exists() else {}
    except (ValueError,OSError): previous={}
    data=collect(previous, include_apple_chart=False)
    data=domestic_collect(data,previous,chart_kinds={'melon_top100','melon_hot100'})
    data=records_collect(data,previous)
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'matched':sum(v['match']=='matched' for v in data['tracks'].values()),'total':len(data['tracks']),'providers':{k:v['state'] for k,v in data['providers'].items()}},ensure_ascii=False))
