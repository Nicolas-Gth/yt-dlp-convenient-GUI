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

# -------------------------------------------------------------------
# macOS: ensure Python 3.10+ (yt-dlp requires it)
# -------------------------------------------------------------------
if [[ "$OSTYPE" == "darwin"* ]]; then
    _py_version=$(python3 -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null)
    # Check if Homebrew has a suitable Python already
    _brew_py=""
    for bp in /opt/homebrew/bin/python3 /usr/local/bin/python3; do
        if [[ -x "$bp" ]]; then
            bver=$("$bp" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null)
            if [[ "$bver" == "True" ]]; then
                _brew_py="$bp"
                break
            fi
        fi
    done

    if [[ "$_py_version" != "True" ]] && [[ -z "$_brew_py" ]]; then
        # Need to install Python 3.10+ via Homebrew
        if command -v brew >/dev/null 2>&1; then
            _py_msg=$(_raw_t "install.python_not_found")
            _py_msg="Python 3.10+ requis (Python 3.9 n'est plus supporté par yt-dlp)."
            if command -v osascript >/dev/null 2>&1; then
                osascript -e "display dialog \"$_py_msg\" with title \"$APP_NAME\" buttons {\"OK\"} default button \"OK\"" 2>/dev/null
            fi
            brew install python@3
            exec "$0" "$@"
        fi
    fi
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS: create a .app bundle in /Applications
    MACOS_APP="/Applications/yt-dlp Convenient GUI.app"
else
    # Linux: .desktop entry + launcher script
    ICON_NAME="yt-dlp-convenient-gui"
    ICON_DIR="$HOME/.local/share/icons/hicolor/256x256/apps"
    ICON_DEST="${ICON_DIR}/${ICON_NAME}.png"
    DESKTOP_DIR="$HOME/.local/share/applications"
    DESKTOP_FILE="${DESKTOP_DIR}/yt-dlp-gui.desktop"
    LAUNCHER_DIR="$HOME/.local/bin"
    LAUNCHER="${LAUNCHER_DIR}/yt-dlp-gui-launcher"
fi

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
    # Prefer Homebrew Python 3.10+ over system Python 3.9
    local py="python3"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        for bp in /opt/homebrew/bin/python3 /usr/local/bin/python3; do
            if [[ -x "$bp" ]]; then
                local ver
                ver=$("$bp" -c "import sys; print(sys.version_info >= (3,10))" 2>/dev/null)
                if [[ "$ver" == "True" ]]; then
                    py="$bp"
                    break
                fi
            fi
        done
    fi
    # On Apple-Silicon Macs, force native ARM64 architecture.
    # The .app bundle may be launched under Rosetta (x86_64) which causes
    # Homebrew (installed in /opt/homebrew) to refuse to work.
    if [[ "$OSTYPE" == "darwin"* ]] && [[ "$(uname -m)" == "x86_64" ]] && [[ -x /usr/bin/arch ]]; then
        exec /usr/bin/arch -arm64 "$py" run.py
    fi
    exec "$py" run.py
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

if [[ "$OSTYPE" == "darwin"* ]]; then
    # ---- macOS: .app bundle ----
    _shortcut_installed() {
        [[ -d "$MACOS_APP" ]]
    }

    _shortcut_needs_repair() {
        if [[ -d "$MACOS_APP" ]]; then
            local script="$MACOS_APP/Contents/MacOS/launcher.sh"
            [[ -f "$script" ]] && grep -q "APP_DIR=\"${APP_DIR}\"" "$script" 2>/dev/null && return 1
            return 0
        fi
        return 1
    }

    _install_shortcut() {
        local contents="$MACOS_APP/Contents"
        local macos_dir="$contents/MacOS"
        local resources="$contents/Resources"

        mkdir -p "$macos_dir" "$resources"

        # Convert PNG icon to icns (macOS native format)
        if [[ -f "$ICON_SRC" ]]; then
            local iconset
            iconset=$(mktemp -d "${TMPDIR:-/tmp}/ytdlp_icon.XXXXXX").iconset
            mkdir -p "$iconset"
            sips -z 256 256 "$ICON_SRC" --out "$iconset/icon_256x256.png" >/dev/null 2>&1
            sips -z 128 128 "$ICON_SRC" --out "$iconset/icon_128x128.png" >/dev/null 2>&1
            iconutil -c icns "$iconset" -o "$resources/AppIcon.icns" 2>/dev/null || \
                cp "$ICON_SRC" "$resources/AppIcon.png"
            rm -rf "$iconset"
        fi

        # Info.plist
        cat > "$contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>yt-dlp Convenient GUI</string>
    <key>CFBundleDisplayName</key>
    <string>yt-dlp Convenient GUI</string>
    <key>CFBundleIdentifier</key>
    <string>com.nicolasgth.ytdlp-convenient-gui</string>
    <key>CFBundleExecutable</key>
    <string>launcher.sh</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
</dict>
</plist>
PLIST

        # Launcher script
        local moved_msg
        moved_msg=$(t "shortcut.moved")
        cat > "$macos_dir/launcher.sh" <<'WRAPPER_HEAD'
#!/bin/bash
# Source shell profile to get Homebrew and other tools in PATH.
# macOS .app bundles don't inherit the user's shell environment.
for f in "$HOME/.zprofile" "$HOME/.bash_profile" "$HOME/.profile"; do
    [[ -f "$f" ]] && source "$f" 2>/dev/null && break
done
# Also ensure common Homebrew paths are present
for p in /opt/homebrew/bin /usr/local/bin; do
    [[ -d "$p" ]] && [[ ":$PATH:" != *":$p:"* ]] && export PATH="$p:$PATH"
done
WRAPPER_HEAD
        cat >> "$macos_dir/launcher.sh" <<WRAPPER_TAIL
APP_DIR="${APP_DIR}"
if [[ ! -d "\$APP_DIR" ]] || [[ ! -f "\$APP_DIR/install.sh" ]]; then
    msg="${moved_msg//\{path\}/\$APP_DIR}"
    osascript -e "display dialog \"\$msg\" with title \"yt-dlp Convenient GUI\" buttons {\"OK\"} default button \"OK\"" 2>/dev/null
    exit 1
fi
exec "\$APP_DIR/install.sh" --launch
WRAPPER_TAIL
        chmod +x "$macos_dir/launcher.sh"
    }

    _remove_shortcut() {
        rm -rf "$MACOS_APP"
    }

    _refresh_menu() {
        true  # No-op on macOS
    }

    _kmenuedit_unhide() {
        true  # No-op on macOS
    }

else
    # ---- Linux: .desktop entry ----
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

        _kmenuedit_unhide
        local _comment
        _comment=$(t "shortcut.comment")
        mkdir -p "$DESKTOP_DIR"
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

    _refresh_menu() {
        update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
        command -v kbuildsycoca6 >/dev/null 2>&1 && kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
    }
fi

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

# -------------------------------------------------------------------
# macOS osascript helpers (used when zenity is not available)
# -------------------------------------------------------------------

# _osascript_ask BUTTON1 BUTTON2 BUTTON3 TEXT
# Shows a dialog with up to 3 buttons via osascript.
# Returns: 0 = button1 (rightmost/default), 1 = button2, 2 = button3 (leftmost)
_osascript_ask() {
    local btn1="$1" btn2="$2" btn3="$3" text="$4"
    local result
    result=$(osascript -e "
        tell application \"System Events\"
            display dialog \"$text\" with title \"$APP_NAME\" buttons {\"$btn3\", \"$btn2\", \"$btn1\"} default button \"$btn1\"
            return button returned of result
        end tell
    " 2>/dev/null) || { return 2; }  # User cancelled or error → treat as quit

    if [[ "$result" == "$btn1" ]]; then
        return 0
    elif [[ "$result" == "$btn2" ]]; then
        return 1
    else
        return 2
    fi
}

_osascript_info() {
    local text="$1"
    osascript -e "
        tell application \"System Events\"
            display dialog \"$text\" with title \"$APP_NAME\" buttons {\"OK\"} default button \"OK\"
        end tell
    " >/dev/null 2>&1 || true
}

if ! command -v zenity >/dev/null 2>&1; then
    if [[ "$OSTYPE" == "darwin"* ]] && command -v osascript >/dev/null 2>&1; then
        # macOS: use osascript dialogs (mirrors the zenity logic below)
        if _shortcut_installed; then
            if _shortcut_needs_repair; then
                _osascript_ask \
                    "$(t shortcut.btn_repair)" \
                    "$(t shortcut.btn_no_repair)" \
                    "$BTN_QUIT" \
                    "$(t shortcut.repair)"
                rc=$?
                [[ $rc -eq 2 ]] && exit 0
                [[ $rc -eq 0 ]] && { _install_shortcut; _refresh_menu; }
                _launch_app
            else
                _osascript_ask \
                    "$(t shortcut.btn_remove)" \
                    "$(t shortcut.btn_launch)" \
                    "$BTN_QUIT" \
                    "$(t shortcut.remove)"
                rc=$?
                [[ $rc -eq 2 ]] && exit 0
                [[ $rc -eq 0 ]] && { _remove_shortcut; _osascript_info "$(t shortcut.removed)"; _refresh_menu; exit 0; }
                _launch_app
            fi
        else
            _osascript_ask \
                "$(t shortcut.btn_create)" \
                "$(t shortcut.btn_no_create)" \
                "$BTN_QUIT" \
                "$(t shortcut.create)"
            rc=$?
            [[ $rc -eq 2 ]] && exit 0
            if [[ $rc -eq 0 ]]; then
                _install_shortcut
                _osascript_info "$(t shortcut.created)"
                _refresh_menu
                exit 0
            fi
            _launch_app
        fi
    else
        _launch_app
    fi
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
