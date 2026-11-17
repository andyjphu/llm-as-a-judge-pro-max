# Agent guidance

For each judge study, define the construct, unit, evidence channels and labels. Freeze the source manifest and model-visible prompt bytes. Record input, prompt, model and parser hashes with results; retain incomplete calls and prior versions. Verify positive citations against source blocks. Treat judge labels as model observations and name each reviewer's type.

Read candidate misses and hard negatives in their source context. Use development examples for prompt edits and keep held-out cases private until the prompt is frozen. Test one case, then batches of at most ten. Compare old and new prompts on the same reviewed cases; report disagreement counts and denominators for that sample. Stop on invalid output, unknown provider status or a material disagreement. Present the prompt change, observed errors and expected cost to Andy before seeking approval for a full cohort.

Report each cohort and channel separately: outward text, tool-argument prose, returned reasoning and exit interviews. Quote a source-verified example when a surprising score drives the conclusion. Describe artifacts for their actual reader through the properties that help that reader use them. Put methodological detail where it changes interpretation.

This repository is public. Store credentials, raw private trajectories, provider responses, source-ID maps and held-out labels in owner-controlled storage. Use short examples whose meaning survives sanitation; mark paraphrases. Have a second reviewer inspect release safety and source fidelity before publication. Follow the credential owner's rotation procedure if a key enters Git history.

The [scenario guide](scenarios/eval-awareness/guide.md) defines evaluation-awareness labels. The model-facing prompt is [JUDGE_SYSTEM_PROMPT.md](scenarios/eval-awareness/JUDGE_SYSTEM_PROMPT.md). `tests/test.py` sends a dataset packet as the user message. Obtain explicit authorization for model calls and full-cohort runs.
