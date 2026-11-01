# Setup instructions for Claude

This repo provides a `/reword` slash command for Claude Code and the Python tool that powers it. The user has just cloned it and wants to get it working. When they ask you to set it up (or open this repo and say "set this up"), follow these steps in order, then tell them what you did.

What it does: the user runs `/reword <what to write>`. You create the content, send it to an LLM API (OpenAI, DeepSeek or Anthropic) for rewording, and deliver the result in chat or in a file (`.docx`, `.tex`, `.md`, `.txt`).

## 1. Install the files

From the repo root, run:

```bash
./install.sh
```

This copies the following into `~/.claude/`:
- `hooks/paraphrase_review.py` and `hooks/reword_prompt.txt`
- `commands/reword.md` and `commands/reword_paraphrased.md`
- `hooks/reword.env`, created from the empty template **only if the user does not already have one**. An existing file is never overwritten.

Requires `python3` (standard library only; nothing to install with pip). If `python3` is not available, tell the user to install it.

## 2. Have the user add their API key

**Do not open, read, print or edit `~/.claude/hooks/reword.env`.** Ask the user to complete this step themselves:

> Open `~/.claude/hooks/reword.env` and paste in at least one key:
> `OPENAI_API_KEY=sk-...`, `DEEPSEEK_API_KEY=...` or `ANTHROPIC_API_KEY=sk-ant-...`

Notes to share:
- Keys in this file take precedence over keys exported in the shell, so an outdated `OPENAI_API_KEY` in the environment cannot override it.
- If no key is set, the tool prints `no api my guy` and sends nothing anywhere.
- If they prefer not to edit the file, they can export the key in the shell that launches Claude Code. It is used only when the file contains no key.

Wait for the user to confirm that they've added the key before proceeding to step 3.

## 3. Check that it works

Run this short test. It prints a status line only, never the key:

```bash
printf 'Planes fly fast at high altitude.\n' > /tmp/reword_test.txt
python3 -I ~/.claude/hooks/paraphrase_review.py --reword /tmp/reword_test.txt /tmp/reword_test_out.txt
```

- `[reworded with <provider>] saved to ...` → working.
- `no api my guy` → no key was found; return to step 2.
- `... call failed: HTTP Error 401` → the key is invalid or for a different provider; ask the user to check it. Do not try to find the key yourself.

## 4. Tell the user how to use it

Have them restart Claude Code (or start a new session), then run:

```
/reword one paragraph on jets
/reword summary in report.docx
/reword intro section in paper.tex
```

- Reword mode remains enabled for the session; they can say "stop" to disable it.
- They can specify a provider or model in the request to override the default, for example `/reword ... with deepseek-reasoner`. The default is OpenAI `gpt-6-luna`; if their account uses different models, they can edit the `PROVIDERS` table at the top of `~/.claude/hooks/paraphrase_review.py`.
- They can edit the rewrite prompt in `~/.claude/hooks/reword_prompt.txt`.

## 5. Optional: auto-paraphrase hook

Do this only if the user asks. It causes every Write/Edit of a `.md`, `.tex`, `.txt` or `.rst` file to also generate a `<name>_paraphrased<ext>` copy and a diff. Add the following to `~/.claude/settings.json`, merging it with any existing `hooks` rather than replacing them, and show the user the change before applying it:

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

- **Safety checks:** if a rewrite alters numbers, URLs, LaTeX commands or math, it is rejected and the original is retained.
- **`.docx` input:** only paragraph text is replaced; styles, tables, images and layout remain intact. Text in tables is reworded, while headers, footers and footnotes are left unchanged. If a paragraph mixes formatting (for example, one bold word), the first run's style is used.
- **`.docx` output:** it is always saved as a new file. Ask before overwriting an existing file.
- When delivering content into a file, use `cp`/`cat` through Bash, not the Edit/Write tools, which would trigger the auto-hook and reword the content twice.

## Files

| File | Purpose |
|---|---|
| `hooks/paraphrase_review.py` | The tool (`--reword IN OUT` CLI mode, plus hook mode) |
| `hooks/reword_prompt.txt` | Editable rewrite prompt |
| `hooks/reword.env` | Empty key template, copied to `~/.claude/hooks/` by `install.sh` |
| `commands/reword.md` | The `/reword` command |
| `commands/reword_paraphrased.md` | Alternate-wording version of the same command |
| `install.sh` | Copies everything into `~/.claude/` |
