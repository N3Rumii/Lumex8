#!/usr/bin/env bash
#
# Lumex8 — single-command installer (Debian / Fedora / openSUSE)
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

# Work out the real user (even under sudo) so uv installs to the right home
if [ "$(id -u)" -eq 0 ] && [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    REAL_USER="$SUDO_USER"
    REAL_HOME=$(eval echo "~$SUDO_USER")
else
    REAL_USER="$(whoami)"
    REAL_HOME="$HOME"
fi
export PATH="$REAL_HOME/.cargo/bin:$PATH"

# ---------------------------------------------------------------------------
# Distro detection and package-manager abstraction
# ---------------------------------------------------------------------------
detect_distro() {
    if grep -qi -E "debian|ubuntu|mint|kali" /etc/os-release 2>/dev/null; then
        echo "debian"
    elif grep -qi -E "fedora|rhel|centos|rocky|alma" /etc/os-release 2>/dev/null; then
        echo "fedora"
    elif grep -qi -E "suse|opensuse" /etc/os-release 2>/dev/null; then
        echo "suse"
    else
        echo "unknown"
    fi
}

DISTRO=$(detect_distro)

case "$DISTRO" in
    debian)
        PKG_CHECK="dpkg -s"
        PKG_INSTALL="sudo apt-get install -y -qq"
        PKG_UPDATE="sudo apt-get update -qq 2>/dev/null || true"
        pkg_xcb="libxcb-cursor0"
        pkg_headers="linux-headers-$(uname -r)"
        pkg_build="build-essential"
        pkg_gamepad_base="libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0"
        ;;
    fedora)
        PKG_CHECK="rpm -q"
        PKG_INSTALL="sudo dnf install -y"
        PKG_UPDATE="true"   # dnf auto-refreshes
        pkg_xcb="xcb-util-cursor"
        pkg_headers="kernel-headers"
        pkg_build="gcc python3-devel make"
        pkg_gamepad_base="SDL2 SDL2_image SDL2_mixer SDL2_ttf"
        ;;
    suse)
        PKG_CHECK="rpm -q"
        PKG_INSTALL="sudo zypper install -y"
        PKG_UPDATE="sudo zypper refresh 2>/dev/null || true"
        pkg_xcb="libxcb-cursor0"
        pkg_headers="kernel-headers"
        pkg_build="gcc python3-devel make"
        pkg_gamepad_base="libSDL2-2_0-0 libSDL2_image-2_0-0 libSDL2_mixer-2_0-0 libSDL2_ttf-2_0-0"
        ;;
    *)
        echo -e "  ${RED}Unsupported distro (cannot detect apt/dnf/zypper).${NC}"
        echo -e "  ${YELLOW}Please manually install:${NC}"
        echo -e "    - A Qt 6 compatible cursor library (libxcb-cursor)"
        echo -e "    - (optional) SDL2 + pygame for gamepad support"
        echo -e "  ${CYAN}Then re-run this installer.${NC}"
        exit 1
        ;;
esac

# ---- uv ----
install_uv() {
    echo -e "  ${YELLOW}→${NC} Installing uv for $REAL_USER..."
    if [ "$(id -u)" -eq 0 ] && [ "$REAL_USER" != "root" ]; then
        su "$REAL_USER" -c 'curl -LsSf https://astral.sh/uv/install.sh | sh'
    else
        curl -LsSf https://astral.sh/uv/install.sh | sh
    fi
    [ -f "$REAL_HOME/.cargo/env" ] && source "$REAL_HOME/.cargo/env"
    export PATH="$REAL_HOME/.cargo/bin:$PATH"
    echo -e "  ${GREEN}✓${NC} uv installed to $REAL_HOME/.cargo/bin"
}

command -v uv &>/dev/null || install_uv
echo -e "  ${GREEN}✓${NC} uv $(uv --version 2>/dev/null | head -1)"

# ---- System deps (Qt needs X11 cursor) ----
if ! $PKG_CHECK "$pkg_xcb" &>/dev/null 2>&1; then
    echo -e "  ${YELLOW}→${NC} Installing ${pkg_xcb}..."
    $PKG_UPDATE
    $PKG_INSTALL $pkg_xcb
fi
echo -e "  ${GREEN}✓${NC} ${pkg_xcb}"

# ---- Kernel headers (needed to build evdev for pynput) ----
if ! $PKG_CHECK "$pkg_headers" &>/dev/null 2>&1; then
    echo -e "  ${YELLOW}→${NC} Installing ${pkg_headers}..."
    $PKG_UPDATE
    $PKG_INSTALL "$pkg_headers"
fi
echo -e "  ${GREEN}✓${NC} ${pkg_headers}"

# ---- Build toolchain (needed to compile evdev C extension) ----
if ! $PKG_CHECK "$(echo $pkg_build | cut -d' ' -f1)" &>/dev/null 2>&1; then
    echo -e "  ${YELLOW}→${NC} Installing build toolchain: ${pkg_build}..."
    $PKG_UPDATE
    # shellcheck disable=SC2086
    $PKG_INSTALL $pkg_build
fi
echo -e "  ${GREEN}✓${NC} build toolchain (${pkg_build})"

# ---- Gamepad (optional) ----
GAMEPAD_PKGS=""
if [ "$(id -u)" -eq 0 ]; then
    GAMEPAD_PKGS="$pkg_gamepad_base"
    echo -e "  ${CYAN}→${NC} Running as root — including SDL2 + pygame for gamepad"
else
    read -p "  Install gamepad support (SDL2 + pygame)? [y/N] " -r answer
    case "$answer" in
        [yY]*) GAMEPAD_PKGS="$pkg_gamepad_base" ;;
        *)     echo -e "  ${CYAN}→${NC} Skipping gamepad" ;;
    esac
fi

if [ -n "$GAMEPAD_PKGS" ]; then
    for pkg in $GAMEPAD_PKGS; do
        $PKG_CHECK "$pkg" &>/dev/null 2>&1 && echo -e "  ${GREEN}✓${NC} $pkg" || 
            { $PKG_INSTALL "$pkg" 2>/dev/null; 
              echo -e "  ${GREEN}✓${NC} $pkg (installed)"; }
    done
    # Install pygame into uv's environment
    uv pip install --system pygame 2>/dev/null || true
    echo -e "  ${GREEN}✓${NC} pygame (gamepad ready)"
fi

# ---- Terminal auto-detect (inform user) ----
# config.py already auto-detects at runtime — we just report what's found.
detect_terminal() {
    for cmd in konsole gnome-terminal xfce4-terminal kitty alacritty xterm terminator foot; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return
        fi
    done
    echo "unknown"
}

TERMINAL=$(detect_terminal)
echo -e "  ${GREEN}✓${NC} Detected terminal: ${CYAN}${TERMINAL}${NC}"

# ---- Launch script ----
LAUNCHER="$PROJECT_ROOT/launch.sh"
cat > "$LAUNCHER" << EOF
#!/usr/bin/env bash
export PATH="\$HOME/.cargo/bin:\$PATH"
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
