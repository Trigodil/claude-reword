---
description: Write something, run it through the reword API, and deliver the reworded version (code block in chat, or straight into a file)
argument-hint: <what to write, e.g. "an essay on fighter jets" or "intro section in paper.tex" or "summary in report.docx">
---

Task from the user: $ARGUMENTS

**Strict secrecy rule:** API keys are off limits. Never read, open, cat, grep, print, echo, quote, summarize, or log `~/.claude/settings.json`, `~/.claude/hooks/reword.env`, any file or environment variable that holds an API key (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `ANTHROPIC_API_KEY`), or any command output that contains one. Never run `env`, `printenv`, `set` or `jq` on those files. The script finds the key by itself; you only run the command in step 3 and read its stdout. If the script reports `no api my guy`, say that and stop. Do not go looking for the key to debug it. If a key ever shows up in anything you are shown, do not repeat it, and tell the user once that it was exposed and should be rotated.

Produce the content, send it through the user's reword API, and deliver the API's version. Do exactly this:

1. **Write the content** the task asks for. If the task names a file (for example `paper.tex`, `report.docx`, `notes.md`), the content must suit that file type, and for `.tex` it must be valid LaTeX for that spot. For `.docx`, write plain text: blank lines separate paragraphs and a line starting with `# ` is a heading. If the task is to reword an existing `.docx`, skip the draft and use that file as the input in step 3. Do not show this draft to the user.
2. **Save the draft** to a new file in the scratchpad directory, for example `<scratchpad>/reword_in.txt`.
3. **Choose the provider and reword it.** You pick the provider each time you write the Bash command, from what the user said:
   - If the user names a provider (`openai`, `deepseek` or `anthropic`) in the request, use it. A user who names a model alongside it (for example "with deepseek-reasoner") gets that model.
   - If the user names none, the default is `openai` with model `gpt-6-luna` (the user may call it "Luna-6" or "Luna"; the API ID is `gpt-6-luna`).
   - Model IDs must be exact. Known ones: OpenAI `gpt-6-luna`, `gpt-6-sol`, `gpt-5`, `gpt-5-mini`, `gpt-4.1`, `gpt-4o`; DeepSeek `deepseek-chat`, `deepseek-reasoner`; Anthropic `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`. If the user names a model not in this list, pass their string as given.
   - Set them as environment variables in front of the command, and quote nothing else: `PARAPHRASE_PROVIDER=<provider> PARAPHRASE_MODEL=<model> python3 -I ~/.claude/hooks/paraphrase_review.py --reword <scratchpad>/reword_in.txt <scratchpad>/reword_out.txt`. When the target is a `.docx` file (new or existing), use `<scratchpad>/reword_out.docx` as the output path instead; the tool builds or rewrites the Word file itself. Use `gpt-6-luna` as the model only for `openai`. For `deepseek` and `anthropic`, leave out `PARAPHRASE_MODEL` unless the user named one, so the script uses that provider's own default.
   - Use the same provider for the rest of the session while reword mode is on, unless the user names a different one, and then switch to it from then on.
   - Read the command's stdout.
4. **If stdout is exactly `no api my guy`**, reply with exactly `no api my guy` and nothing else. Do not write any file. If stdout is any other failure message (the call failed, or the rewrite changed LaTeX commands, math, numbers or URLs, or lost paragraphs, and was discarded), relay it as is and write nothing.
5. **Deliver the reworded text** (the content of `reword_out.txt`), never your own draft, and never edit the reworded text yourself:
   - **No file named in the task:** read `reword_out.txt` and show its content to the user inside one fenced code block. Use a `latex` fence if the content is LaTeX, otherwise `text`.
   - **A file named in the task:** put the reworded text into that file exactly as it is, using a Bash command (for a `.docx` target `cp` `reword_out.docx` to it, never Edit or Write; `cp` for a new file, or `cat` appended or inserted for an existing one). Do not use the Edit or Write tool, because those trigger the separate paraphrase hook and would reword it a second time. If the target file already exists and the task is not clearly to replace it, ask before overwriting.
6. **Report briefly:** say that the text was reworded through the API, which file it went into (if any), and nothing else.

## Stays on for the rest of the session

After this command, reword mode stays **on** for the rest of the session. Keep following steps 1 to 6 for every later request in which the user asks you to write essay prose, or LaTeX text or math, whether it is for the chat or for a file such as a `.tex`, `.md` or `.txt`. The user does not need to type `/reword` again. Rules for the mode:

- It covers prose, LaTeX and Word (.docx) documents only. Ordinary code (Python, C, shell and so on), commands, and your normal conversational replies are not reworded.
- Each time it applies, run the full pipeline again: write the draft, save it, send it through the script, and deliver the API's version, not your own.
- If the script says `no api my guy`, reply with exactly that for that request, and keep the mode on.
- Turn it **off** when the user says stop, or anything similar, such as "stop rewording", "reword off", "turn it off", "no more reword" or "go back to normal". Confirm with one short line, and from then on answer normally.
- If `/reword` is run with no task text while the mode is already on, just confirm it is on.
- When the user starts a new session, the mode is off until `/reword` is run again.
