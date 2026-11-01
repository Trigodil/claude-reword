#!/usr/bin/env bash
# Installs the reword hook + slash commands into ~/.claude. Does not touch settings.json
# or overwrite an existing reword.env.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
dest="$HOME/.claude"
mkdir -p "$dest/hooks" "$dest/commands"
cp "$here/hooks/paraphrase_review.py" "$here/hooks/reword_prompt.txt" "$dest/hooks/"
cp "$here/commands/"*.md "$dest/commands/"
if [ ! -f "$dest/hooks/reword.env" ]; then
  cp "$here/hooks/reword.env.example" "$dest/hooks/reword.env"
  chmod 600 "$dest/hooks/reword.env"
  echo "Created $dest/hooks/reword.env from the template. Edit it and add your API key."
else
  echo "Kept your existing $dest/hooks/reword.env"
fi
echo "Installed. Optional auto-hook: see CLAUDE.md step 4."
