```text
   _____ ____  ______     __
  / ___// __ \/ ____/____/ /________  ______ ___
  \__ \/ /_/ / __/ / ___/ __/ ___/ / / / __ `__ \
 ___/ / ____/ /___/ /__/ /_/ /  / /_/ / / / / / /
/____/_/   /_____/\___/\__/_/   \__,_/_/ /_/ /_/

  YOUR CONTEXT  ->  PAIRWISE CHOICES  ->  PREFERENCE STRUCTURES
```

# SPEctrum

SPEctrum collects pairwise choices from language models and estimates their relative preferences. Use the included educational dataset or define an instrument for another context.

[![Offline checks](https://github.com/brianadvent/spectrum/actions/workflows/check.yml/badge.svg)](https://github.com/brianadvent/spectrum/actions/workflows/check.yml)
[![Code: MIT](https://img.shields.io/badge/code-MIT-blue.svg)](LICENSE)
[![Data: CC BY 4.0](https://img.shields.io/badge/data-CC_BY_4.0-green.svg)](LICENSE-DATA)
[![Star on GitHub](https://img.shields.io/github/stars/brianadvent/spectrum?style=social)](https://github.com/brianadvent/spectrum)

[Deutsch](docs/README.de.md) · [Study Explorer](https://spe-explorer.autenrieth-partner.de) · [Adaptation guide](docs/your-context.md) · [Educational instrument](instrument/)

The educational dataset contains 144 action descriptions based on 48 principles developed in an expert Delphi study on AI in education. It covers educational attitudes, learning, competence development, aesthetic and emotional experience, social and democratic values, worldviews, future skills and preparation for advanced AI. It retains principles on which the panel agreed and those on which views differed.

German is the original language. English translations use the same item IDs and form a separate language condition. The repository includes the instrument and collection/analysis code, without collected model responses or individual expert ratings. Study results are presented in the [SPE Explorer](https://spe-explorer.autenrieth-partner.de).

The runner supports OpenAI Responses, Anthropic Messages and OpenAI-compatible Chat Completions endpoints. Runs record model, endpoint, language, prompt and instrument hash and can resume after interruption.

## Start with your context

Requires Python 3.12+, [uv](https://docs.astral.sh/uv/), and macOS/Linux (Windows: WSL).

```sh
git clone https://github.com/brianadvent/spectrum.git
cd spectrum
uv sync --frozen

# Freeze a small example: 4 actions, 6 pairs, 10 repetitions = 60 choices.
uv run python tools/prepare.py \
  --input examples/team-decisions.json --output-dir studies/team-decisions \
  --title "Team decisions" --language en

# Inspect the schedule. No API calls and no key required.
uv run python tools/run_spe.py --provider openai \
  --protocol studies/team-decisions/protocol.json --model YOUR_MODEL_ID
```

Replace the example with your own JSON file:

```json
{
  "outcomes": [
    {"id": "consult-team", "text": "Ask the team to discuss the options before deciding.", "dimension": "participation"},
    {"id": "delegate-decision", "text": "Let the person closest to the problem decide.", "dimension": "autonomy"}
  ]
}
```

`id` and `text` are required; `dimension` and `item` (principle) are optional. IDs must be unique and stable. `prepare.py` checks the instrument and writes its hash into a portable protocol next to it. Choose a new study directory for every changed condition. Use an even `--repetitions` count (default 10), and optionally `--prompt-file` with `{outcome_a}` and `{outcome_b}` exactly once each. The default custom prompt is domain-neutral. Other languages require an explicit translated prompt.

Select actions at comparable levels of detail and review their coverage and wording with domain experts. Pilot the prompt before collecting the full comparison set. The [adaptation guide](docs/your-context.md) describes these steps.

## Collect choices

Dry-run is always the default. Supply `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the process environment. Network runs require the execution switch and exact request ceilings. For the four-action example above:

```sh
uv run python tools/run_spe.py --provider openai --model YOUR_MODEL_ID \
  --protocol studies/team-decisions/protocol.json \
  --output-dir runs/team-decisions --execute \
  --confirm-requests 60 --confirm-max-api-attempts 72
```

Use the counts printed by your dry-run for your actual instrument. With $n$ actions and $k$ repetitions:

```math
N_{\mathrm{pairs}} = \binom{n}{2} = \frac{n(n-1)}{2}, \qquad N_{\mathrm{choices}} = k\,N_{\mathrm{pairs}}.
```

Half the presentations use each A/B order. The saved API-attempt budget includes retries and survives restarts; it limits requests, not currency cost. Model defaults in the bundled protocol reflect study snapshots. Specify an available model yourself; incompatible API settings must be explicitly edited in a separate protocol. Models are never silently substituted.

Repeat the identical command to resume. The manifest checks model, language, instrument hash, protocol, selected pairs and settings. Each run writes responses, attempts, usage/termination metadata, complete-pair preferences and an audit. Outputs and keys belong outside version control.

## Other models and local servers

Use `--provider compatible` with a server that implements `/chat/completions`. Pass its API base URL and exact model ID. This command prepares a dry-run against a local Ollama server:

```sh
uv run python tools/run_spe.py --provider compatible \
  --base-url http://localhost:11434/v1 --no-auth --model YOUR_LOCAL_MODEL \
  --protocol studies/team-decisions/protocol.json
```

For a hosted service, put its key in an environment variable and name that variable with `--api-key-env` (default `SPE_API_KEY`). For example, Gemini provides a compatible endpoint:

```sh
uv run python tools/run_spe.py --provider compatible \
  --base-url https://generativelanguage.googleapis.com/v1beta/openai \
  --api-key-env GEMINI_API_KEY --model YOUR_GEMINI_MODEL \
  --protocol studies/team-decisions/protocol.json
```

Add `--output-dir`, `--execute` and the two request budgets shown above to collect responses. `--no-auth` is limited to local loopback addresses. The adapter sends `model`, `messages` and `max_tokens`; it records response text, model, token usage and finish reason. Servers must support those fields. See the [Ollama](https://docs.ollama.com/api/openai-compatibility) and [Gemini](https://ai.google.dev/gemini-api/docs/openai) API documentation.

The educational protocol limits output to 16 tokens. Use `--max-output-tokens` when a model needs a larger budget, including for internal reasoning. The changed limit is recorded as part of the run condition. Start with `--preflight-pairs 1` in a separate output directory to check the response format. Compatibility is tested with a local simulated server; no hosted-provider run is claimed for this release.

## Analyze your study

```sh
uv run python tools/analyze.py --input runs/team-decisions/preferences.json \
  --instrument studies/team-decisions/instrument.json \
  --output-dir results/team-decisions
```

Outputs: `analysis.json` and `utilities.csv`, with mean observed choice rates, Thurstone utilities, fit and coherence. Instrument and language must match the collected run. Utilities describe relative priorities within your selected actions, not absolute quality.

```math
P(A \succ B) = \Phi\!\left(\frac{\mu_A-\mu_B}{\sqrt{2}}\right).
```

Thurstone Case V uses unit variance, centered utilities and equal weights for complete pairs. Directional accuracy is in-sample and excludes tied majorities. Transitivity uses triples with three observed strict majorities. Missing choices are not imputed; disconnected comparison graphs are rejected. See [protocol and analysis details](docs/protocol.md).

## Use the educational instrument

```sh
uv run python tools/validate.py
uv run python tools/run_spe.py --provider openai                 # German original
uv run python tools/run_spe.py --provider anthropic --language en
```

144 descriptions, 48 principles, eight dimensions, 10,296 pairs, ten repetitions, 102,960 scheduled choices. JSON and CSV versions are in `instrument/`. German preserves the original texts. English is a reviewed, separate language condition; cross-language measurement equivalence has not been established. See [provenance](instrument/provenance.json) and the [translation review](docs/translation-review.md). The [original paper supplement](https://github.com/brianadvent/education-llm-spe-study) remains separate.

## Check, cite and contribute

```sh
uv run python -m unittest discover -s tests -v
```

Tests use synthetic responses and local fixtures, including custom instruments, balanced ordering, resume guards, budgets, ties and missing decisions. No paid calls are made by tests or CI.

- Autenrieth (2026), [How AI Systems Think About Education](https://arxiv.org/abs/2603.21006).
- Mazeika et al. (2025), [Utility Engineering](https://arxiv.org/abs/2502.08640).

Use `CITATION.cff` for SPEctrum and cite the research paper separately. Report the exact release, instrument, language, model, prompt and protocol.

## License

Copyright © 2026 Daniel Autenrieth.

| Material | License |
| --- | --- |
| Python code, tests and CI workflows | [MIT License](LICENSE) |
| Educational dataset, example instruments and documentation | [Creative Commons Attribution 4.0 International](LICENSE-DATA) |

Both files contain the full license text. [REUSE.toml](REUSE.toml) assigns SPDX license identifiers to repository files. For the dataset, credit Daniel Autenrieth, link to this repository and the [CC BY 4.0 license](https://creativecommons.org/licenses/by/4.0/), and indicate changes. Research citations are provided in [CITATION.cff](CITATION.cff). Third-party attribution is in [NOTICE.md](NOTICE.md).
