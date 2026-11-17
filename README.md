# llm-as-a-judge-pro-max

Original controls: [Sophia trace](scenarios/eval-awareness/SOPHIA_TRACE_CONTROL_PROMPT.md), [D-E5 trace](scenarios/eval-awareness/DE5_TRACE_CONTROL_PROMPT.md), [Sophia interview](scenarios/eval-awareness/SOPHIA_INTERVIEW_CONTROL_PROMPT.md), [D-E5 interview](scenarios/eval-awareness/DE5_INTERVIEW_CONTROL_PROMPT.md).

Treatment: [JUDGE_SYSTEM_PROMPT.md](scenarios/eval-awareness/JUDGE_SYSTEM_PROMPT.md). [AGENTS.md](AGENTS.md) guides contributors; the [scenario guide](scenarios/eval-awareness/guide.md) defines labels. `tests/test.py` sends each Hugging Face case as the user message.

[Hugging Face tests](https://huggingface.co/datasets/andyphu/llm-as-a-judge-pro-max-tests/tree/c4cc2948c4ff8e3823dba920708f14c5e46b6b10) contain 40 synthetic AI-agent-authored regression cases. The runner accepts a prompt path, pinned dataset revision, provider and model, and processes up to ten cases per invocation.
