# Approved static profile cache recovery

Production run 43375601709 failed before upload because the Genie portrait request timed out. This is distinct from the already repaired gallery HTTP 302.

The twelve files are byte-identical to successful reviewed CI artifact 14013037326 (run 43371356598), ZIP SHA-256 a8716a00ac0ebec079f0a05bfc4954f072923a4670689281214552622770351b, and the earlier successful site artifact 13812453298 (run 42922168252). Genie derivative hashes already match the unchanged review/portraits.json. SOOP original identities and observation dates are bound to the cache manifest and unchanged.

Ordinary builds perform no Genie/SOOP profile or gallery image requests. Missing/tampered cached images stop the build, rather than following redirects or substituting images. Explicit test fetchers and source verification functions remain separate.

No collection schedule, publication history, shared write lock, access policy, account or authorization code changed. The temporary branch-only cache import workflow is removed before production merge.
