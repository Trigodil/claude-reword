# reword-tool

A Claude Code slash command (`/reword`) plus a Python script that sends prose or LaTeX
through an LLM API (OpenAI, DeepSeek or Anthropic) to be reworded, then delivers that
version instead of Claude's own draft. LaTeX commands and math are checked and the
rewrite is discarded if they change.

## Rules for Claude working in this repo

- **Never read, print, commit or push any real API key or `reword.env`.** Only
  `hooks/reword.env` (empty template) belongs in git. `.gitignore` blocks `*.env`.
- Before any commit, confirm `git status` shows no `.env` file staged.

## Setup (tell the user to do these steps, or do them for them)

1. **Install the files** from the repo root:
   ```bash
   ./install.sh
   ```
   This copies into `~/.claude/`:
   - `hooks/paraphrase_review.py`, `hooks/reword_prompt.txt`
   - `commands/reword.md`, `commands/reword_paraphrased.md`
   - `hooks/reword.env` created from `hooks/reword.env` (only if missing; an existing one is never overwritten)

2. **Add an API key.** The user edits `~/.claude/hooks/reword.env` themselves
   (Claude must not open it) and fills in at least one of `OPENAI_API_KEY`,
   `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`. Keys can alternatively be exported in the shell
   that launches Claude Code. With no key set the script prints `no api my guy` and
   sends nothing anywhere.

3. **Use it.** Restart Claude Code, then run `/reword <what to write>`, for example
   `/reword one paragraph on jets` or `/reword intro section in paper.tex`.
   Reword mode then stays on for the session; say "stop" to turn it off.
   Pick a provider/model by naming it in the request ("with deepseek-reasoner").
   Default is OpenAI `gpt-6-luna`; change the default table at the top of
   `paraphrase_review.py` (`PROVIDERS`) if your account uses other models.

4. **(Optional) auto-paraphrase hook.** To have every Write/Edit of a `.md/.tex/.txt/.rst`
   file produce a `<name>_paraphrased<ext>` copy plus a diff, add this to
   `~/.claude/settings.json`. Note this makes `/reword` file delivery use `cp`/`cat` so
   the hook does not reword twice (the command already does this):
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

## Files

| File | Purpose |
|---|---|
| `hooks/paraphrase_review.py` | The tool. `--reword in out` CLI mode, plus the PostToolUse hook mode |
| `hooks/reword_prompt.txt` | Editable system prompt for the rewrite |
| `hooks/reword.env` | Empty key template, copied to `~/.claude/hooks/reword.env` by install.sh. Keep it empty in git |
| `commands/reword.md` | The `/reword` slash command |
| `commands/reword_paraphrased.md` | Variant of the same command with alternate wording |
| `install.sh` | Copies everything into `~/.claude/` |

## Testing

```bash
printf 'Jets push air backward to move forward.\n' > /tmp/in.txt
python3 -I ~/.claude/hooks/paraphrase_review.py --reword /tmp/in.txt /tmp/out.txt
```
Expect `[reworded with <provider>] saved to /tmp/out.txt`, or `no api my guy` if no key is set.
