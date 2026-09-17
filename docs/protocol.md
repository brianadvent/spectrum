# Collection and analysis details

Every unordered pair is presented `k` times, with canonical order on even repetitions and reversed order on odd repetitions. `k` must be even. Responses are back-coded to canonical action IDs before aggregation. The default is ten repetitions.

The parser accepts exactly A or B after trimming and uppercasing. Other replies are logged and retried within the protocol limits. They are never silently counted as B. Default settings permit at most 15 content-bearing attempts per logical choice, subject to the global physical-attempt budget. Transport retries are separate. Retry counts and the global budget survive restarts; permanent API errors stop the run. No system prompt or sampling overrides are supported by this runner.

Use `--preflight-pairs N` to inspect or explicitly collect the first N pairs in a separate directory. `--pair-indices-file` selects a fixed subset. Neither creates a full-instrument study. The manifest prevents accidental mixing of settings or instruments. Simultaneous writers to the same run are blocked.

The aggregate includes only pairs with all `k` valid choices. Nondecisions remain in logs and the audit. Interrupted runs should be resumed before final analysis. A closed run with nondecisions returns exit code 1. Strict response parsing differs from the separate, case-reviewed semantic recoding used for the Explorer's Sonnet-5 analysis.

`analyze.py` accepts one preference aggregate and its exact instrument. It verifies the stored hash and language when present. The runner always supplies both. Hand-authored historical inputs without those fields cannot receive the same provenance verification. It does not merge runs.

Analysis fits Thurstone Case V to complete-pair probabilities with equal weight, unit variance and mean-zero utilities. Accuracy is the agreement of fitted ordering with observed majority direction in the same data, excluding ties. Coherence enumerates all triples with three observed strict majorities; missing edges and tied edges are excluded. Outcomes without any comparisons are listed as excluded. Disconnected comparison graphs are rejected because one common utility scale is unidentified. Sparse samples or near-perfect separation can produce unstable utility magnitudes.

API adapters: [OpenAI Responses](https://developers.openai.com/api/reference/python/resources/responses/methods/create), [Anthropic Messages](https://platform.claude.com/docs/en/api/messages/create). Consult the provider's current model documentation when choosing settings. The toolkit never substitutes another model for an unavailable model ID.

The `compatible` adapter uses Chat Completions with an explicitly supplied base URL and model. Endpoint, authentication mode, key-variable name (never the key) and output-token limit are part of the saved condition. Changing them requires a separate run directory. Compatible endpoints need not report a service tier; their audit checks coverage, ordering and duplicate responses without imposing OpenAI or Anthropic tier names.
