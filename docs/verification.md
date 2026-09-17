# Release 1.0.0 verification

Prepared 17 September 2026. Offline checks:

- 144 unique outcomes per language, matching IDs/order/principles/dimensions and JSON/CSV content.
- German IDs, order and texts exactly match the original instrument; the historical metadata count is corrected.
- All 144 translations read side by side; two corrections documented separately. This is an editorial, not empirical, review.
- Twenty-five unittest cases: known synthetic rankings, ties, cycles, missing edges, invalid input, canonical order mapping, protocol/language/model/hash resume guards, persistent attempt budget, retry exhaustion, recovery after logging a valid response, and local HTTP collection/resume/analysis.
- Provider payload/response handling is tested against local fixtures; no paid model endpoint was called.

Run the checks yourself using the commands in README.md. Actual provider credentials, account access and current availability of historical models remain environment-specific and were not tested by paid requests.

## SPEctrum 1.1.0

The context-adaptation release adds preparation of arbitrary instruments, portable protocol-relative paths, custom prompts/languages, even repetition counts and instrument-aware analysis. Twenty-eight offline tests pass, including a four-action, four-repetition custom condition, balanced back-coding, custom analysis, modified-instrument rejection, language isolation, input validation and refusal to overwrite a prepared condition. The bundled educational instruments are unchanged.

## SPEctrum 1.2.0

The Chat Completions adapter adds explicit endpoint/model selection, named key environment variables and optional authentication-free loopback access. Thirty-three offline tests pass. A local HTTP test covers invalid-response retry, ten balanced presentations, a 0.5 aggregate for a model that always answers A, resume without repeated requests, and rejection of a changed endpoint. Additional checks cover response metadata, dry-run isolation and redirects. Hosted providers were not called.

License texts and file assignments are checked with REUSE. README and German documentation now describe the educational dataset as Delphi-based, retaining both consensus and dissent. The educational item files are unchanged.
