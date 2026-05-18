#!/usr/bin/env bash
#
# Lumex8 — single-command installer
#
#   chmod +x install.sh
#   ./install.sh               # guided (asks about gamepad)
#   sudo ./install.sh           # auto-installs everything
#
set -e

BOLD="\033[1m"; GREEN="\033[0;32m"; YELLOW="\033[0;33m"
CYAN="\033[0;36m";   RED="\033[0;31m";   NC="\033[0m"

echo -e "${CYAN}${BOLD}  Lumex8 Installer${NC}
"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

[ -f "lumex8/__main__.py" ] || { echo -e "${RED}Error: lumex8/ not found${NC}"; exit 1; }

# ---- uv ----
install_uv() {
    echo -e "  ${YELLOW}→${NC} Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
    [ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env"
    echo -e "  ${GREEN}✓${NC} uv installed"
}

command -v uv &>/dev/null || install_uv

echo -e "  ${GREEN}✓${NC} uv $(uv --version 2>/dev/null | head -1)"

# ---- System deps (Qt needs X11 cursor) ----
if ! dpkg -s libxcb-cursor0 &>/dev/null 2>&1; then
    echo -e "  ${YELLOW}→${NC} Installing libxcb-cursor0..."
    sudo apt-get update -qq 2>/dev/null || true
    sudo apt-get install -y -qq libxcb-cursor0
fi
echo -e "  ${GREEN}✓${NC} libxcb-cursor0"

# ---- Gamepad (optional) ----
GAMEPAD_PKGS=""
if [ "$(id -u)" -eq 0 ]; then
    # Root: auto-include
    GAMEPAD_PKGS="libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0"
    echo -e "  ${CYAN}→${NC} Running as root — including SDL2 + pygame for gamepad"
else
    read -p "  Install gamepad support (SDL2 + pygame)? [y/N] " -r answer
    case "$answer" in
        [yY]*) GAMEPAD_PKGS="libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0" ;;
        *)     echo -e "  ${CYAN}→${NC} Skipping gamepad" ;;
    esac
fi

if [ -n "$GAMEPAD_PKGS" ]; then
    for pkg in $GAMEPAD_PKGS; do
        dpkg -s "$pkg" &>/dev/null 2>&1 && echo -e "  ${GREEN}✓${NC} $pkg" || \
            { sudo apt-get install -y -qq "$pkg" 2>/dev/null; \
              echo -e "  ${GREEN}✓${NC} $pkg (installed)"; }
    done
    # Install pygame into uv's environment
    uv pip install --system pygame 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} pygame (gamepad ready)"
fi

# ---- Launch script ----
LAUNCHER="$PROJECT_ROOT/launch.sh"
cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
cd "$PROJECT_ROOT"
uv run "$PROJECT_ROOT/lumex8/__main__.py"
EOF
chmod +x "$LAUNCHER"
echo -e "  ${GREEN}✓${NC} launch.sh"

# ---- Desktop entry ----
DESKTOP="$PROJECT_ROOT/lumex8.desktop"
cat > "$DESKTOP" << EOF
[Desktop Entry]
Name=Lumex8
Comment=Windows 8 style tile launcher
Exec=$LAUNCHER
Icon=$SCRIPT_DIR/icons/cmd_unpin.svg
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
EOF
chmod +x "$DESKTOP"
echo -e "  ${GREEN}✓${NC} lumex8.desktop"

# ---- Ownership fix (if root) ----
if [ "$(id -u)" -eq 0 ] && [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    chown -R "$SUDO_USER:$SUDO_USER" "$PROJECT_ROOT" 2>/dev/null || true
fi

echo ""
echo -e "${GREEN}${BOLD}Done.${NC}"
echo -e "  ${CYAN}./launch.sh${NC}                    # Double-click or terminal"
echo -e "  ${CYAN}cp lumex8.desktop ~/.local/share/applications/${NC}"
echo ""
