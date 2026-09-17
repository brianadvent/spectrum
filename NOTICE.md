# Provenance and attribution

The German instrument and runner originate in Daniel Autenrieth's dissertation research. German text, IDs and order are unchanged. The original source hash is recorded in `instrument/provenance.json`; the historical wrapper's incorrect 147-outcome metadata is replaced with the actual count of 144.

The English texts originate in `brianadvent/spe-explorer` at commit `fc854fa06fc2c3386c1363f3c0e28950a909a20e`, with the two editorial corrections documented in `docs/translation-review.md`.

`tools/run_spe.py` adapts the August 2026 SPE replication runner. `tools/statistics.py` adapts its generation-comparison analysis. Changes make paths portable, support explicit language/model conditions, persist retry limits, prevent concurrent writers and retain nondecisions. The analysis fits observed complete pairs only.

No code or full paper text from Mazeika et al. has been copied. Their Utility Engineering paper is credited as the methodological research reference. Python dependencies retain their own licenses.
