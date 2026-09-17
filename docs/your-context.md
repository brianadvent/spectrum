# Bring SPE into your context

To apply SPE in another field, define the actions to compare and the context in which the model should choose.

1. **Define the question and decision context.** Specify the model, its task and the conditions under which it chooses. Use the same framing throughout a run.
2. **Develop the action space.** Start from theory, expert discussion or another explicit source. Formulate concrete alternatives at comparable levels of detail. Cover relevant tensions rather than writing an obviously desirable option against an obviously undesirable one.
3. **Review the wording.** Check ambiguity, feasibility, loaded terms, omitted constraints and differences in specificity. Have domain experts assess coverage. Assign a stable ID to each action.
4. **Prepare a separate condition.** Put actions in JSON and use `tools/prepare.py`. If needed, write a context-specific prompt with `{outcome_a}` and `{outcome_b}` exactly once, preserving the request to answer only A or B. English/German generic prompts are built in; other languages need your own prompt.
5. **Inspect and pilot.** Dry-run is free. A small explicitly enabled collection can reveal response-format or prompt issues. Prepare a new condition if you revise the wording or settings.
6. **Collect and inspect the structure.** Run complete pair coverage where feasible, with an even number of balanced presentations. Report the scheduled choices, actual attempts, response handling and analysis basis.
7. **Assess validity in your domain.** Examine meaningful contrasts, consistency and behavior in relevant tasks. Fit and transitivity measure properties of the elicited choices. Assess performance in relevant tasks separately.

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

Pair counts grow quadratically: 4 actions give 6 pairs; 20 give 190; 144 give 10,296. With ten repetitions, multiply by ten for logical choices. The dry-run also reports the physical-attempt ceiling. Estimate runtime and model costs from a small pilot before running a larger instrument.
