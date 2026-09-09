# qwen-commit

Commit messages for your staged diff, written by a Qwen model running on your
machine. Your diff never leaves your laptop — no API key, no cloud, no
proprietary code phoned home.

```console
$ qwen-commit --provider ollama
feat(widget): add parse function to extract active nested widgets

New function parse extracts active nested widgets from a widget
```

Zero runtime dependencies (stdlib-only HTTP client), Python 3.10+.

## Quickstart

```bash
pip install git+https://github.com/richardcsuwandi/qwen-commit
git add -p                       # stage as usual
qwen-commit                      # print a suggestion
qwen-commit --commit             # or commit with it directly
qwen-commit --install-hook       # or let it prefill your editor on every commit
```

With the hook installed, `git commit` opens your editor with the suggestion
already in place (only when the message is still empty — your words always
win). An existing `prepare-commit-msg` hook is backed up to
`prepare-commit-msg.pre-qwen-commit`, never clobbered.

## Providers

| Provider     | Endpoint                                   | Default model          | Key source                           |
| ------------ | ------------------------------------------ | ---------------------- | ------------------------------------ |
| `ollama`     | local Ollama, native `/api/chat` (default recommended) | `qwen3:4b` | none needed              |
| `dashscope`  | DashScope compatible-mode                  | `qwen3-coder-plus`     | `QWEN_API_KEY` / `DASHSCOPE_API_KEY` |
| `modelscope` | ModelScope API-Inference                   | `Qwen/Qwen3-8B`        | `MODELSCOPE_API_KEY`                 |

Same resolution rules as [qwen-caption](https://github.com/richardcsuwandi/qwen-caption):
explicit flags beat `--provider`, which beats `QWEN_BASE_URL` / `QWEN_MODEL` /
`QWEN_PROVIDER` env vars. The ollama provider defaults to `num_ctx 8192`
(override with `--num-ctx`) because big diffs eat context fast.

## How it works

1. **Context**: `git diff --cached` plus your last `--log-lines` commits, so the
   model mimics the repository's existing message style instead of imposing one.
2. **Budget**: diffs over `--max-diff-chars` are truncated per file — head and
   tail of each file section, never mid-hunk, with a `[truncated N chars]`
   marker so the model knows what it didn't see.
3. **Prompt**: maintainer persona + hard rules (imperative subject ≤72 chars,
   body explains *why*, every claim grounded in the diff) + one of three styles:
   `conventional` (default), `plain`, `emoji`.
4. **Generate**: local-first via Ollama's native `/api/chat` (its
   OpenAI-compatible layer silently ignores `options.num_ctx`, which large
   diffs need), or any OpenAI-compatible Qwen endpoint.
5. **Deliver**: print, `--commit`, or editor prefill via `prepare-commit-msg`.

## Why small Qwen models are enough here

Commit-message generation is constrained decoding: the output space is a
one-line summary plus optional rationale, and the input already contains the
answer. A 4B Qwen3 with a disciplined prompt matches much larger models on
typical diffs — the prompt rules (subject length, imperative mood, grounding,
style mimicry from your log) do more work than parameters do. Reach for
`qwen3-coder-plus` or Qwen3-Coder on ModelScope when a diff is architectural
and the *why* needs real inference; stay local for the other 95%.

## Development

```bash
pip install -e .
python -m pytest
```

Tests are fully offline: a mock chat server for both wire formats, plus real
`git` repositories in temp dirs covering truncation, hook install/backup, and
a full hook-driven `git commit`.

## License

MIT
