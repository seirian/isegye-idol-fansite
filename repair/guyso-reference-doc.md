# Guyso peak reference migration — 2026-11-18 KST

Owner-requested changes: remove the source labels/links inside the seven peak cards, retain the exact “최고 성적 출처와 확인 시각” expandable section, and replace the actual reference provider for all registered Melon songs with 가이섬. All seven cards, including daily peaks, use the same verified provider. Original Melon achievement objects remain unmodified as separate data; this is not a relabeling of those objects.

## Actual source review

The 26 registered titles contain 24 linked Melon songs and two video-only entries (But You Want More and 이세돌 싸이퍼). On 2026-11-18 01:03–01:04 KST, each of the 24 exact Guyso Melon song pages was retrieved and checked against registered song ID, album ID, title and artist. The source summary provides 164 numeric peak ranks across 168 song/chart combinations. The four absent entries are the two HOT100 periods for RE : WIND and 겨울봄; they remain unknown, not zero or chart-out. Summary achievement dates are not supplied and are not borrowed from the former provider.

Evidence run: 44121379741. Archive SHA256: `d5e96d12958d874d9fa5cf0263ffb46cd8724c638b46807a845f1d00bbab005a`.
Reviewed dataset SHA256: `57a8e8d48d3cfa5b7311f2483ba08dab528f34780b2816739ec490cb63a7b776`.
The reviewed dataset contains only identities, seven rank fields and response provenance, not source HTML, images, lyrics or other songs’ data.

## Runtime and UI

Peak cards display chart name, rank and date availability; no card source label or link. Source links and actual confirmation time are retained in the expandable table. The explanatory source text is also inside the expandable section only. HOT100 30/100-day and newest week/month are distinct. Missing source values remain dashes. Old Isegyechart references are rejected by both the frontend and active collector and its URL allowlist; they are never relabeled as Guyso.

The existing record collection uses exact registered Melon IDs, with a six-hour per-song cache to avoid hourly duplicate requests. No schedule or hourly chart collection policy changes. Cached and failed refreshes retain the real source confirmation timestamp. Failures can retain only previously verified Guyso values, not the former provider’s values. The approved historical backfill and all chart time-series fields are preserved.

The build migrates only a generated snapshot copy; the original approved seed files and manifest are immutable. The one-time owner-requested maintenance publisher runs only after the source-details-only UI is deployed, retains existing pause variables, main-only/host/owner gates, uses the album lock, compares live bytes, backs up the old feed and verifies readback. It does not run an hourly collection, change source/collection clocks, or read account stores. Subsequent periodic work still respects existing night pauses.

Production success must be established separately from the publication artifact; source review and test completion alone do not claim publication.
