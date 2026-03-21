#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# El Language Installer — Mac & Linux
# Usage: bash install.sh [--system]
#   --system   installs to /usr/local/bin (requires sudo)
# ─────────────────────────────────────────────────────────────────────────────
set -e

EL_VERSION="1.0.9"
INSTALL_DIR="$HOME/.el"
BIN_DIR="$HOME/.local/bin"

# Optional: system-wide install
if [[ "$1" == "--system" ]]; then
  BIN_DIR="/usr/local/bin"
fi

# ── Check Python ─────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "❌ Python 3 is required but not found."
  echo "   Install it from https://python.org or via your package manager."
  exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1-2)
echo "✔ Python $PYTHON_VERSION found"

# ── Copy source ───────────────────────────────────────────────────────────────
echo "📦 Installing El $EL_VERSION to $INSTALL_DIR ..."
rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_DIR"
cp -r "$(dirname "$0")/." "$INSTALL_DIR/"

# ── Create launcher ───────────────────────────────────────────────────────────
mkdir -p "$BIN_DIR"
cat > "$BIN_DIR/el" << LAUNCHER
#!/usr/bin/env bash
exec python3 "$INSTALL_DIR/el_cli.py" "\$@"
LAUNCHER
chmod +x "$BIN_DIR/el"

# ── PATH hint ─────────────────────────────────────────────────────────────────
if ! echo "$PATH" | grep -q "$BIN_DIR"; then
  echo ""
  echo "⚠️  Add $BIN_DIR to your PATH by adding this line to ~/.bashrc or ~/.zshrc:"
  echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "✅ El $EL_VERSION installed successfully!"
echo "   Run:  el run <file>.el"
echo "   Help: el --help"
