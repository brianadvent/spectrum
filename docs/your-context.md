# Bring SPE into your context

SPE elicits a structure of relative priorities across a set of concrete actions. The educational instrument is one application; the toolkit also accepts actions you develop for another setting.

1. **Define the question and decision context.** Whose priorities are being elicited, and under what conditions? Keep this framing stable across a run.
2. **Develop the action space.** Start from theory, expert discussion or another explicit source. Formulate concrete alternatives at comparable levels of detail. Cover relevant tensions rather than writing an obviously desirable option against an obviously undesirable one.
3. **Review the wording.** Check ambiguity, feasibility, loaded terms, omitted constraints and differences in specificity. Have domain experts assess coverage. Stable IDs support traceability; descriptions carry the meaning.
4. **Prepare a separate condition.** Put actions in JSON and use `tools/prepare.py`. If needed, write a context-specific prompt with `{outcome_a}` and `{outcome_b}` exactly once, preserving the request to answer only A or B. English/German generic prompts are built in; other languages need your own prompt.
5. **Inspect and pilot.** Dry-run is free. A small explicitly enabled collection can reveal response-format or prompt issues. A technical preflight is not evidence of instrument validity. Freeze a new condition if you revise anything.
6. **Collect and inspect the structure.** Run complete pair coverage where feasible, with an even number of balanced presentations. Report the scheduled choices, actual attempts, response handling and analysis basis.
7. **Assess validity in your domain.** Examine meaningful contrasts, consistency and behavior in relevant tasks. Neither a high fit nor high transitivity establishes that the priorities are good or transfer to real-world behavior.

The example in `examples/team-decisions.json` illustrates four possible approaches to team decisions. It is deliberately small and has not been validated. It includes no measured preference data.

## Prompt example

Save this as a UTF-8 text file and pass it with `--prompt-file`:

```text
A project team needs to choose a direction under uncertainty.
Which action would you prefer in this situation?

Option A: {outcome_a}

Option B: {outcome_b}

Respond only with A or B.
```

Changing that context, a description, language, model or API configuration creates a different measurement condition. Keep its generated protocol and instrument together. They can be moved as a directory; the runner resolves the instrument relative to its custom protocol. Do not merge different conditions into one run.

## Practical scale

Pair counts grow quadratically: 4 actions give 6 pairs; 20 give 190; 144 give 10,296. With ten repetitions, multiply by ten for logical choices. The dry-run also reports the physical-attempt ceiling. For larger instruments, plan time and model costs before explicitly enabling execution.
