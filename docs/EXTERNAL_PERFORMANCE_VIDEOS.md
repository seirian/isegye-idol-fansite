# Selected external performance uploads

Owner requested these two URLs on 2026-11-11. Public YouTube Data API verification run: 43033346225. Checked 2026-11-11T13:54:15.335564+00:00. This verifies public metadata and availability, not a complete audiovisual playback review. The 4K designation comes from the publisher's title.

| Video | Type | Publication (KST) | Duration |
| --- | --- | --- | --- |
| `_E9ZHH9R7o4` | REBELS performance teaser | 2026-11-10 22:00:38 | 0:31 |
| `Mj7q8HU8ZXg` | REBELS full performance | 2026-11-11 22:47:14 | 3:12 |

Both uploader IDs are `UCEIi7zFR_wE23jFncVtd6-A` (STUDIO CHOOM [스튜디오 춤]). The selected-video catalog is separate from the 22 fully collected artist channels; it does not authorize scraping or adding all STUDIO CHOOM uploads.

Both appear in Contents, with an external-channel filter and explicit source label. Only the full performance additionally appears in Music > Videos. Both link to the existing `rebels` song and to each other. The original `y-klhPVFblg` MV, five album tracks, release date, album chart metrics and MV statistics remain unchanged. No duplicate song or album is created. Runtime music refresh retains the two baseline video rows. Existing login, preview protection and batch schedules are untouched.

The composition is applied after the hash-pinned reviewed album UI. Archived review sources remain unchanged. Normal CI and the main-only production workflow run the selected-video browser regression before upload.

The owner replaced the first full-video URL `z8AJgnTC52k` with `Mj7q8HU8ZXg` before publication. Only the replacement is registered; its own publication timestamp is used. The teaser is unchanged.

## Pagination-aware release verification — 2026-11-24

Production run [45299926320](https://github.com/seirian/isegye-idol-fansite/actions/runs/45299926320) stopped before upload because the external-video browser check expected the full STUDIO CHOOM performance on the first page of `music?tab=videos&q=REBELS`. The music screen sorts newest first and renders 24 results per page. Replaying the archived source and catalog produced 40 matches, with `Mj7q8HU8ZXg` at position 27 on page two. This exact position describes the archived catalog reproduction; the run's complete post-refresh catalog was not preserved. The original report confirms the preceding 28 checks passed before the first-page assertion failed.

`tests/external_videos_browser.py` now follows the rendered next-page links until the search ends. It checks that the query and page advance correctly, that every reported result is rendered, and that the combined DOM agrees with the eligible search data. Each selected full performance must appear exactly once across all pages; the teaser must appear zero times in the music-performance list. Separate checks verify both STUDIO CHOOM IDs, source labels, types and song relationships in the full catalog and external-content screen.

An isolated browser regression adds 24 newer matching group videos in memory, exercises the same real renderer and navigation, and restores the original catalog in a `finally` block. The song and video-detail checks require the exact full/teaser counterpart links and exclude self-links. These checks run on the composed release before upload; they do not change the public page size, sort order or selected-video catalog.

The owner supplied both original links again on 2026-11-24. The existing read-only two-video verifier was rerun as [43033346225, attempt 2](https://github.com/seirian/isegye-idol-fansite/actions/runs/43033346225/attempts/2). YouTube Data API v3 `videos.list` returned both videos at **2026-11-24T03:10:44.972014+00:00** (12:10:44 KST): the same STUDIO CHOOM channel, matching titles and publication timestamps, full performance `PT3M12S`, teaser `PT31S`, `privacyStatus: public`, and `embeddable: true`. This is a current public-metadata and availability check, not a full audiovisual playback review. The original catalog observation timestamp remains historical.

Reverification artifact: [14885801584](https://github.com/seirian/isegye-idol-fansite/actions/runs/43033346225/artifacts/14885801584), ZIP SHA-256 `2efc460e15b5310c4c3d8a19385aab36556d2c5fc5f8a5474d3097a15c01b4f5`.


## MBC Show! MusicCore — owner-selected stage

On 2026-11-14 the owner requested `sy40EGkSfRA`, from MBCkpop (`UCe52oeb7Xv_KaJsEzcKXJJg`). YouTube Data API v3 verification run 43573401740 confirmed the title `ISEGYE IDOL (이세계아이돌) - REBELS | Show! MusicCore | MBC261114방송`, public and embeddable status, duration 3:08, and publication 2026-11-14 15:37:04 KST. Checked 2026-11-14T07:56:19.498394+00:00. The title identifies the 2026-11-14 broadcast date separately from the video's publication timestamp. This is metadata verification, not full playback review.

The API reports HD, not a verified 4K resolution. Do not inherit STUDIO CHOOM's 4K label. The source blocks viewing in Japan (JP); preserve this in metadata and the detail summary. No video/audio is downloaded or rehosted. Only a source-linked catalog entry is registered.

`catalog/music-core-videos.json` and `scripts/music_core_videos.py` add exactly this one video, after the unchanged STUDIO CHOOM selection. The existing two uploads and original observation timestamps are preserved. Content > External, Music > Videos and the existing REBELS related-performance section include the new stage. Related sections derive publisher names from actual rows and sort full performances newest first, then teasers. MBCkpop has its own selected-video channel filter, not channel-wide collection.

No song, album, official MV, album/MV statistic, collection schedule, auth, member store or pinned review source is changed. The existing pre-upload external-video browser suite covers all three selected videos and source restrictions.


## M2 REBELS Relay Dance — owner-selected video

On 2026-11-17 the owner requested `mkJRSPYjX8k`. YouTube Data API v3 verification run 44057788105 confirmed `[릴레이댄스] 이세계아이돌(ISEGYE IDOL) - REBELS (4K)`, published by M2 (`UCTQVIXvcHrR9jYoJ6qaBAow`) on 2026-11-16 at 18:00:17 KST (09:00:17Z), duration 3:18, public and embeddable. Checked 2026-11-17T09:41:08.048557+00:00. The description identifies REBELS Relay Dance; this is public metadata verification, not full audiovisual playback review. The 4K label is explicitly based on the source title, not independently measured resolution.

`catalog/m2-relay-videos.json` and `scripts/m2_relay_videos.py` allow only the requested video, separate from the unchanged STUDIO CHOOM and MBC selections. The selected M2 channel is not added to scheduled whole-channel collection. Composition adds one video in Contents > External, Music > Videos and the REBELS related-performance section. Original MV, songs, album tracks/statistics, artist channel counters, collection schedules, login/access rules and pinned review sources are unchanged. Pre-upload browser tests verify the four selected external videos, original links, publication dates, relay classification, source labels, mobile layouts and preservation after runtime music refresh.
