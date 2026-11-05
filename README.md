# claude-reword

## Use case
I did this for fun because I had a free weekend with nothing better to do, I live solving specific engineering problems, so I found a solution for the watermark pipeline for fun, of-course you can use this as you like. This is a hobby project for me.

A `/reword` slash command for [Claude Code](https://claude.com/claude-code), plus the small Python tool behind it.

You ask Claude to write something (an essay paragraph, notes, a Word document). Instead of showing Claude's own draft, it sends the draft to an LLM API (OpenAI, DeepSeek or Anthropic) to be reworded, and delivers that version, either in chat or straight into a file like `report.docx`.

- Keeps facts, numbers, code, URLs and meaning unchanged.
- Word (.docx) support: builds a new `.docx`, or rewords an existing one in place, keeping styles, tables, images and layout.
- It checks that numbers, URLs and code survived. If not, the rewrite is discarded.
- Reword mode stays on for the session until you say "stop".
- With no API key set, it prints `no api my guy` and sends nothing anywhere.
- An optional hook can also make a `_paraphrased` copy of any prose file Claude writes.

## Quick start

```bash
git clone https://github.com/Trigodil/claude-reword.git
cd claude-reword
./install.sh
```

Then put at least one API key in `~/.claude/hooks/reword.env` (it's created from the empty template and never committed), restart Claude Code, and run:

```
/reword one paragraph on jets
```

Name a provider or model in the request to override the default, e.g. `/reword ... with deepseek-reasoner`.

See [`CLAUDE.md`](CLAUDE.md) for full setup details, including the optional auto-hook.

## Files

| File | Purpose |
|---|---|
| `hooks/paraphrase_review.py` | The reword tool |
| `hooks/reword_prompt.txt` | Editable rewrite prompt |
| `hooks/reword.env` | Empty key template, keep it empty in git |
| `commands/reword.md` | The `/reword` command |
| `install.sh` | Copies everything into `~/.claude/` |
