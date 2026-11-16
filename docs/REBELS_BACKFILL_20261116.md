# REBELS Melon historical repair — 2026-11-16

User-requested scope: only REBELS (Melon song 603813508, album 15120216), from release **2026-11-09 18:00 KST** through the inspected source cutoff **2026-11-16 09:00 KST**. Other songs, providers, current chart clocks and collection schedules are unchanged.

## Verified audit

Baseline: published observation artifact 14187286366, run 43777601996, digest `774db6baa173b57d7a64d873da5e4c231846cd573506d9caa2f251a6c54cddf6`.

| Chart | Existing valid hours | Added ranked | Added verified chart-out | Final valid hours | Unresolved / not provided |
|---|---:|---:|---:|---:|---|
| TOP100 | 56 | 58 | 45 | 159/160 | 2026-11-10 16:00 KST remains unverified |
| HOT100 (100 days) | 56 | 68 | 1 | 125/125 published source slots | 35 hours, 02:00–06:00 on November 10–16, have no source rows |

Total: **172 observations added**, no conflicting existing values. First ranked observation on both charts is November 9 at 19:00 KST: TOP100 97, HOT100 11. The release-hour 18:00 chart was checked separately and REBELS was absent from each complete 100-song list; it is not assigned a fabricated rank.

TOP100 November 10 at 16:00 was not a complete 100-song chart in the secondary archive. Its empty trend entry cannot prove chart-out. It remains missing, not zero, 101, interpolated or forward-filled.

## Evidence and attribution

Public historical data source: **가이섬**.

- TOP100: https://xn--o39an51b2re.com/chart/melon/top100/trend/ranking/603813508
- HOT100: https://xn--o39an51b2re.com/chart/melon/hot100-d100/trend/ranking/603813508
- Terms / attribution: https://xn--o39an51b2re.com/policy

The bounded one-time page review used the rendered page's `__NEXT_DATA__`, not graph pixel estimates or an undocumented partner API. It checked exact song ID, album ID, chart type, hourly timestamps and numeric ranks. Complete dated chart pages independently proved each added chart-out observation by checking the source clock, 100 unique songs and exact ranks 1–100. Requests with date query parameters were found to return the current chart and were rejected; only verified `/chart/melon/<kind>/<date>/<hour>` pages are accepted.

Rank evidence: run 43782307006, artifact 14187774745, archive SHA256 `d3902c890ff4d42e4d221b36ae4aceea26b59691332e929bfa8ff3cb75ab9a5c`.
Dated complete-chart evidence: run 43782800358, artifact 14188916741, archive SHA256 `0670d300c8115aa4148b48bf677b5ccfa2d86b62ab3e61b5c5bca1ddfd17076e`.
Each accepted source page URL and SHA256 is retained with the finite reviewed factual dataset. No lyrics, images, source UI, other songs' rankings or visitor data are republished.

## Application and safety

`scripts/rebels_melon_backfill.py audit --snapshot <path>` computes a candidate and exact before/after report without remote writes.
`publish` requires the existing main-only production connection, owner/host-key checks, pause controls and deployed source attribution. It uses the album lock, compares the live bytes before replacement, saves the prior feed and verifies readback. Failed readback restores the previous bytes when ownership still matches. No collection or original publication timestamp is refreshed by the historical repair.

The existing daily collector reuses only this finite local dataset within its normal 30-day retention window, preserving the repaired observations and attribution. It makes **no recurring requests to 가이섬**. Conflicting existing valid observations win; the dedicated repair refuses publication on conflicts. A one-time workflow runs after successful production deployment of the specifically tagged repair commit; unrelated production commits do not trigger a repair job.

The UI adds the source link and distinguishes the known incomplete TOP100 slot and HOT100 source-absent night hours. Existing album layout and all other song data remain intact. The original album approval anchor is retained with an explicit source-attribution amendment and updated checksums.

Publication success must be established separately using `rebels-backfill-report.json` and verified live readback; this source review alone is not a deployment claim.
