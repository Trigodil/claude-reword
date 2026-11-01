#!/usr/bin/env python3
"""PostToolUse hook: after Claude edits a prose file (.md, .tex, .txt, .rst),
send it to another LLM API to be reworded, save the result as
<name>_paraphrased<ext> next to the original, and show a diff.

The original file is never modified. Code files are never touched.

Config (environment variables, read from the shell that launches Claude Code):
  PARAPHRASE_PROVIDER   openai | deepseek | anthropic   (default: first one with a key)
  PARAPHRASE_MODEL      model name (defaults below)
  PARAPHRASE_BASE_URL   optional override of the API base URL
  OPENAI_API_KEY / DEEPSEEK_API_KEY / ANTHROPIC_API_KEY

With no key set, the hook does nothing and sends nothing anywhere.
"""
import difflib
import json
import os
import re
import sys
import urllib.request

EXTS = {".md", ".tex", ".txt", ".rst"}
MAX_CHARS = 60000
TIMEOUT = 50

PROVIDERS = {
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1", "gpt-6-luna"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1", "deepseek-chat"),
    "anthropic": ("ANTHROPIC_API_KEY", "https://api.anthropic.com", "claude-haiku-4-5"),
}

DEFAULT_PROMPT = (
    "You are an editor. Reword and paraphrase the document below so the wording is "
    "natural and fits its context, while keeping the exact meaning. Keep every fact, "
    "number, name and claim unchanged, keep the length similar to the original (at most "
    "10 to 15 percent longer or shorter), leave LaTeX commands, math, code and URLs "
    "untouched, and return only the full reworded document."
)


def load_prompt():
    """Editable prompt: ~/.claude/hooks/reword_prompt.txt, or the built-in default."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reword_prompt.txt")
    try:
        text = open(path, encoding="utf-8").read().strip()
        return text or DEFAULT_PROMPT
    except OSError:
        return DEFAULT_PROMPT


PROMPT = load_prompt()


def out(msg=None):
    print(json.dumps({"systemMessage": msg} if msg else {}))
    sys.exit(0)


def load_key_file():
    """Read API keys from ~/.claude/hooks/reword.env (KEY=value lines) when they
    are not already set in the environment. Keeps keys out of settings.json."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reword.env")
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if v and not os.environ.get(k):
                os.environ[k] = v
    except OSError:
        pass


def pick_provider():
    load_key_file()
    want = os.environ.get("PARAPHRASE_PROVIDER", "").lower()
    order = [want] if want in PROVIDERS else list(PROVIDERS)
    for name in order:
        if os.environ.get(PROVIDERS[name][0]):
            return name
    return None


def post(url, headers, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode(), headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def rewrite(text, name):
    key_env, base, default_model = PROVIDERS[name]
    key = os.environ[key_env]
    model = os.environ.get("PARAPHRASE_MODEL", default_model)
    base = os.environ.get("PARAPHRASE_BASE_URL", base).rstrip("/")
    if name == "anthropic":
        r = post(
            base + "/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01",
             "content-type": "application/json"},
            {"model": model, "max_tokens": 16000, "system": PROMPT,
             "messages": [{"role": "user", "content": text}]},
        )
        return "".join(b.get("text", "") for b in r["content"])
    r = post(
        base + "/chat/completions",
        {"Authorization": "Bearer " + key, "content-type": "application/json"},
        {"model": model,
         "messages": [{"role": "system", "content": PROMPT},
                      {"role": "user", "content": text}]},
    )
    return r["choices"][0]["message"]["content"]


def tex_tokens(s):
    """Commands and math that must survive a rewrite unchanged."""
    cmds = re.findall(r"\\[A-Za-z]+\*?(?:\{[^{}]*\})?", s)
    math = re.findall(r"\$[^$]+\$", s)
    return sorted(cmds + math)


def reword_cli(path, out_path=None):
    """/reword: reword the text in `path`; print it, or save it to `out_path`."""
    provider = pick_provider()
    if not provider:
        print("no api my guy")
        sys.exit(0)
    text = open(path, encoding="utf-8", errors="replace").read()
    if not text.strip():
        print("nothing to reword")
        sys.exit(0)
    if len(text) > MAX_CHARS:
        print("too long to reword (%d chars, max %d)" % (len(text), MAX_CHARS))
        sys.exit(0)
    try:
        new = rewrite(text, provider).strip("\n")
    except Exception as e:
        print("%s call failed: %s" % (provider, e))
        sys.exit(0)
    if tex_tokens(text) != tex_tokens(new):
        print("rewrite changed LaTeX commands or math, so it was discarded. "
              "Original left as is.")
        sys.exit(0)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(new + "\n")
        print("[reworded with %s] saved to %s" % (provider, out_path))
        return
    print("[reworded with %s]\n" % provider)
    print(new)


def main():
    if len(sys.argv) in (3, 4) and sys.argv[1] == "--reword":
        reword_cli(sys.argv[2], sys.argv[3] if len(sys.argv) == 4 else None)
        return
    try:
        data = json.load(sys.stdin)
        path = (data.get("tool_input") or {}).get("file_path") or \
               (data.get("tool_response") or {}).get("filePath")
    except Exception:
        out()
    if not path or not os.path.isfile(path):
        out()
    stem, ext = os.path.splitext(path)
    if ext.lower() not in EXTS or stem.endswith("_paraphrased"):
        out()
    provider = pick_provider()
    if not provider:
        out()
    text = open(path, encoding="utf-8", errors="replace").read()
    if not text.strip() or len(text) > MAX_CHARS:
        out()
    try:
        new = rewrite(text, provider).strip("\n") + "\n"
    except Exception as e:
        out("paraphrase hook: %s call failed (%s)" % (provider, e))
    if ext.lower() == ".tex" and tex_tokens(text) != tex_tokens(new):
        out("paraphrase hook: rewrite changed LaTeX commands or math, discarded "
            "(%s)" % os.path.basename(path))
    target = stem + "_paraphrased" + ext
    open(target, "w", encoding="utf-8").write(new)
    diff = list(difflib.unified_diff(
        text.splitlines(), new.splitlines(),
        os.path.basename(path), os.path.basename(target), lineterm="", n=0))
    shown = "\n".join(diff[:60]) + ("\n... (diff truncated)" if len(diff) > 60 else "")
    out("Paraphrased with %s -> %s\n%s" % (provider, target, shown))


main()
