from pathlib import Path
R=Path.cwd()
def replace_once(text,old,new):
    if text.count(old)!=1:raise ValueError('Hardening anchor changed')
    return text.replace(old,new,1)
p=R/'scripts/album_history_backfill.py';s=p.read_text()
ids=['rewind','winter-spring','kidding','misty-rainbow','stargazers','elevate','memory','be-my-light','nameless','white','smile-for-you','lockdown','another-world','syzygy','over','superhero','cat-save-world','your-turn','pump-jump-bump','love-cells','rebels','back-2-the-future','anti-hero','dream-residue']
s=replace_once(s,'MAX_POINTS=50000','MAX_POINTS=50000\n# The reviewed 24-song scope is fixed; later catalog additions are not an error.\nTARGET_TRACKS=frozenset('+repr(ids)+')')
s=replace_once(s,"or data.get('cutoffAt')!=CUTOFF.isoformat() or set(data.get('tracks',{}))!=set(catalog)):","or data.get('cutoffAt')!=CUTOFF.isoformat() or set(data.get('tracks',{}))!=TARGET_TRACKS\n        or not TARGET_TRACKS.issubset(catalog)):")
helper='''def reuse_published(data,previous):
    """Daily collection only preserves a repair activated by the UI-gated publisher."""
    at=clock(data['generatedAt'])
    if at<CUTOFF:return None
    published=any(row.get(ARCHIVE,{}).get('datasetSha256')==DATA_SHA256
        for row in previous.get('tracks',{}).values())
    if not published:return None
    return apply(data,previous=previous,at=at,strict=False)

'''
s=replace_once(s,'def patch_remote(remote):',helper+'def patch_remote(remote):');p.write_text(s)
p=R/'scripts/daily_albums.py';s=p.read_text();old="    from album_history_backfill import apply as repair_catalog, CUTOFF as archive_cutoff\n    if clock(data['generatedAt']) >= archive_cutoff:\n        repair_catalog(data, previous=previous, at=clock(data['generatedAt']), strict=False)"
s=replace_once(s,old,"    from album_history_backfill import reuse_published\n    reuse_published(data, previous)");p.write_text(s)
p=R/'tests/test_album_history_backfill.py';s=p.read_text();anchor='    def test_exact_catalog_and_identity(self):'
new='''    def test_new_catalog_songs_do_not_expand_or_break_finite_repair(self):
        ds=fixture();catalog=deepcopy(load_catalog())
        catalog['songs'].append({'id':'future-song','title':'Future','date':'2027-01-01'})
        with patch('album_releases.load_catalog',return_value=catalog):b.validate_dataset(ds)
        self.assertEqual(set(ds['tracks']),b.TARGET_TRACKS)
    def test_daily_reuse_waits_for_ui_gated_published_archive(self):
        ds=fixture();d=sample(ds);d['generatedAt']=AT.isoformat();previous=deepcopy(d)
        with patch.object(b,'apply') as repair:
            self.assertIsNone(b.reuse_published(d,previous));repair.assert_not_called()
            previous['tracks']['rewind'][b.ARCHIVE]={'datasetSha256':'untrusted'}
            self.assertIsNone(b.reuse_published(d,previous));repair.assert_not_called()
            previous['tracks']['rewind'][b.ARCHIVE]={'datasetSha256':b.DATA_SHA256}
            b.reuse_published(d,previous);repair.assert_called_once()
    def test_daily_reuse_preserves_original_generation_and_keeps_scope(self):
        ds=fixture();d=sample(ds);d['generatedAt']=AT.isoformat();previous=deepcopy(d)
        previous['tracks']['rewind'][b.ARCHIVE]={'datasetSha256':b.DATA_SHA256}
        with patch.object(b,'load_dataset',return_value=(ds,DIGEST)):
            result=b.reuse_published(d,previous)
        self.assertEqual(d['generatedAt'],AT.isoformat());self.assertTrue(result['unrelatedFieldsUnchanged'])
'''
s=replace_once(s,anchor,new+anchor);p.write_text(s)
p=R/'docs/ALBUM_HISTORY_20261116.md';s=p.read_text();s+='\nDaily reuse activates only after the UI-gated publisher has stored this exact archive digest. Future catalog additions do not expand or invalidate the fixed 24-song repair scope.\n';p.write_text(s)
print('Daily activation and future-catalog boundaries hardened; no remote writes')
