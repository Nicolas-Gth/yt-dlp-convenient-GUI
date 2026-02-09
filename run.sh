#!/bin/bash

# yt-dlp Convenient GUI - Universal Installation and Launch Script
# Supports macOS, Ubuntu/Debian, Fedora/RHEL, Arch Linux, and other distributions

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Set title
echo -e "${BLUE}▗▖  ▗▖▗▄▄▄▖    ▗▄▄▄ ▗▖   ▗▄▄▖                                          ${NC}"
echo -e "${BLUE} ▝▚▞▘   █      ▐▌  █▐▌   ▐▌ ▐▌                                         ${NC}"
echo -e "${BLUE}  ▐▌    █  ▀▀▘ ▐▌  █▐▌   ▐▛▀▘                                          ${NC}"
echo -e "${BLUE}  ▐▌    █      ▐▙▄▄▀▐▙▄▄▖▐▌                                            ${NC}"
echo -e "${BLUE} ▗▄▄▖ ▗▄▖ ▗▖  ▗▖▗▖  ▗▖▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖▗▄▄▄▖▗▖  ▗▖▗▄▄▄▖   ▗▄▄▖▗▖ ▗▖▗▄▄▄▖${NC}"
echo -e "${BLUE}▐▌   ▐▌ ▐▌▐▛▚▖▐▌▐▌  ▐▌▐▌   ▐▛▚▖▐▌  █  ▐▌   ▐▛▚▖▐▌  █    ▐▌   ▐▌ ▐▌  █  ${NC}"
echo -e "${BLUE}▐▌   ▐▌ ▐▌▐▌ ▝▜▌▐▌  ▐▌▐▛▀▀▘▐▌ ▝▜▌  █  ▐▛▀▀▘▐▌ ▝▜▌  █    ▐▌▝▜▌▐▌ ▐▌  █  ${NC}"
echo -e "${BLUE}▝▚▄▄▖▝▚▄▞▘▐▌  ▐▌ ▝▚▞▘ ▐▙▄▄▖▐▌  ▐▌▗▄█▄▖▐▙▄▄▖▐▌  ▐▌  █    ▝▚▄▞▘▝▚▄▞▘▗▄█▄▖${NC}"
echo

# Function to detect OS and distribution
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        DISTRO="macos"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if command -v lsb_release >/dev/null 2>&1; then
            DISTRO=$(lsb_release -si | tr '[:upper:]' '[:lower:]')
        elif [[ -f /etc/os-release ]]; then
            DISTRO=$(grep '^ID=' /etc/os-release | cut -d'=' -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]')
        elif [[ -f /etc/arch-release ]]; then
            DISTRO="arch"
        elif [[ -f /etc/fedora-release ]]; then
            DISTRO="fedora"
        elif [[ -f /etc/debian_version ]]; then
            DISTRO="debian"
        else
            DISTRO="unknown"
        fi
    else
        OS="unknown"
        DISTRO="unknown"
    fi
    
    echo -e "${BLUE}Detected OS: ${YELLOW}$OS${NC} (${YELLOW}$DISTRO${NC})"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Python dependencies
check_python_deps() {
    # Check if venv exists and activate it
    if [[ -d "venv" ]]; then
        source venv/bin/activate
        python -c "import yt_dlp, PIL, ttkthemes, plyer, mutagen" >/dev/null 2>&1
        local result=$?
        deactivate 2>/dev/null || true
        return $result
    else
        # If no venv, check system-wide
        python3 -c "import yt_dlp, PIL, ttkthemes, plyer, mutagen" >/dev/null 2>&1
        return $?
    fi
}

# Function to check all components
check_components() {
    local all_ok=1
    
    # Check Python 3
    if command_exists python3; then
        echo -e "${GREEN}[OK]${NC} Python 3 is installed"
        python3 --version
    else
        echo -e "${RED}[MISSING]${NC} Python 3 not found"
        all_ok=0
    fi
    
    # Check pip
    if command_exists pip3 || command_exists pip; then
        echo -e "${GREEN}[OK]${NC} pip is available"
    else
        echo -e "${RED}[MISSING]${NC} pip not found"
        all_ok=0
    fi
    
    # Check FFmpeg
    if command_exists ffmpeg; then
        echo -e "${GREEN}[OK]${NC} FFmpeg is installed"
        ffmpeg -version 2>/dev/null | head -1
    else
        echo -e "${RED}[MISSING]${NC} FFmpeg not found"
        all_ok=0
    fi
    
    # Check Python dependencies
    if [ $all_ok -eq 1 ]; then
        if check_python_deps; then
            echo -e "${GREEN}[OK]${NC} All Python dependencies are installed"
        else
            echo -e "${RED}[MISSING]${NC} Some Python dependencies are missing"
            all_ok=0
        fi
    fi
    
    # Return 0 for success (all OK), 1 for failure (something missing)
    if [ $all_ok -eq 1 ]; then
        return 0
    else
        return 1
    fi
}

# Function to install packages based on distribution
install_packages() {
    local packages=("$@")
    
    case $DISTRO in
        "macos")
            # Install Homebrew if not present
            if ! command_exists brew; then
                echo -e "${YELLOW}Installing Homebrew...${NC}"
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                # Add Homebrew to PATH
                if [[ -f "/opt/homebrew/bin/brew" ]]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)"
                elif [[ -f "/usr/local/bin/brew" ]]; then
                    eval "$(/usr/local/bin/brew shellenv)"
                fi
            fi
            brew install "${packages[@]}"
            ;;
        "ubuntu"|"debian"|"linuxmint"|"pop"|"elementary")
            sudo apt update
            sudo apt install -y "${packages[@]}"
            ;;
        "fedora"|"rhel"|"centos"|"almalinux"|"rocky")
            if command_exists dnf; then
                sudo dnf install -y "${packages[@]}"
            else
                sudo yum install -y "${packages[@]}"
            fi
            ;;
        "arch"|"manjaro"|"endeavouros"|"garuda")
            if command_exists yay; then
                yay -S --noconfirm "${packages[@]}"
            elif command_exists paru; then
                paru -S --noconfirm "${packages[@]}"
            else
                sudo pacman -S --noconfirm "${packages[@]}"
            fi
            ;;
        "opensuse"|"suse")
            sudo zypper install -y "${packages[@]}"
            ;;
        "void")
            sudo xbps-install -Sy "${packages[@]}"
            ;;
        "alpine")
            sudo apk add "${packages[@]}"
            ;;
        *)
            echo -e "${RED}[ERROR]${NC} Unsupported distribution: $DISTRO"
            echo -e "${YELLOW}Please install the following packages manually:${NC}"
            printf '%s\n' "${packages[@]}"
            return 1
            ;;
    esac
}

# Function to get Python and FFmpeg package names for each distro
get_package_names() {
    case $DISTRO in
        "macos")
            PYTHON_PACKAGE="python@3.11"
            FFMPEG_PACKAGE="ffmpeg"
            ;;
        "ubuntu"|"debian"|"linuxmint"|"pop"|"elementary")
            PYTHON_PACKAGE="python3 python3-pip python3-venv python3-tk"
            FFMPEG_PACKAGE="ffmpeg"
            ;;
        "fedora"|"rhel"|"centos"|"almalinux"|"rocky")
            PYTHON_PACKAGE="python3 python3-pip python3-tkinter"
            FFMPEG_PACKAGE="ffmpeg"
            ;;
        "arch"|"manjaro"|"endeavouros"|"garuda")
            PYTHON_PACKAGE="python python-pip tk"
            FFMPEG_PACKAGE="ffmpeg"
            ;;
        "opensuse"|"suse")
            PYTHON_PACKAGE="python3 python3-pip python3-tk"
            FFMPEG_PACKAGE="ffmpeg-4"
            ;;
        "void")
            PYTHON_PACKAGE="python3 python3-pip python3-tkinter"
            FFMPEG_PACKAGE="ffmpeg"
            ;;
        "alpine")
            PYTHON_PACKAGE="python3 py3-pip py3-tkinter"
            FFMPEG_PACKAGE="ffmpeg"
            ;;
        *)
            PYTHON_PACKAGE="python3"
            FFMPEG_PACKAGE="ffmpeg"
            ;;
    esac
}

# Function to install components
install_components() {
    detect_os
    get_package_names
    
    echo -e "${YELLOW}[1/4] Installing Python 3 and system dependencies...${NC}"
    if ! command_exists python3; then
        install_packages $PYTHON_PACKAGE
        if ! command_exists python3; then
            echo -e "${RED}[ERROR]${NC} Failed to install Python 3"
            exit 1
        fi
    else
        # Install additional packages even if Python3 exists
        case $DISTRO in
            "fedora"|"rhel"|"centos"|"almalinux"|"rocky")
                # Ensure tkinter is installed for ttkthemes
                if ! python3 -c "import tkinter" >/dev/null 2>&1; then
                    echo -e "${YELLOW}Installing python3-tkinter...${NC}"
                    if command_exists dnf; then
                        sudo dnf install -y python3-tkinter
                    else
                        sudo yum install -y python3-tkinter
                    fi
                fi
                ;;
            "ubuntu"|"debian"|"linuxmint"|"pop"|"elementary")
                if ! python3 -c "import tkinter" >/dev/null 2>&1; then
                    echo -e "${YELLOW}Installing python3-tk...${NC}"
                    sudo apt update && sudo apt install -y python3-tk
                fi
                ;;
        esac
        echo -e "${GREEN}[OK]${NC} Python 3 is already installed"
    fi
    
    # Ensure pip is available and updated
    echo -e "${YELLOW}[2/4] Ensuring pip is available and updated...${NC}"
    if ! command_exists pip3 && ! command_exists pip; then
        python3 -m ensurepip --upgrade 2>/dev/null || true
    fi
    
    # Use pip3 if available, otherwise pip
    local pip_cmd="pip3"
    if ! command_exists pip3; then
        pip_cmd="pip"
    fi
    
    python3 -m pip install --upgrade pip
    
    echo -e "${YELLOW}[3/4] Installing Python dependencies...${NC}"
    
    # Create virtual environment if it doesn't exist
    if [[ ! -d "venv" ]]; then
        echo -e "${YELLOW}Creating virtual environment...${NC}"
        python3 -m venv venv
        if [[ $? -ne 0 ]]; then
            echo -e "${RED}[ERROR]${NC} Failed to create virtual environment"
            echo -e "${YELLOW}[INFO]${NC} Make sure python3-venv is installed"
            exit 1
        fi
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip in venv
    python -m pip install --upgrade pip
    
    # Install dependencies in venv
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    else
        pip install "yt-dlp>=2023.12.30" "Pillow>=10.0.0" "ttkthemes>=3.2.2" "plyer>=2.1.0" "mutagen>=1.47.0"
    fi
    
    # Deactivate venv
    deactivate
    
    echo -e "${YELLOW}[4/4] Installing FFmpeg...${NC}"
    if ! command_exists ffmpeg; then
        install_packages $FFMPEG_PACKAGE
        if ! command_exists ffmpeg; then
            echo -e "${YELLOW}[WARNING]${NC} FFmpeg installation may have failed"
            echo -e "${YELLOW}Please install FFmpeg manually for your distribution${NC}"
        fi
    else
        echo -e "${GREEN}[OK]${NC} FFmpeg is already installed"
    fi
    
    echo -e "${GREEN}[OK] Installation completed!${NC}"
    echo
}

# Function to launch the application
launch_app() {
    echo -e "${BLUE}Launching yt-dlp Convenient GUI...${NC}"
    
    # Final verification
    if ! command_exists python3; then
        echo -e "${RED}[ERROR]${NC} Python 3 not accessible"
        exit 1
    fi
    
    # Launch the application using venv if it exists
    if [[ -d "venv" ]]; then
        source venv/bin/activate
        python run.py
        local exit_code=$?
        deactivate
        
        if [ $exit_code -ne 0 ]; then
            echo
            echo -e "${RED}[ERROR]${NC} Application launch failed"
            echo -e "${YELLOW}[INFO]${NC} Press any key to exit..."
            read -n 1
        fi
    else
        # Fallback to system python
        python3 run.py
        
        if [ $? -ne 0 ]; then
            echo
            echo -e "${RED}[ERROR]${NC} Application launch failed"
            echo -e "${YELLOW}[INFO]${NC} Press any key to exit..."
            read -n 1
        fi
    fi
}

# Function to check for updates from GitHub
check_for_updates() {
    # Only check if git is available and we're in a git repo
    if ! command_exists git; then
        echo -e "${YELLOW}[SKIP]${NC} git is not installed, skipping update check"
        echo
        return
    fi
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo -e "${YELLOW}[SKIP]${NC} Not a git repository, skipping update check"
        echo
        return
    fi

    echo -e "${YELLOW}Checking for updates...${NC}"

    # Fetch latest changes without modifying working tree
    if ! git fetch origin 2>/dev/null; then
        echo -e "${YELLOW}[SKIP]${NC} Could not reach GitHub (no internet?)"
        return
    fi

    # Compare local and remote
    LOCAL=$(git rev-parse HEAD 2>/dev/null)
    REMOTE=$(git rev-parse origin/main 2>/dev/null || git rev-parse origin/master 2>/dev/null)

    if [[ -z "$REMOTE" ]]; then
        echo -e "${YELLOW}[SKIP]${NC} Could not determine remote branch"
        return
    fi

    if [[ "$LOCAL" == "$REMOTE" ]]; then
        echo -e "${GREEN}[OK]${NC} Already up to date"
    else
        BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || git rev-list --count HEAD..origin/master 2>/dev/null)
        echo -e "${YELLOW}[UPDATE]${NC} ${BEHIND} new commit(s) available"
        echo -e "${YELLOW}Update now? (Y/n):${NC}"
        read -r update_response
        if [[ ! "$update_response" =~ ^[Nn]$ ]]; then
            # Determine remote branch
            local remote_branch
            if git rev-parse origin/main >/dev/null 2>&1; then
                remote_branch="origin/main"
            else
                remote_branch="origin/master"
            fi
            # Force reset to remote (overwrites all local changes)
            git reset --hard "$remote_branch" 2>/dev/null
            if [[ $? -eq 0 ]]; then
                echo -e "${GREEN}[OK]${NC} Updated successfully!"
            else
                echo -e "${RED}[ERROR]${NC} Update failed."
            fi
        else
            echo -e "${YELLOW}[SKIP]${NC} Update skipped"
        fi
    fi
    echo
}

# Main script logic
check_for_updates
echo -e "${YELLOW}Checking system components...${NC}"
echo

if check_components; then
    echo
    echo -e "${GREEN}All components are ready!${NC}"
    echo
    launch_app
else
    echo
    echo -e "${YELLOW}Some components are missing. Starting installation...${NC}"
    echo
    
    # Ask for confirmation since installations may require admin privileges
    echo -e "${YELLOW}This script will install missing components using your system's package manager.${NC}"
    echo -e "${YELLOW}You may be prompted for your password for sudo operations.${NC}"
    echo -e "${YELLOW}Continue? (y/N):${NC}"
    read -r response
    
    if [[ "$response" =~ ^[Yy]$ ]]; then
        install_components
        echo
        echo -e "${BLUE}Verifying installation...${NC}"
        if check_components; then
            echo
            launch_app
        else
            echo -e "${RED}[ERROR]${NC} Installation verification failed"
            exit 1
        fi
    else
        echo -e "${YELLOW}Installation cancelled by user.${NC}"
        exit 0
    fi
fi
