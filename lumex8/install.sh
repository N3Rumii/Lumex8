#!/usr/bin/env bash
#
# Lumex8 — one-command install script
#
# Usage:
#   chmod +x install.sh
#   ./install.sh
#
# This will:
#   1. Check for Python 3.12+
#   2. Create a virtual environment (or use uv if available)
#   3. Install dependencies (PyQt6, pynput, pygame)
#   4. Generate launch.sh and a .desktop file
#   5. Print launch instructions
#

set -e

BOLD="\033[1m"
GREEN="\033[0;32m"
YELLOW="\033[0;33m"
CYAN="\033[0;36m"
NC="\033[0m"

echo -e "${CYAN}${BOLD}"
echo "  _      ____  __  __ _____ ____   _  _ "
echo " | |    |  _ \|  \/  | ____|___ \ / || |"
echo " | |    | |_) | |\/| |  _|   __) | || |"
echo " | |___ |  __/| |  | | |___ / __/| || |"
echo " |_____||_|   |_|  |_|_____|_____|_||_|"
echo -e "${NC}"
echo -e "${BOLD}Lumex8 Installer${NC}"
echo ""

# ---- Step 1: Find project root ----
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."
PROJECT_ROOT="$(pwd)"

if [ ! -f "lumex8/__main__.py" ]; then
    echo -e "${YELLOW}Error: Can't find lumex8/ package${NC}"
    echo "Make sure install.sh is inside lumex8/ with its parent containing the package."
    exit 1
fi

echo -e "  Project root: ${CYAN}$PROJECT_ROOT${NC}"

# ---- Step 2: Python ----
PYTHON=""
for cmd in python3.12 python3.13 python3; do
    if command -v "$cmd" &> /dev/null; then
        PYTHON="$cmd"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo -e "${YELLOW}Error: Python 3.12+ not found.${NC}"
    echo "Install it:  sudo apt install python3.12 python3.12-venv"
    exit 1
fi
echo -e "  ${GREEN}✓${NC} $($PYTHON --version)"

# ---- Step 3: Choose runner (uv preferred) ----
USE_UV=false
if command -v uv &> /dev/null; then
    USE_UV=true
    echo -e "  ${GREEN}✓${NC} Found uv — using fast package manager"
elif $PYTHON -c "import venv" &> /dev/null; then
    echo -e "  ${CYAN}→${NC} Using virtual environment"
else
    echo -e "${YELLOW}Error: python3-venv not installed and uv not found.${NC}"
    echo "Install one:  pip install uv  OR  sudo apt install python3-venv"
    exit 1
fi

# ---- Step 4: Install dependencies ----
if $USE_UV; then
    echo -e "  ${CYAN}→${NC} uv will resolve deps from __main__.py inline metadata"
else
    if [ ! -d "venv" ]; then
        echo -e "  ${CYAN}→${NC} Creating virtual environment..."
        $PYTHON -m venv venv
    else
        echo -e "  ${GREEN}✓${NC} Virtual environment exists (venv/)"
    fi
    echo -e "  ${CYAN}→${NC} Installing dependencies..."
    source venv/bin/activate
    pip install --quiet --upgrade pip
    pip install --quiet PyQt6 pynput pygame
    echo -e "  ${GREEN}✓${NC} Dependencies installed"
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
source venv/bin/activate
python "$PROJECT_ROOT/lumex8/__main__.py"
LAUNCH_EOF
fi
chmod +x "$LAUNCHER"
echo -e "  ${GREEN}✓${NC} Created ${CYAN}launch.sh${NC}"

# ---- Step 6: Generate .desktop file ----
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
echo -e "  ${GREEN}✓${NC} Created ${CYAN}lumex8.desktop${NC}"
echo -e "       (install with: cp lumex8.desktop ~/.local/share/applications/)"

# ---- Step 7: Done ----
echo ""
echo -e "${GREEN}${BOLD}Installation complete!${NC}"
echo ""
echo "Launch options:"
echo -e "  ${CYAN}./launch.sh${NC}                      Double-click or terminal"
echo -e "  ${CYAN}uv run python -m lumex8${NC}           From $PROJECT_ROOT"
echo -e "  ${CYAN}cp lumex8.desktop ~/.local/share/applications/${NC}"
echo "                                   Add to app launcher"
echo ""
echo "Controls:"
echo "  Super+P            Toggle launcher"
echo "  Click tile         Launch app"
echo "  Right-click tile   AppBar (actions)"
echo "  ⚙ → Add Tiles     Edit mode"
echo "  ⚙ → Settings      Configuration"
echo ""
