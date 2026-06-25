#!/bin/bash
# Install the Claude Code override indicator for Ubuntu/GNOME.
# Run once. Adds the tray icon and sets it to auto-start on login.

set -e

DEST="$HOME/.local/share/claude-override"
AUTOSTART="$HOME/.config/autostart"

echo "Installing dependency..."
sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1

echo "Copying files..."
mkdir -p "$DEST"
cp "$(dirname "$0")/claude-override-indicator.py" "$DEST/"
cp "$(dirname "$0")/claude-override.svg"        "$DEST/"
cp "$(dirname "$0")/claude-override-green.svg"  "$DEST/"
cp "$(dirname "$0")/claude-override-orange.svg" "$DEST/"
cp "$(dirname "$0")/claude-override-red.svg"    "$DEST/"
chmod +x "$DEST/claude-override-indicator.py"

echo "Setting up autostart..."
mkdir -p "$AUTOSTART"
cat > "$AUTOSTART/claude-override-indicator.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Claude Override Indicator
Exec=$DEST/claude-override-indicator.py
StartupNotify=false
X-GNOME-Autostart-enabled=true
EOF

echo ""
echo "Done. Starting now..."
nohup "$DEST/claude-override-indicator.py" &>/dev/null &
echo "The tray icon is running. It will be invisible until you hit the usage limit."
echo "It will also start automatically on every login."
