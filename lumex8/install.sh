#!/usr/bin/env bash
#
# Lumex8 — self-installing launcher setup
#
# Run as root (sudo) to auto-install everything:
#   sudo ./install.sh
#
# Run as normal user for guided setup:
#   ./install.sh
#
set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
RED="\033[0;31m"
NC="\033[0m"

# ---- Detect root ----
if [ "$(id -u)" -eq 0 ]; then
    IS_ROOT=true
    SUDO=""
else
    IS_ROOT=false
    SUDO="sudo"
fi

# ---- Banner ----
echo -e "${CYAN}${BOLD}"
echo "  _      ____  __  __ _____ ____   _  _ "
echo " | |    |  _ \|  \/  | ____|___ \ / || |"
echo " | |    | |_) | |\/| |  _|   __) | || |"
echo " | |___ |  __/| |  | | |___ / __/| || |"
echo " |_____||_|   |_|  |_|_____|_____|_||_|"
echo -e "${NC}"
echo -e "${BOLD}Lumex8 Installer${NC}"
echo ""

# ---- Step 1: Project root ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"
echo -e "  Project root: ${CYAN}$PROJECT_ROOT${NC}"

if [ ! -f "lumex8/__main__.py" ]; then
    echo -e "${RED}Error: Can't find lumex8/ package${NC}"
    exit 1
fi

# ---- Step 2: Auto-install system packages ----
install_system_pkg() {
    local pkg="$1"
    if dpkg -s "$pkg" &>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $pkg"
        return 0
    fi
    if $IS_ROOT; then
        echo -e "  ${YELLOW}→${NC} Installing $pkg..."
        apt-get update -qq
        apt-get install -y -qq "$pkg"
        echo -e "  ${GREEN}✓${NC} $pkg (installed)"
    else
        echo -e "  ${YELLOW}→${NC} Installing $pkg..."
        $SUDO apt-get update -qq 2>/dev/null || true
        $SUDO apt-get install -y -qq "$pkg"
        echo -e "  ${GREEN}✓${NC} $pkg (installed)"
    fi
}

echo -e "
${BOLD}Step 1: System packages${NC}"

# Python + venv
for py in python3.12 python3.13 python3; do
    if command -v "$py" &>/dev/null; then
        PYTHON="$py"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    if command -v apt-get &>/dev/null; then
        install_system_pkg "python3.12"
        install_system_pkg "python3.12-venv"
        PYTHON="python3.12"
    else
        echo -e "${RED}Error: Python 3.12+ not found and apt not available.${NC}"
        exit 1
    fi
fi
echo -e "  ${GREEN}✓${NC} $($PYTHON --version)"

# Qt cursor support (needed on X11)
install_system_pkg "libxcb-cursor0"

# Venv
if ! $PYTHON -c "import venv" &>/dev/null; then
    install_system_pkg "$($PYTHON -c 'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}-venv")')"
fi

# ---- Step 3: Gamepad support (optional) ----
echo -e "
${BOLD}Step 2: Gamepad support${NC}"
INSTALL_PYGAME=false

if $IS_ROOT; then
    INSTALL_PYGAME=true
    echo -e "  ${CYAN}→${NC} Running as root — including gamepad support"
else
    echo -ne "  Install gamepad support? (requires SDL2 + pygame) [y/N] "
    read -r answer
    case "$answer" in
        [yY]|[yY][eE][sS]) INSTALL_PYGAME=true ;;
        *) echo -e "  ${CYAN}→${NC} Skipping gamepad support (run again with -g to add)" ;;
    esac
fi

if $INSTALL_PYGAME; then
    # SDL2 runtime libs
    for sdl in libsdl2-2.0-0 libsdl2-image-2.0-0 libsdl2-mixer-2.0-0 libsdl2-ttf-2.0-0; do
        install_system_pkg "$sdl"
    done
    GAMEPAD_DEPS="pygame"
else
    GAMEPAD_DEPS=""
fi

# ---- Step 4: Choose runner ----
echo -e "
${BOLD}Step 3: Python dependencies${NC}"

if command -v uv &>/dev/null; then
    USE_UV=true
    echo -e "  ${GREEN}✓${NC} uv detected"
    echo -e "  ${CYAN}→${NC} Dependencies declared in __main__.py inline metadata"
else
    USE_UV=false
    echo -e "  ${CYAN}→${NC} Using pip + virtual environment"

    if [ ! -d ".venv" ]; then
        $PYTHON -m venv .venv
        echo -e "  ${GREEN}✓${NC} Created .venv/"
    fi
    source .venv/bin/activate

    pip install --quiet --upgrade pip
    pip install --quiet PyQt6 pynput $GAMEPAD_DEPS
    echo -e "  ${GREEN}✓${NC} Core deps installed"
    if $INSTALL_PYGAME; then
        echo -e "  ${GREEN}✓${NC} pygame installed (gamepad ready)"
    fi
fi

# ---- Step 5: Generate launch.sh ----
LAUNCHER="$PROJECT_ROOT/launch.sh"
if $USE_UV; then
    cat > "$LAUNCHER" << LAUNCH_EOF
#!/usr/bin/env bash
cd "$PROJECT_ROOT"
uv run "$PROJECT_ROOT/lumex8/__main__.py"
LAUNCH_EOF
else
    cat > "$LAUNCHER" << LAUNCH_EOF
#!/usr/bin/env bash
cd "$PROJECT_ROOT"
source .venv/bin/activate
python "$PROJECT_ROOT/lumex8/__main__.py"
LAUNCH_EOF
fi
chmod +x "$LAUNCHER"
echo -e "  ${GREEN}✓${NC} Created launch.sh"

# ---- Step 6: Generate .desktop ----
DESKTOP="$PROJECT_ROOT/lumex8.desktop"
ICON_PATH="$PROJECT_ROOT/lumex8/icons/cmd_unpin.svg"
cat > "$DESKTOP" << DESKTOP_EOF
[Desktop Entry]
Name=Lumex8
Comment=Windows 8 style tile launcher
Exec=$LAUNCHER
Icon=$ICON_PATH
Terminal=false
Type=Application
Categories=Utility;
StartupNotify=false
DESKTOP_EOF
chmod +x "$DESKTOP"
echo -e "  ${GREEN}✓${NC} Created lumex8.desktop"

# ---- Step 7: Revert ownership if ran as root ----
if $IS_ROOT; then
    USER_HOME=$(eval echo "~$SUDO_USER")
    if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
        chown -R "$SUDO_USER:$SUDO_USER" "$PROJECT_ROOT" 2>/dev/null || true
        echo -e "  ${GREEN}✓${NC} Ownership reverted to $SUDO_USER"
    fi
fi

# ---- Done ----
echo ""
echo -e "${GREEN}${BOLD}Done.${NC}"
echo ""
echo "Launch:"
echo -e "  ${CYAN}./launch.sh${NC}"
echo "  ${CYAN}cp lumex8.desktop ~/.local/share/applications/${NC}"
echo ""
echo "Controls: Super+P toggle | Right-click = AppBar | ⚙ = settings"
echo ""
