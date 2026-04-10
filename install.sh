#!/bin/bash

# Folio Installer Script
# This script installs Folio into an isolated virtual environment and 
# adds a 'folio' command to your ~/.local/bin directory.

set -e

INSTALL_DIR="$HOME/.local/share/folio"
BIN_DIR="$HOME/.local/bin"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting Folio installation...${NC}"

# 1. Check for Python 3.11+
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    exit 1
fi

if ! python3 -c 'import sys; exit(0) if sys.version_info >= (3, 11) else exit(1)'; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    echo -e "${RED}Error: Folio requires Python 3.11 or newer. Found $PYTHON_VERSION${NC}"
    exit 1
fi

# 2. Check for venv module (often missing on Ubuntu/Debian)
if ! python3 -m venv --help &> /dev/null; then
    echo -e "${RED}Error: The python3 'venv' module is not installed.${NC}"
    echo "On Debian/Ubuntu systems, you can install it with:"
    echo "    sudo apt install python3-venv"
    exit 1
fi

# 3. Create installation directory
echo -e "${BLUE}Creating installation directory at $INSTALL_DIR...${NC}"
mkdir -p "$INSTALL_DIR"

# 4. Create virtual environment
echo -e "${BLUE}Setting up virtual environment...${NC}"
python3 -m venv "$INSTALL_DIR/venv"

# 5. Install Folio
echo -e "${BLUE}Installing dependencies and Folio...${NC}"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip --quiet
"$INSTALL_DIR/venv/bin/pip" install "$SCRIPT_DIR" --quiet

# 6. Create wrapper script in BIN_DIR
echo -e "${BLUE}Creating executable in $BIN_DIR/folio...${NC}"
mkdir -p "$BIN_DIR"
cat << EOF > "$BIN_DIR/folio"
#!/bin/bash
# Wrapper script for Folio
exec "$INSTALL_DIR/venv/bin/folio" "\$@"
EOF
chmod +x "$BIN_DIR/folio"

# 7. Final instructions
echo -e "\n${GREEN}--------------------------------------------------${NC}"
echo -e "${GREEN}Folio has been installed successfully!${NC}"
echo -e "You can now run it using the: ${BLUE}folio${NC} command."
echo ""

# Check if BIN_DIR is in PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "${RED}Warning: $BIN_DIR is not in your PATH.${NC}"
    echo "To use 'folio' from any terminal, add this to your .bashrc or .zshrc:"
    echo -e "    ${BLUE}export PATH=\"\$PATH:$BIN_DIR\"${NC}"
    echo "Then restart your terminal."
fi
echo -e "${GREEN}--------------------------------------------------${NC}"
