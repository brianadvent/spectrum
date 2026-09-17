# Release 1.0.0 verification

Prepared 17 September 2026. Offline checks:

- 144 unique outcomes per language, matching IDs/order/principles/dimensions and JSON/CSV content.
- German IDs, order and texts exactly match the original instrument; the historical metadata count is corrected.
- All 144 translations read side by side; two corrections documented separately. This is an editorial, not empirical, review.
- Twenty-five unittest cases: known synthetic rankings, ties, cycles, missing edges, invalid input, canonical order mapping, protocol/language/model/hash resume guards, persistent attempt budget, retry exhaustion, recovery after logging a valid response, and local HTTP collection/resume/analysis.
- Provider payload/response handling is tested against local fixtures; no paid model endpoint was called.

Run the checks yourself using the commands in README.md. Actual provider credentials, account access and current availability of historical models remain environment-specific and were not tested by paid requests.
