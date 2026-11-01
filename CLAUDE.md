# Setup instructions for Claude

This repo is a `/reword` slash command for Claude Code plus the Python tool behind it. The user has just cloned it and wants it working. When they ask you to set it up (or open this repo and say "set this up"), follow the steps below in order, and tell them what you did at the end.

What it does: the user runs `/reword <what to write>`. You write the content, send it through an LLM API (OpenAI, DeepSeek or Anthropic) to be reworded, and deliver that version, either in chat or into a file (`.docx`, `.tex`, `.md`, `.txt`).

## 1. Install the files

From the repo root, run:

```bash
./install.sh
```

It copies into `~/.claude/`:
- `hooks/paraphrase_review.py` and `hooks/reword_prompt.txt`
- `commands/reword.md` and `commands/reword_paraphrased.md`
- `hooks/reword.env`, created from the empty template **only if the user has none yet**. An existing one is never overwritten.

Requires `python3` (standard library only, nothing to pip install). If `python3` is missing, tell the user to install it.

## 2. Have the user add their API key

**Do not open, read, print or edit `~/.claude/hooks/reword.env`.** It holds the user's secret key. Ask the user to do this step themselves:

> Open `~/.claude/hooks/reword.env` and paste in at least one key:
> `OPENAI_API_KEY=sk-...`, `DEEPSEEK_API_KEY=...` or `ANTHROPIC_API_KEY=sk-ant-...`

Notes to pass on:
- Keys in this file take priority over keys exported in the shell, so a stale `OPENAI_API_KEY` in the environment can't shadow it.
- With no key set, the tool prints `no api my guy` and sends nothing anywhere.
- If the user would rather not edit the file, they can export the key in the shell that launches Claude Code. It is only used when the file has none.

Wait for the user to confirm they've added the key before step 3.

## 3. Check that it works

Run this small test. It prints only a status line, never the key:

```bash
printf 'Planes fly fast at high altitude.\n' > /tmp/reword_test.txt
python3 -I ~/.claude/hooks/paraphrase_review.py --reword /tmp/reword_test.txt /tmp/reword_test_out.txt
```

- `[reworded with <provider>] saved to ...` → working.
- `no api my guy` → no key found; go back to step 2.
- `... call failed: HTTP Error 401` → the key is invalid or belongs to a different provider; ask the user to check it. Do not go looking for the key yourself.

## 4. Tell the user how to use it

Restart Claude Code (or open a new session), then:

```
/reword one paragraph on jets
/reword summary in report.docx
/reword intro section in paper.tex
```

- Reword mode stays on for the session; they say "stop" to turn it off.
- Name a provider or model in the request to override the default, e.g. `/reword ... with deepseek-reasoner`. The default is OpenAI `gpt-6-luna`; if their account uses other models, edit the `PROVIDERS` table at the top of `~/.claude/hooks/paraphrase_review.py`.
- The rewrite prompt is editable in `~/.claude/hooks/reword_prompt.txt`.

## 5. Optional: auto-paraphrase hook

Only do this if the user asks. It makes every Write/Edit of a `.md`, `.tex`, `.txt` or `.rst` file also produce a `<name>_paraphrased<ext>` copy plus a diff. Add this to `~/.claude/settings.json`, merging with any existing `hooks` instead of replacing them, and show the user the change first:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 -I ~/.claude/hooks/paraphrase_review.py",
            "timeout": 60,
            "statusMessage": "Paraphrasing prose file..."
          }
        ]
      }
    ]
  }
}
```

## How the tool treats files (for your reference)

- **Safety checks:** if a rewrite changes numbers, URLs, LaTeX commands or math, it is discarded and the original is kept.
- **`.docx` input:** only paragraph text is replaced; styles, tables, images and layout are kept. Text in tables is reworded; headers, footers and footnotes are left alone. Mixed formatting inside one paragraph (e.g. one bold word) takes the first run's style.
- **`.docx` output:** always written as a new file. Ask before overwriting an existing one.
- When delivering into a file, use `cp`/`cat` through Bash, not the Edit/Write tools (those would trigger the auto-hook and reword twice).

## Files

| File | Purpose |
|---|---|
| `hooks/paraphrase_review.py` | The tool (`--reword IN OUT` CLI mode, plus hook mode) |
| `hooks/reword_prompt.txt` | Editable rewrite prompt |
| `hooks/reword.env` | Empty key template, copied to `~/.claude/hooks/` by `install.sh` |
| `commands/reword.md` | The `/reword` command |
| `commands/reword_paraphrased.md` | Variant of the same command with alternate wording |
| `install.sh` | Copies everything into `~/.claude/` |
