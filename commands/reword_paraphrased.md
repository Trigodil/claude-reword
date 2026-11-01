---
description: Create content, run it through the reword API, and deliver the reworded version (in a code block in chat or directly in a file)
argument-hint: <what to write, e.g. "an essay on fighter jets" or "intro section in paper.tex">
---

Task from the user: $ARGUMENTS

**Strict secrecy rule:** API keys are strictly off limits. Never read, open, cat, grep, print, echo, quote, summarize, or log `~/.claude/settings.json`, `~/.claude/hooks/reword.env`, any file or environment variable containing an API key (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`), or any command output containing one. Never run `env`, `printenv`, `set` or `jq` on those files. The script locates the key itself; run only the command in step 3 and read its stdout. If the script reports `no api my guy`, say so and stop. Do not search for the key to troubleshoot. If a key appears in anything shown to you, do not repeat it; tell the user once that it was exposed and should be rotated.

Create the content, submit it to the user's reword API, and deliver the API's version. Follow these steps exactly:

1. **Write the content** requested by the task. If the task specifies a file (for example `paper.tex`, `notes.md`), make sure the content fits that file type; for `.tex`, it must be valid LaTeX for that location. Do not show the draft to the user.
2. **Save the draft** as a new file in the scratchpad directory, such as `<scratchpad>/reword_in.txt`.
3. **Select a provider and reword the draft.** Choose the provider each time you write the Bash command, based on what the user requested:
   - If the request specifies a provider (`openai`, `deepseek` or `anthropic`), use that provider. If the user names a model too (for example "with deepseek-reasoner"), use that model.
   - If no provider is named, default to `openai` with model `gpt-6-luna` (the user may refer to it as "Luna-6" or "Luna"; the API ID is `gpt-6-luna`).
   - Model IDs must match exactly. Known IDs: OpenAI `gpt-6-luna`, `gpt-6-sol`, `gpt-5`, `gpt-5-mini`, `gpt-4.1`, `gpt-4o`; DeepSeek `deepseek-chat`, `deepseek-reasoner`; Anthropic `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`. If the user specifies a model not on this list, use their string as given.
   - Set the variables before the command, and quote nothing else: `PARAPHRASE_PROVIDER=<provider> PARAPHRASE_MODEL=<model> python3 -I ~/.claude/hooks/paraphrase_review.py --reword <scratchpad>/reword_in.txt <scratchpad>/reword_out.txt`. Use `gpt-6-luna` as the model only for `openai`. For `deepseek` and `anthropic`, omit `PARAPHRASE_MODEL` unless the user named a model, allowing the script to use that provider's default.
   - Continue using the same provider for the rest of the session while reword mode is on, unless the user specifies another provider; if they do, switch to it from then on.
   - Read the command's stdout.
4. **If stdout is exactly `no api my guy`**, respond with exactly `no api my guy` and nothing more. Do not write any file. If stdout contains any other failure message (the call failed, or the rewrite changed LaTeX commands or math and was discarded), pass it along unchanged and write nothing.
5. **Deliver the reworded text** (from `reword_out.txt`), not your own draft, and do not edit the reworded text:
   - **If no file is named in the task:** read `reword_out.txt` and show its contents to the user in a single fenced code block. Use a `latex` fence for LaTeX content; otherwise, use `text`.
   - **If a file is named in the task:** write the reworded text into that file exactly as it appears, using a Bash command (`cp` for a new file, or `cat` appended or inserted into an existing file). Do not use the Edit or Write tool, since they trigger the separate paraphrase hook and would reword the text a second time. If the target file already exists and the task does not clearly ask you to replace it, ask before overwriting.
6. **Report briefly:** state that the text was reworded through the API, identify the file it went into (if any), and say nothing else.

## Stays on for the rest of the session

Once this command has been run, reword mode remains **on** for the rest of the session. Continue following steps 1–6 for every later request to write essay prose or LaTeX text or math, whether for chat or a file such as `.tex`, `.md` or `.txt`. The user does not need to run `/reword` again. Rules while the mode is active:

- It applies only to prose and LaTeX. Ordinary code (Python, C, shell and so on), commands, and normal conversational replies are not reworded.
- Whenever it applies, run the full process again: write the draft, save it, submit it through the script, and deliver the API's version rather than your own.
- If the script says `no api my guy`, respond with exactly that for the request and leave the mode on.
- Turn the mode **off** when the user asks you to stop, or says something similar, such as "stop rewording", "reword off", "turn it off", "no more reword" or "go back to normal". Confirm in one short line, then answer normally from that point on.
- If `/reword` is run without task text while the mode is already on, simply confirm that it is on.
- At the beginning of a new session, the mode is off until `/reword` is run again.
