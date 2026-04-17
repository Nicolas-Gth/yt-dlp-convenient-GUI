#!/bin/bash
# yt-dlp Convenient GUI — Linux installer & shortcut manager
#
# Usage:
#   ./install.sh            → Show shortcut dialog, install desktop entry, launch app
#   ./install.sh --launch   → Launch the app directly (used by desktop shortcut)

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="yt-dlp Convenient GUI"
ICON_SRC="${APP_DIR}/assets/yt-dlp_convenient_gui_icon.png"

# -------------------------------------------------------------------
# Lightweight i18n for the install phase (before python3 is guaranteed)
# Falls back to English keys read via awk if python3 is unavailable.
# -------------------------------------------------------------------
_raw_t() {
    local key="$1"
    local lang=""
    # Try to read language from config
    if [[ -f "${APP_DIR}/yt-dlp-gui-config.json" ]]; then
        lang=$(grep -oP '"language"\s*:\s*"\K[^"]+' "${APP_DIR}/yt-dlp-gui-config.json" 2>/dev/null)
    fi
    if [[ -z "$lang" || "$lang" == "system" ]]; then
        lang="${LANG%%_*}"
        lang="${lang%%.*}"
    fi
    local file="${APP_DIR}/locales/${lang}.json"
    [[ -f "$file" ]] || file="${APP_DIR}/locales/en.json"
    # Extract value for key using awk (no python needed)
    awk -F'"' -v k="$key" '$2 == k { gsub(/\\n/,"\n",$4); print $4; exit }' "$file"
}

# -------------------------------------------------------------------
# Ensure Python 3 is installed — auto-install with user confirmation
# -------------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    # Detect distro and pick install command
    _detect_distro() {
        if [[ "$OSTYPE" == "darwin"* ]]; then
            echo "macos"
        elif [[ -f /etc/os-release ]]; then
            grep '^ID=' /etc/os-release | cut -d= -f2 | tr -d '"' | tr '[:upper:]' '[:lower:]'
        else
            echo "unknown"
        fi
    }
    DISTRO=$(_detect_distro)

    # Immutable distros: don't layer packages, show instructions instead
    if [[ -f /run/ostree-booted ]]; then
        _immutable_msg=$(_raw_t "install.python_immutable")
        zenity --error --title="$APP_NAME" --text="$_immutable_msg" \
            --window-icon="$ICON_SRC" 2>/dev/null
        exit 1
    fi

    case "$DISTRO" in
        ubuntu|debian|linuxmint|pop|elementary)
            _INSTALL_CMD="sudo apt update && sudo apt install -y python3" ;;
        fedora|rhel|centos|almalinux|rocky)
            _INSTALL_CMD="sudo dnf install -y python3" ;;
        arch|manjaro|endeavouros|garuda)
            _INSTALL_CMD="sudo pacman -S --noconfirm python" ;;
        opensuse*|suse)
            _INSTALL_CMD="sudo zypper install -y python3" ;;
        void)
            _INSTALL_CMD="sudo xbps-install -y python3" ;;
        alpine)
            _INSTALL_CMD="sudo apk add python3" ;;
        nixos)
            _INSTALL_CMD="nix profile install nixpkgs#python3" ;;
        macos)
            if command -v brew >/dev/null 2>&1; then
                _INSTALL_CMD="brew install python@3"
            else
                _INSTALL_CMD=""
            fi ;;
        *)  _INSTALL_CMD="" ;;
    esac

    _not_found=$(_raw_t "install.python_not_found")
    _installing=$(_raw_t "install.python_installing")
    _failed=$(_raw_t "install.python_failed")
    _restart=$(_raw_t "install.python_restart")

    if [[ -z "$_INSTALL_CMD" ]]; then
        # Unknown distro — just show error
        zenity --error --title="$APP_NAME" --text="$_not_found" \
            --window-icon="$ICON_SRC" 2>/dev/null
        exit 1
    fi

    # Ask user via popup
    zenity --question --title="$APP_NAME" --text="$_not_found" \
        --ok-label="OK" --cancel-label="$(_raw_t 'shortcut.btn_quit')" \
        --window-icon="$ICON_SRC" 2>/dev/null
    if [[ $? -ne 0 ]]; then
        exit 0
    fi

    # Install with progress popup
    (
        echo "# $_installing"
        eval "$_INSTALL_CMD" >/dev/null 2>&1
        if [[ $? -ne 0 ]]; then
            echo "# $_failed"
            sleep 3
            echo "100"
            exit 1
        fi
        echo "100"
    ) | zenity --progress --title="$APP_NAME" --text="$_installing" \
        --pulsate --auto-close --no-cancel \
        --window-icon="$ICON_SRC" 2>/dev/null

    if ! command -v python3 >/dev/null 2>&1; then
        zenity --error --title="$APP_NAME" --text="$_failed" \
            --window-icon="$ICON_SRC" 2>/dev/null
        exit 1
    fi

    # Success — restart the script (python3 is now available for t())
    zenity --info --title="$APP_NAME" --text="$_restart" \
        --window-icon="$ICON_SRC" 2>/dev/null
    exec "$0" "$@"
fi

ICON_NAME="yt-dlp-convenient-gui"
ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
ICON_DEST="${ICON_DIR}/${ICON_NAME}.png"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="${DESKTOP_DIR}/yt-dlp-gui.desktop"
LAUNCHER_DIR="$HOME/.local/bin"
LAUNCHER="${LAUNCHER_DIR}/yt-dlp-gui-launcher"

# -------------------------------------------------------------------
# i18n — reuse src/utils/i18n_utils.py via python3
# -------------------------------------------------------------------
t() {
    python3 -c "
import sys; sys.path.insert(0, '${APP_DIR}/src')
from utils.i18n_utils import t
print(t('$1'))
" 2>/dev/null
}

# -------------------------------------------------------------------
# Launch the app
# -------------------------------------------------------------------
_launch_app() {
    cd "$APP_DIR"
    exec python3 run.py
}

# -------------------------------------------------------------------
# Direct launch mode (called by the desktop shortcut wrapper)
# -------------------------------------------------------------------
if [[ "$1" == "--launch" ]]; then
    _launch_app
fi

# -------------------------------------------------------------------
# Shortcut helpers
# -------------------------------------------------------------------
_shortcut_installed() {
    [[ -f "$DESKTOP_FILE" ]] && [[ -f "$LAUNCHER" ]] && [[ -f "$ICON_DEST" ]]
}

_shortcut_needs_repair() {
    if [[ -f "$LAUNCHER" ]]; then
        grep -q "APP_DIR=\"${APP_DIR}\"" "$LAUNCHER" 2>/dev/null && return 1
        return 0
    fi
    return 1
}

_install_shortcut() {
    local moved_msg
    moved_msg=$(t "shortcut.moved")

    mkdir -p "$ICON_DIR"
    cp "$ICON_SRC" "$ICON_DEST"

    mkdir -p "$LAUNCHER_DIR"
    cat > "$LAUNCHER" <<WRAPPER
#!/bin/bash
APP_DIR="${APP_DIR}"
if [[ ! -d "\$APP_DIR" ]] || [[ ! -f "\$APP_DIR/install.sh" ]]; then
    msg="${moved_msg//\{path\}/\$APP_DIR}"
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --title="yt-dlp Convenient GUI" --text="\$msg" 2>/dev/null
    elif command -v notify-send >/dev/null 2>&1; then
        notify-send -u critical "yt-dlp Convenient GUI" "\$msg"
    fi
    exit 1
fi
exec "\$APP_DIR/install.sh" --launch
WRAPPER
    chmod +x "$LAUNCHER"

    # Remove from kmenuedit .hidden if a previous removal left it there
    _kmenuedit_unhide
    local _comment
    _comment=$(t "shortcut.comment")
    mkdir -p "$DESKTOP_DIR"
    # install -m 644 ensures correct permissions regardless of umask
    # (KDE ignores .desktop files with restrictive permissions like 600)
    install -m 644 /dev/stdin "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=yt-dlp Convenient GUI
Comment=${_comment}
Exec=${LAUNCHER}
Icon=${ICON_NAME}
Terminal=false
Categories=AudioVideo;
StartupWMClass=yt-dlp-convenient-gui
EOF
}

_remove_shortcut() {
    rm -f "$DESKTOP_FILE" "$LAUNCHER" "$ICON_DEST"
}

# Force desktop menu cache rebuild
_refresh_menu() {
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
    command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
}

# Remove our .desktop from kmenuedit's .hidden section (KDE adds it there on removal)
_kmenuedit_unhide() {
    local kmenu="$HOME/.config/menus/applications-kmenuedit.menu"
    if [[ -f "$kmenu" ]] && grep -q 'yt-dlp-gui\.desktop' "$kmenu" 2>/dev/null; then
        sed -i '/<Filename>yt-dlp-gui\.desktop<\/Filename>/d' "$kmenu" 2>/dev/null || true
    fi
}

# -------------------------------------------------------------------
# Shortcut management dialog
# -------------------------------------------------------------------
cd "$APP_DIR"

BTN_QUIT=$(t shortcut.btn_quit)

# Helper: run zenity with Quit as cancel (bottom) and the secondary action as extra-button.
# OK → exit 0, no stdout. Extra → exit 1, stdout = label. Cancel (Quit) → exit 1, no stdout.
# Returns: 0 = OK, 1 = extra-button (secondary action), 2 = Quit
_zenity_ask() {
    local extra_label="$1"; shift
    local result rc
    result=$(zenity "$@" --extra-button="$extra_label" --cancel-label="$BTN_QUIT" --window-icon="$ICON_SRC" 2>/dev/null)
    rc=$?
    # Normalize possible line endings and whitespace artifacts.
    result="${result//$'\r'/}"
    result="${result//$'\n'/}"

    # Across zenity versions/themes, extra-button behavior can vary.
    # The reliable discriminator is whether stdout is non-empty.
    if [[ -n "$result" ]]; then
        return 1  # extra-button clicked
    elif [[ $rc -eq 0 ]]; then
        return 0  # OK clicked
    else
        return 2  # Cancel (Quit) clicked
    fi
}

if ! command -v zenity >/dev/null 2>&1; then
    _launch_app
fi

if _shortcut_installed; then
    if _shortcut_needs_repair; then
        _zenity_ask "$(t shortcut.btn_no_repair)" --question \
            --title="$APP_NAME" \
            --text="$(t shortcut.repair)" \
            --ok-label="$(t shortcut.btn_repair)"
        rc=$?
        [[ $rc -eq 2 ]] && exit 0
        [[ $rc -eq 0 ]] && { _install_shortcut; _refresh_menu; }
        _launch_app
    else
        _zenity_ask "$(t shortcut.btn_launch)" --question \
            --title="$APP_NAME" \
            --text="$(t shortcut.remove)" \
            --ok-label="$(t shortcut.btn_remove)"
        rc=$?
        [[ $rc -eq 2 ]] && exit 0
        [[ $rc -eq 0 ]] && { _remove_shortcut; zenity --info --title="$APP_NAME" --text="$(t shortcut.removed)" --ok-label="$BTN_QUIT" --window-icon="$ICON_SRC" 2>/dev/null || true; _refresh_menu; exit 0; }
        _launch_app
    fi
else
    _zenity_ask "$(t shortcut.btn_no_create)" --question \
        --title="$APP_NAME" \
        --text="$(t shortcut.create)" \
        --ok-label="$(t shortcut.btn_create)"
    rc=$?
    [[ $rc -eq 2 ]] && exit 0
    if [[ $rc -eq 0 ]]; then
        _install_shortcut
        zenity --info --title="$APP_NAME" --text="$(t shortcut.created)" --ok-label="$BTN_QUIT" --window-icon="$ICON_SRC" 2>/dev/null || true
        _refresh_menu
        exit 0
    fi
    _launch_app
fi
