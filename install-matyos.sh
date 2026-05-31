#!/usr/bin/env bash
# Install the `matyos` command on Linux/macOS.
#
# Place the downloaded `matyos` binary next to this script (or build dist/matyos),
# then run:  bash install-matyos.sh
#
# Installs to ~/.local/bin (make sure it is on your PATH).
set -e

DEST="${HOME}/.local/bin"
SRC=""
for c in "$(dirname "$0")/matyos" "$(dirname "$0")/dist/matyos"; do
  if [ -f "$c" ]; then SRC="$c"; break; fi
done
if [ -z "$SRC" ]; then
  echo "matyos binary not found next to this script or in dist/. Download it from the Releases page first." >&2
  exit 1
fi

mkdir -p "$DEST"
cp "$SRC" "$DEST/matyos"
chmod +x "$DEST/matyos"
echo "Installed matyos to $DEST/matyos"
case ":$PATH:" in
  *":$DEST:"*) echo "Run:  matyos version" ;;
  *) echo "Add to your shell profile:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac
