```text
   _____ ____  ______     __
  / ___// __ \/ ____/____/ /________  ______ ___
  \__ \/ /_/ / __/ / ___/ __/ ___/ / / / __ `__ \
 ___/ / ____/ /___/ /__/ /_/ /  / /_/ / / / / / /
/____/_/   /_____/\___/\__/_/   \__,_/_/ /_/ /_/

  YOUR CONTEXT  ->  PAIRWISE CHOICES  ->  PREFERENCE STRUCTURES
```

# SPEctrum

**Structured Preference Elicitation for your context.** Define the actions that matter in your field, let language models compare them, and examine the resulting preference structure.

[![Offline checks](https://github.com/brianadvent/spectrum/actions/workflows/check.yml/badge.svg)](https://github.com/brianadvent/spectrum/actions/workflows/check.yml)
[![Star on GitHub](https://img.shields.io/github/stars/brianadvent/spectrum?style=social)](https://github.com/brianadvent/spectrum)

[Deutsch](docs/README.de.md) · [Study Explorer](https://spe-explorer.autenrieth-partner.de) · [Adaptation guide](docs/your-context.md) · [Educational instrument](instrument/)

SPEctrum turns concrete action descriptions into a balanced pairwise study: prepare an instrument, inspect its schedule, collect choices with an explicit budget, and estimate relative utilities and coherence. It supports OpenAI and Anthropic, interrupted-run recovery, and separately recorded language/model conditions.

The included **144 educational descriptions in German and English** are a worked research instrument. You can use them or bring your own. No collected model responses, study preference data, or human ratings are included. The small team-decisions example is illustrative, not a validated instrument.

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

**Design comes before running.** Select a relevant set of comparable actions, check how wording frames each alternative, and pilot the prompt. A new context is a new instrument; it does not inherit the educational instrument's validation. See the [adaptation guide](docs/your-context.md).

## Collect choices

Dry-run is always the default. Supply `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in the process environment. Both the execution switch and exact request ceilings are required for a paid run. For the four-action example above:

```sh
uv run python tools/run_spe.py --provider openai --model YOUR_MODEL_ID \
  --protocol studies/team-decisions/protocol.json \
  --output-dir runs/team-decisions --execute \
  --confirm-requests 60 --confirm-max-api-attempts 72
```

Use the counts printed by your dry-run for your actual instrument. With $n$ actions and $k$ repetitions:

$$N_{\mathrm{pairs}} = \binom{n}{2} = \frac{n(n-1)}{2}, \qquad N_{\mathrm{choices}} = k\,N_{\mathrm{pairs}}.$$

Half the presentations use each A/B order. The saved API-attempt budget includes retries and survives restarts; it limits requests, not currency cost. Model defaults in the bundled protocol reflect study snapshots. Specify an available model yourself; incompatible API settings must be explicitly edited in a separate protocol. Models are never silently substituted.

Repeat the identical command to resume. The manifest checks model, language, instrument hash, protocol, selected pairs and settings. Each run writes responses, attempts, usage/termination metadata, complete-pair preferences and an audit. Outputs and keys belong outside version control.

## Analyze your study

```sh
uv run python tools/analyze.py --input runs/team-decisions/preferences.json \
  --instrument studies/team-decisions/instrument.json \
  --output-dir results/team-decisions
```

Outputs: `analysis.json` and `utilities.csv`, with mean observed choice rates, Thurstone utilities, fit and coherence. Instrument and language must match the collected run. Utilities describe relative priorities within your selected actions, not absolute quality.

$$P(A \succ B) = \Phi\!\left(\frac{\mu_A-\mu_B}{\sqrt{2}}\right).$$

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

Use `CITATION.cff` for SPEctrum and cite the research paper separately. Report the exact release, instrument, language, model, prompt and protocol. Issues and pull requests for new context examples, adapters and methodological improvements are welcome. If SPEctrum is useful, give it a **Star** using GitHub's button above.

Own code: MIT (`LICENSE`). Included educational items, examples and documentation: CC BY 4.0 (`LICENSE-DATA`). Your own inputs remain yours; these licenses do not automatically relicense them. Dependencies retain their licenses. See `NOTICE.md`.
