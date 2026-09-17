# SPE replication

Reproduce **Structured Preference Elicitation** with 144 educational action descriptions derived from 48 Delphi principles across eight dimensions. Daniel Autenrieth · instrument release 1.0.0.

[Deutscher Einstieg](docs/README.de.md) · [Explore study results](https://spe-explorer.autenrieth-partner.de) · [Instrument provenance](instrument/provenance.json) · [Translation review](docs/translation-review.md)

This repository contains the instrument and code. It contains **no collected model responses, study preference results or human ratings**. Test data are generated synthetically in tests. The [original paper supplement](https://github.com/brianadvent/education-llm-spe-study) is a separate historical repository.

## Quick start (no API calls)

Python 3.12 or later, macOS or Linux, and [uv](https://docs.astral.sh/uv/) are required. On Windows use WSL (the runner uses a POSIX process lock).

```sh
git clone https://github.com/brianadvent/spe-replication.git
cd spe-replication
uv sync --frozen
uv run python tools/validate.py
uv run python tools/run_spe.py --provider openai
uv run python tools/run_spe.py --provider anthropic --language en
uv run python -m unittest discover -s tests -v
```

Without `--execute`, the runner validates the local instrument and schedule only. It does not need a key and makes no network requests. JSON and CSV instruments are in `instrument/`. Each row has `id`, `item` (source principle), `dimension`, and `text`.

## Design

All 10,296 unordered pairs of the 144 outcomes are presented ten times: five canonical and five reversed A/B orders, interleaved by repetition. Each full run schedules 102,960 logical decisions. A physical API attempt is a separate unit: retries increase requests, not sample size. No system/developer prompt or sampling parameters are sent. The German prompt and original texts are preserved; historical metadata incorrectly declaring 147 outcomes is corrected in the released wrapper.

German (`--language de`, default) is the original measurement condition. English (`--language en`) uses a reviewed translation and translated prompt. **Cross-language measurement equivalence has not been established.** Never pool language conditions as if they were the same instrument.

`tools/protocol.json` freezes the instrument hashes and API settings. The included model IDs are the historical study configurations, not a claim of current availability. Use `--model YOUR_MODEL_ID` for another model. Models are never silently substituted. If a model requires different reasoning, token limits or other settings, copy and explicitly edit the protocol, pass `--protocol PATH`, and report the change as a different condition.

## Run your own experiment

Provide `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the process environment, or use `--env-file` with a private file outside the repository. Never commit keys or run outputs.

First inspect a small dry-run:

```sh
uv run python tools/run_spe.py --provider openai --preflight-pairs 2
```

An explicitly enabled **paid** preflight:

```sh
uv run python tools/run_spe.py --provider openai --preflight-pairs 2 \
  --output-dir runs/preflight-de --execute \
  --confirm-requests 20 --confirm-max-api-attempts 24
```

For a full run, omit `--preflight-pairs`, choose a new output directory and set `--confirm-requests 102960 --confirm-max-api-attempts 123552`. The physical-attempt ceiling is persisted, includes retries, and is not reset on restart. It limits requests, not currency cost. Estimate costs for your actual model before running.

Repeat the identical command to resume an interrupted run. Model, language, effective protocol, instrument hash, selected pairs and run settings are checked against the saved manifest. Different conditions require different directories. Concurrent writers to one directory are blocked.

The strict parser accepts only A or B after trimming whitespace and normalizing case. Other replies are logged rather than counted as B. Up to 15 content-bearing attempts per logical decision are allowed, subject to the global ceiling. Retry counts survive interruption. Exhausted decisions are closed as nondecisions; rerunning does not reopen them. Transport failures and 429/5xx responses are retried within the configured limits; permanent API errors stop the run.

This protocol preserves the collection format. The Explorer's Sonnet-5 results additionally use a separate audited semantic recoding of the earliest unambiguous choice. The strict runner does **not** claim to implement that case-reviewed recoding.

## Outputs and analysis

Each run writes a manifest, response JSONL, attempt JSONL, persistent budget, complete-pair preferences and audit. Raw texts, returned model IDs, usage and termination metadata remain available for inspection. Failed or interrupted runs retain their logs; resume before analyzing the final aggregate. A closed run with nondecisions returns exit code 1 and documents incomplete pairs.

```sh
uv run python tools/analyze.py --input runs/preflight-de/preferences.json \
  --language de --output-dir results/preflight-de
```

Analysis produces `analysis.json` and `utilities.csv`. Only pairs with ten valid choices enter the preference aggregate; there is no imputation. Thurstone Case V fitting uses sigma=1 and centered utilities, with equal weight per complete pair. Accuracy is in-sample agreement with observed majority direction, excluding 5:5 ties. Transitivity enumerates all triples with three observed strict majorities. Missing edges and ties are excluded from its denominator. Disconnected comparison graphs are rejected; outcomes absent from a small sample are listed. Sparse samples do not provide a full-instrument ranking.

Utilities measure relative preference within this instrument. They are not pedagogical quality scores. Magnitudes from separately fitted models are not calibrated absolute differences. Historical provider/model availability, response handling and collection infrastructure constrain exact replication.

## Sources and citation

- Autenrieth (2026), [How AI Systems Think About Education](https://arxiv.org/abs/2603.21006).
- Mazeika et al. (2025), [Utility Engineering](https://arxiv.org/abs/2502.08640).
- [OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create) and [Anthropic Messages API](https://platform.claude.com/docs/en/api/messages/create).

Use `CITATION.cff` for the software/instrument and cite the research paper separately. Cite the exact release, language, model, prompt and protocol used. The collected study results are available in the Explorer.

## License

Own code (`tools/`, `tests/`, workflow): MIT, see `LICENSE`. Instrument and documentation: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/), see `LICENSE-DATA`. Dependencies retain their own licenses. No third-party paper full texts are included. See `NOTICE.md` for provenance.
