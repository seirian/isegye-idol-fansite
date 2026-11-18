# Selected IRISÉ / LILPA collaboration replay

Owner requested only `https://www.youtube.com/live/P15VglxEkss` for content registration and production deployment on 2026-11-17. The canonical watch URL retains the same video ID and drops the share-tracking parameter. This does not authorize collection of the whole IRISÉ channel.

## Public source evidence

YouTube Data API v3 `videos.list` verification run **44108855400**, checked **2026-11-17T14:57:59.458338+00:00**. Source artifact 14339577330 SHA-256: `5c07cdab68522cf21e1145ba04752ddb1544af159571fd99582b5186aa7b2f08`.

- Title: `[IRISÉ LIVE] 오늘은 릴파 선배님과 함께! 🩵💙`.
- Publisher: IRISÉ, channel `UCMmcz1ybSoAD-GUlDx_7H2A`.
- Actual broadcast start: 2026-11-16 18:04:24 KST. Actual end: 19:39:58 KST.
- Video publication: 2026-11-16 19:45:19 KST. This is distinct from broadcast start and scheduled start (18:00 KST).
- Recorded duration: 5,731 seconds (1:35:31), from contentDetails; do not replace it with the live start/end difference.
- Public and embeddable; HD reported, not verified 4K. Viewing blocked in RU (Russia); retain this restriction in the detail summary.
- The source title and description identify LILPA, KIIRI and TIZ and describe new-song challenges and K-POP random play dance. The matching official Weverse page is https://weverse.io/irise/live/0-181588285?hl=ko.

Verification covers public metadata, publisher description and the matching official notice, not full audiovisual playback. No video/audio is downloaded or rehosted. No detailed timestamps or dialogue are inferred.

## Registration boundaries

`catalog/irise-lilpa-videos.json` and `scripts/irise_lilpa_videos.py` allow only the verified video. Contents > Videos > External and the selected IRISÉ channel filter expose it; the member filter connects **only `lilpa`**, with KIIRI/TIZ recorded separately as external guests. Type is `external_collaboration`, recordingKind is `livestream_archive`, and the display label is `합방 다시보기`. It is not an artist-owned upload, group music performance, official MV or new song/album. It has no inferred relatedSong and does not enter REBELS performance recommendations. The existing artist-owned Replay tab is unchanged; this external replay is explicitly labelled in the external video catalog.

The four existing external performance/teaser selections remain byte-for-byte unchanged. Artist channel counts, historical coverage, member profiles, songs, album/MV statistics, scheduled ingestion, access controls and pinned review sources remain unchanged. Runtime music refresh retains the baseline collaboration row without duplication.

The related-performance helper now rejects empty song IDs and excludes collaboration types, preventing unrelated external videos from appearing on ordinary video details. Duration display supports hours without changing existing short-video labels. Unit and browser regression checks cover exact source identity, source/region labels, only-LILPA filters, original links, long duration, publication versus broadcast time, existing performances, runtime retention and mobile overflow. Existing CI and production run these checks before upload. Build-info records the exact selected video/channel IDs; deployment completion requires the actual deployer's read-back and `deployed_and_verified` report, not just a merge or green tests.
