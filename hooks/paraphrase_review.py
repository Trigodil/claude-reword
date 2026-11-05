#!/usr/bin/env python3
"""Reword tool for Claude Code (prose, LaTeX and Word .docx).

CLI (used by the /reword command):
  paraphrase_review.py --reword IN OUT
    IN  = .txt/.md text file  -> OUT may be text, or .docx (a new Word file is built)
    IN  = .docx               -> OUT must be .docx (paragraph text is reworded in place,
                                 styles/tables/images/layout are kept)

Hook mode (PostToolUse): after Claude edits a prose file (.md, .tex, .txt, .rst),
send it to another LLM API to be reworded, save the result as
<name>_paraphrased<ext> next to the original, and show a diff.

The original file is never modified. Code files are never touched.

Config (keys come from hooks/reword.env first, then the shell environment):
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
import zipfile
from xml.sax.saxutils import escape, unescape

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
    "untouched, keep any <<N>> paragraph markers exactly as they are, and return only "
    "the full reworded document."
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
    """Read API keys from ~/.claude/hooks/reword.env (KEY=value lines). Non-empty
    values in this file take priority over keys already in the shell environment,
    so a stale exported key can't shadow it. Keeps keys out of settings.json."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reword.env")
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip("'\"")
            if v:
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


def rewrite(text, name, note=""):
    key_env, base, default_model = PROVIDERS[name]
    prompt = PROMPT + note
    key = os.environ[key_env]
    model = os.environ.get("PARAPHRASE_MODEL", default_model)
    base = os.environ.get("PARAPHRASE_BASE_URL", base).rstrip("/")
    if name == "anthropic":
        r = post(
            base + "/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01",
             "content-type": "application/json"},
            {"model": model, "max_tokens": 16000, "system": prompt,
             "messages": [{"role": "user", "content": text}]},
        )
        return "".join(b.get("text", "") for b in r["content"])
    r = post(
        base + "/chat/completions",
        {"Authorization": "Bearer " + key, "content-type": "application/json"},
        {"model": model,
         "messages": [{"role": "system", "content": prompt},
                      {"role": "user", "content": text}]},
    )
    return r["choices"][0]["message"]["content"]


MASK_NOTE = (
    " Tokens like ⟦12⟧ stand for math or markup: keep every one exactly as written, "
    "in the same order, and reword only the prose around them."
)
MASK_RE = re.compile(r"⟦(\d+)⟧")
CMD_RE = re.compile(r"\\([A-Za-z]+\*?|.)", re.S)
VERBATIM_ENVS = {
    "equation", "align", "gather", "multline", "eqnarray", "displaymath", "math",
    "alignat", "flalign", "verbatim", "lstlisting", "tabular", "array", "tikzpicture",
}
RAW_ARG_CMDS = {
    "begin", "end", "label", "ref", "eqref", "cite", "pageref", "url", "href",
    "usepackage", "documentclass", "newcommand", "renewcommand", "newtheorem",
    "newenvironment", "theoremstyle", "input", "include", "includegraphics",
    "bibliography", "bibliographystyle", "setlength", "DeclareMathOperator",
}


def skip_group(s, i, open_ch, close_ch):
    """Index just past the balanced group starting at s[i] == open_ch."""
    depth = 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        depth += (s[i] == open_ch) - (s[i] == close_ch)
        i += 1
        if depth == 0:
            return i
    return len(s)


def mask_markup(s):
    """Swap math, commands, braces and comments for ⟦n⟧ so only prose is sent."""
    kept, out, i, n = [], [], 0, len(s)

    def hold(chunk):
        kept.append(chunk)
        out.append("⟦%d⟧" % (len(kept) - 1))

    start = re.search(r"\\begin\{document\}", s)
    if start:
        hold(s[:start.end()])
        i = start.end()
    while i < n:
        c = s[i]
        if s.startswith("```", i):
            j = s.find("```", i + 3)
            j = n if j < 0 else j + 3
        elif c == "%":
            j = s.find("\n", i)
            j = n if j < 0 else j
        elif s.startswith("$$", i):
            j = s.find("$$", i + 2)
            j = n if j < 0 else j + 2
        elif c == "$":
            j = i + 1
            while j < n and not (s[j] == "$" and s[j - 1] != "\\"):
                j += 1
            j = min(j + 1, n)
        elif s.startswith("\\[", i) or s.startswith("\\(", i):
            j = s.find("\\]" if s[i + 1] == "[" else "\\)", i + 2)
            j = n if j < 0 else j + 2
        elif c == "\\":
            name = CMD_RE.match(s, i).group(1)
            j = i + 1 + len(name)
            env = re.match(r"\{([A-Za-z]+\*?)\}", s[j:])
            if name == "begin" and env and env.group(1).rstrip("*") in VERBATIM_ENVS:
                end = s.find("\\end{%s}" % env.group(1), j)
                j = n if end < 0 else end + len("\\end{%s}" % env.group(1))
            elif name in RAW_ARG_CMDS:
                while j < n and s[j] in "[{":
                    j = skip_group(s, j, s[j], "]" if s[j] == "[" else "}")
            else:
                while j < n and s[j] == "[":
                    j = skip_group(s, j, "[", "]")
                if j < n and s[j] == "{":
                    j += 1
        elif c in "{}":
            j = i + 1
        else:
            out.append(c)
            i += 1
            continue
        hold(s[i:j])
        i = j
    return "".join(out), kept


def compact_markup(masked, kept):
    """Merge tokens separated only by spaces or punctuation into one token."""
    merged = []

    def join(m):
        merged.append(MASK_RE.sub(lambda t: kept[int(t.group(1))], m.group(0)))
        return "⟦%d⟧" % (len(merged) - 1)

    return re.sub(r"⟦\d+⟧(?:[\s,.;:()\[\]]*⟦\d+⟧)*", join, masked), merged


def rewrite_prose(text, name):
    """Reword only the prose of `text`, paragraph by paragraph.

    Returns (new_text, kept_count): paragraphs whose tokens or numbers changed keep
    their original wording, and kept_count says how many did."""
    masked, kept = compact_markup(*mask_markup(text))
    paras = re.split(r"(\n\s*\n)", masked)
    prose = [i for i in range(0, len(paras), 2)
             if re.search(r"[A-Za-z]{2}", MASK_RE.sub("", paras[i]))]
    if not prose:
        return text, 0
    payload = "\n\n".join("<<%d>> %s" % (i, paras[i]) for i in prose)
    reply = rewrite(payload, name, MASK_NOTE if kept else "")
    parts = re.split(r"<<(\d+)>>", reply)
    got = {int(parts[k]): parts[k + 1].strip() for k in range(1, len(parts) - 1, 2)}
    fallback = 0
    for i in prose:
        new = got.get(i)
        if (new is None or MASK_RE.findall(new) != MASK_RE.findall(paras[i])
                or guard_tokens(new) != guard_tokens(paras[i])):
            fallback += 1
            continue
        lead = paras[i][:len(paras[i]) - len(paras[i].lstrip())]
        paras[i] = lead + new + paras[i][len(paras[i].rstrip()):]
    return MASK_RE.sub(lambda m: kept[int(m.group(1))], "".join(paras)), fallback


def tex_tokens(s):
    """LaTeX commands and math that must survive a rewrite unchanged."""
    cmds = re.findall(r"\\[A-Za-z]+\*?(?:\{[^{}]*\})?", s)
    math = re.findall(r"\$[^$]+\$", s)
    return sorted(cmds + math)


def guard_tokens(s):
    """Numbers and URLs that must survive a rewrite unchanged."""
    s = re.sub(r"<<\d+>>", "", s)
    return sorted(re.findall(r"https?://\S+|\d[\d,.]*\d|\d", s))


# ---------------------------------------------------------------- .docx helpers
P_RE = re.compile(r"<w:p[ >].*?</w:p>", re.S)
T_RE = re.compile(r"(<w:t(?: [^>]*)?>)(.*?)(</w:t>)", re.S)


def para_text(p_xml):
    return unescape("".join(m.group(2) for m in T_RE.finditer(p_xml)))


def set_para_text(p_xml, text):
    """Put `text` in the first run's <w:t>, empty the others. Run/paragraph
    properties (fonts, styles, alignment) are left exactly as they were."""
    n = [0]

    def sub(m):
        n[0] += 1
        if n[0] > 1:
            return m.group(1) + m.group(3)
        tag = m.group(1)
        if "xml:space" not in tag:
            tag = tag[:-1] + ' xml:space="preserve">'
        return tag + escape(text) + m.group(3)

    return T_RE.sub(sub, p_xml)


def reword_docx(src, dst, provider):
    with zipfile.ZipFile(src) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        infos = z.infolist()
        blobs = {i.filename: z.read(i.filename) for i in infos}
    spans = [m for m in P_RE.finditer(xml) if para_text(m.group(0)).strip()]
    if not spans:
        print("no text found in the .docx")
        sys.exit(0)
    texts = [para_text(m.group(0)) for m in spans]
    payload = "\n\n".join("<<%d>> %s" % (i, t) for i, t in enumerate(texts))
    if len(payload) > MAX_CHARS:
        print("too long to reword (%d chars, max %d)" % (len(payload), MAX_CHARS))
        sys.exit(0)
    try:
        reply = rewrite(payload, provider)
    except Exception as e:
        print("%s call failed: %s" % (provider, e))
        sys.exit(0)
    parts = re.split(r"<<(\d+)>>", reply)
    got = {}
    for k in range(1, len(parts) - 1, 2):
        got[int(parts[k])] = parts[k + 1].strip()
    if sorted(got) != list(range(len(texts))):
        print("rewrite lost or merged paragraphs, so it was discarded. Original left as is.")
        sys.exit(0)
    if guard_tokens("\n".join(texts)) != guard_tokens("\n".join(got[i] for i in range(len(texts)))):
        print("rewrite changed numbers or URLs, so it was discarded. Original left as is.")
        sys.exit(0)
    out_xml, last = [], 0
    for i, m in enumerate(spans):
        out_xml.append(xml[last:m.start()])
        out_xml.append(set_para_text(m.group(0), got[i]))
        last = m.end()
    out_xml.append(xml[last:])
    blobs["word/document.xml"] = "".join(out_xml).encode("utf-8")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        for i in infos:
            z.writestr(i.filename, blobs[i.filename])
    print("[reworded with %s] saved to %s" % (provider, dst))


NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def build_docx(text, dst):
    """Make a plain .docx from text. Blank lines separate paragraphs; a line
    starting with '# ' becomes a bold heading."""
    paras = []
    for block in re.split(r"\n\s*\n", text.strip()):
        block = block.strip("\n")
        bold = block.startswith("# ")
        if bold:
            block = block[2:]
        runs = '<w:br/>'.join(
            '<w:t xml:space="preserve">%s</w:t>' % escape(line) for line in block.split("\n"))
        rpr = "<w:rPr><w:b/><w:sz w:val=\"32\"/></w:rPr>" if bold else ""
        paras.append("<w:p><w:r>%s%s</w:r></w:p>" % (rpr, runs))
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document %s><w:body>%s</w:body></w:document>' % (NS, "".join(paras)))
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
             '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)


def reword_cli(path, out_path=None):
    """/reword: reword the file `path`; print the text, or save it to `out_path`."""
    provider = pick_provider()
    if not provider:
        print("no api my guy")
        sys.exit(0)
    src_docx = path.lower().endswith(".docx")
    out_docx = bool(out_path) and out_path.lower().endswith(".docx")
    if src_docx:
        if not out_docx:
            print("a .docx input needs a .docx output path")
            sys.exit(0)
        reword_docx(path, out_path, provider)
        return
    text = open(path, encoding="utf-8", errors="replace").read()
    if not text.strip():
        print("nothing to reword")
        sys.exit(0)
    if len(text) > MAX_CHARS:
        print("too long to reword (%d chars, max %d)" % (len(text), MAX_CHARS))
        sys.exit(0)
    try:
        new, fallback = rewrite_prose(text, provider)
    except Exception as e:
        print("%s call failed: %s" % (provider, e))
        sys.exit(0)
    new = new.strip("\n")
    if fallback:
        print("%d paragraph(s) kept their original wording (markup or numbers changed)."
              % fallback)
    if tex_tokens(text) != tex_tokens(new):
        print("rewrite changed LaTeX commands or math, so it was discarded. "
              "Original left as is.")
        sys.exit(0)
    if guard_tokens(text) != guard_tokens(new):
        print("rewrite changed numbers or URLs, so it was discarded. "
              "Original left as is.")
        sys.exit(0)
    if out_docx:
        build_docx(new, out_path)
        print("[reworded with %s] saved to %s" % (provider, out_path))
        return
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
        new = rewrite_prose(text, provider)[0]
    except Exception as e:
        out("paraphrase hook: %s call failed (%s)" % (provider, e))
    new = new.strip("\n") + "\n"
    if tex_tokens(text) != tex_tokens(new):
        out("paraphrase hook: rewrite changed LaTeX commands or math, discarded "
            "(%s)" % os.path.basename(path))
    if guard_tokens(text) != guard_tokens(new):
        out("paraphrase hook: rewrite changed numbers or URLs, discarded (%s)" % os.path.basename(path))
    target = stem + "_paraphrased" + ext
    open(target, "w", encoding="utf-8").write(new)
    diff = list(difflib.unified_diff(
        text.splitlines(), new.splitlines(),
        os.path.basename(path), os.path.basename(target), lineterm="", n=0))
    shown = "\n".join(diff[:60]) + ("\n... (diff truncated)" if len(diff) > 60 else "")
    out("Paraphrased with %s -> %s\n%s" % (provider, target, shown))


if __name__ == "__main__":
    main()
