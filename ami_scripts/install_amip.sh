#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Enhanced software installer for NYPL AMIP – AV Preservation/Digitization
# -----------------------------------------------------------------------------

set -euo pipefail
IFS=$'\n\t'

# ----------------------------------
# Configuration & Constants
# ----------------------------------
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly LOG_FILE="${SCRIPT_DIR}/install-$(date +%Y%m%d-%H%M%S).log"
readonly XCODE_TIMEOUT=600  # 10 minutes
readonly NETWORK_TIMEOUT=30

# Default versions (can be overridden by environment variables)
readonly RUBY_VERSION="${RUBY_VERSION:-2.7.3}"
readonly PYTHON_VERSION="${PYTHON_VERSION:-3.10.12}"
readonly JAVA_VERSION="${JAVA_VERSION:-11}"

# ----------------------------------
# Logging & Utilities
# ----------------------------------
log() {
    local level="$1"; shift
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $*" | tee -a "$LOG_FILE"
}

info() { log "INFO" "$@"; }
warn() { log "WARN" "$@"; }
error() { log "ERROR" "$@"; }
success() { log "SUCCESS" "$@"; }

progress() {
    local current="$1" total="$2" task="$3"
    printf "\r[%d/%d] %s..." "$current" "$total" "$task"
}

check_network() {
    info "Checking network connectivity..."
    if ! curl -s --max-time "$NETWORK_TIMEOUT" --head https://brew.sh > /dev/null; then
        error "Network connectivity check failed. Please check your internet connection."
        exit 1
    fi
    success "Network connectivity confirmed"
}

verify_installation() {
    local cmd="$1" name="$2"
    if command -v "$cmd" &>/dev/null; then
        success "$name installed successfully"
        return 0
    else
        error "$name installation failed - command '$cmd' not found"
        return 1
    fi
}

# ----------------------------------
# Usage and argument parsing
# ----------------------------------
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Options:
    --env-file PATH     Import environment variables from file
    --dry-run          Show what would be installed without executing
    --verbose          Enable verbose output
    --skip-gui         Skip GUI application installation
    --help             Show this help message

Environment Variables:
    RUBY_VERSION       Ruby version to install (default: $RUBY_VERSION)
    PYTHON_VERSION     Python version to install (default: $PYTHON_VERSION)
    JAVA_VERSION       Java version to install (default: $JAVA_VERSION)
EOF
}

ENV_FILE=""
DRY_RUN=false
VERBOSE=false
SKIP_GUI=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        --env-file)
            ENV_FILE="$2"; shift 2;;
        --dry-run)
            DRY_RUN=true; shift;;
        --verbose)
            VERBOSE=true; shift;;
        --skip-gui)
            SKIP_GUI=true; shift;;
        --help)
            usage; exit 0;;
        *)
            error "Unknown option: $1"
            usage; exit 1;;
    esac
done

# ----------------------------------
# Pre-flight checks
# ----------------------------------
info "Starting NYPL AMIP installation script"
info "Log file: $LOG_FILE"

if [[ "$OSTYPE" != "darwin"* ]]; then
    error "This script is designed for macOS only"
    exit 1
fi

check_network

# === NEW BLOCK ===
# Prompt for sudo password at the beginning and keep the timestamp alive
info "Checking for administrator (sudo) access..."
if sudo -v; then
    # Keep the sudo timestamp alive in the background
    while true; do sudo -n true; sleep 60; kill -0 "$$" || exit; done 2>/dev/null &
    success "Sudo access confirmed and timestamp will be kept alive."
else
    error "Sudo access failed. Please run this script as an Administrator."
    exit 1
fi
# === END NEW BLOCK ===

if [[ "$DRY_RUN" == true ]]; then
    info "DRY RUN MODE - No changes will be made"
fi

# ----------------------------------
# 1. Xcode Command-Line Tools (Enhanced)
# ----------------------------------
install_xcode_tools() {
    if xcode-select -p &>/dev/null; then
        success "Xcode Command-Line Tools already installed"
        return 0
    fi

    info "Installing Xcode Command-Line Tools..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would install Xcode Command-Line Tools"
        return 0
    fi

    # Trigger installation
    xcode-select --install 2>&1 | tee -a "$LOG_FILE" || true
    
    info "A dialog should appear. Please complete the installation."
    info "Waiting for installation to complete (timeout: $((XCODE_TIMEOUT/60)) minutes)..."
    
    local elapsed=0
    local check_interval=10
    
    while ! xcode-select -p &>/dev/null && [[ $elapsed -lt $XCODE_TIMEOUT ]]; do
        printf "."
        sleep $check_interval
        elapsed=$((elapsed + check_interval))
    done
    echo
    
    if [[ $elapsed -ge $XCODE_TIMEOUT ]]; then
        error "Xcode installation timed out after $((XCODE_TIMEOUT/60)) minutes"
        error "Please complete the installation manually and re-run this script"
        exit 1
    fi
    
    success "Xcode Command-Line Tools installed successfully"
}

install_xcode_tools

# ----------------------------------
# 2. Shell profile detection & setup
# ----------------------------------
detect_profile() {
    case "${SHELL##*/}" in
        zsh)   echo "$HOME/.zshrc" ;;
        bash)  echo "$HOME/.bash_profile" ;;
        ksh)   echo "$HOME/.profile" ;;
        *)     echo "$HOME/.profile" ;;
    esac
}

PROFILE="$(detect_profile)"
touch "$PROFILE"
info "Using shell profile: $PROFILE"

# ----------------------------------
# 3. Environment variables import
# ----------------------------------
if [[ -n "$ENV_FILE" ]]; then
    if [[ ! -f "$ENV_FILE" ]]; then
        error "Environment file not found: $ENV_FILE"
        exit 1
    fi
    
    info "Importing environment variables from $ENV_FILE"
    
    if [[ "$DRY_RUN" == false ]]; then
        while IFS= read -r line; do
            # Skip comments and empty lines
            [[ "$line" =~ ^\s*# ]] && continue
            [[ -z "${line// }" ]] && continue
            
            key="${line%%=*}"
            if ! grep -qE "export[[:space:]]+$key=" "$PROFILE"; then
                echo "export $line" >> "$PROFILE"
                info "Added $key to $PROFILE"
            else
                info "$key already exists in $PROFILE"
            fi
        done < "$ENV_FILE"
    else
        info "[DRY RUN] Would import variables from $ENV_FILE"
    fi
fi

# ----------------------------------
# 4. Homebrew installation with verification
# ----------------------------------
install_homebrew() {
    if command -v brew &>/dev/null; then
        success "Homebrew already installed"
        return 0
    fi

    info "Installing Homebrew..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would install Homebrew"
        return 0
    fi

    # Install Homebrew
    NONINTERACTIVE=1 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" 2>&1 | tee -a "$LOG_FILE"
    
    # Add to profile
    {
        echo
        echo '# Homebrew environment'
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"'
    } >> "$PROFILE"
    
    # Source for current session
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || true
    
    # Verify installation
    if ! verify_installation brew "Homebrew"; then
        error "Homebrew installation failed"
        exit 1
    fi
}

install_homebrew

# ----------------------------------
# 5. Homebrew taps
# ----------------------------------
install_taps() {
    local taps=(amiaopensource/amiaos)
    
    info "Installing Homebrew taps..."
    
    for tap in "${taps[@]}"; do
        if [[ "$DRY_RUN" == true ]]; then
            info "[DRY RUN] Would tap $tap"
            continue
        fi
        
        if ! brew tap-info "$tap" &>/dev/null; then
            info "Tapping $tap..."
            brew tap "$tap" 2>&1 | tee -a "$LOG_FILE"
        else
            info "$tap already tapped"
        fi
    done
}

install_taps

# ----------------------------------
# 6. Homebrew maintenance
# ----------------------------------
maintain_homebrew() {
    info "Updating and upgrading Homebrew..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would update and upgrade Homebrew"
        return 0
    fi
    
    brew update 2>&1 | tee -a "$LOG_FILE"
    brew upgrade 2>&1 | tee -a "$LOG_FILE"
    brew cleanup 2>&1 | tee -a "$LOG_FILE"
    
    success "Homebrew updated and cleaned"
}

maintain_homebrew

# ----------------------------------
# 7. CLI packages installation with progress
# ----------------------------------
install_cli_packages() {
    local packages=(
        git coreutils grep jq xmlstarlet tree wget trash
        p7zip rsync rclone gnu-tar awscli clamav
        graphicsmagick ffmpeg mediainfo mpc flac sox exiftool mkvtoolnix mediaconch qcli
        bagit rbenv jenv pyenv openjdk@11
    )
    
    info "Installing CLI packages (${#packages[@]} total)..."
    
    local installed=0
    local failed=()
    
    for i in "${!packages[@]}"; do
        local pkg="${packages[$i]}"
        progress "$((i+1))" "${#packages[@]}" "Installing $pkg"
        
        if [[ "$DRY_RUN" == true ]]; then
            echo " [DRY RUN]"
            continue
        fi
        
        if brew list "$pkg" &>/dev/null; then
            echo " [already installed]"
            ((installed++))
        else
            if brew install "$pkg" >>"$LOG_FILE" 2>&1; then
                echo " [success]"
                ((installed++))
            else
                echo " [FAILED]"
                failed+=("$pkg")
                warn "Failed to install $pkg"
            fi
        fi
    done
    
    echo
    success "CLI packages: $installed/${#packages[@]} installed successfully"
    
    if [[ ${#failed[@]} -gt 0 ]]; then
        error "Failed packages: ${failed[*]}"
        return 1
    fi
}

install_cli_packages

# ----------------------------------
# 8. GUI applications (with skip option)
# ----------------------------------
install_gui_apps() {
    if [[ "$SKIP_GUI" == true ]]; then
        info "Skipping GUI applications (--skip-gui specified)"
        return 0
    fi
    
    local apps=(the-unarchiver google-chrome zoom vlc qctools hex-fiend visual-studio-code)
    
    info "Installing GUI applications (${#apps[@]} total)..."
    
    local installed=0
    local failed=()
    
    for i in "${!apps[@]}"; do
        local app="${apps[$i]}"
        progress "$((i+1))" "${#apps[@]}" "Installing $app"
        
        if [[ "$DRY_RUN" == true ]]; then
            echo " [DRY RUN]"
            continue
        fi
        
        if brew list --cask "$app" &>/dev/null; then
            echo " [already installed]"
            ((installed++))
        else
            if brew install --cask "$app" >>"$LOG_FILE" 2>&1; then
                echo " [success]"
                ((installed++))
            else
                echo " [FAILED]"
                failed+=("$app")
                warn "Failed to install $app"
            fi
        fi
    done
    
    echo
    success "GUI applications: $installed/${#apps[@]} installed successfully"
    
    if [[ ${#failed[@]} -gt 0 ]]; then
        warn "Failed applications: ${failed[*]}"
    fi
}

install_gui_apps

# ----------------------------------
# 9. Mac App Store CLI
# ----------------------------------
install_mas() {
    info "Installing Mac App Store CLI..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would install mas"
        return 0
    fi
    
    if ! command -v mas &>/dev/null; then
        brew install mas 2>&1 | tee -a "$LOG_FILE"
        info "Please sign into the App Store before using 'mas' command"
    else
        success "mas already installed"
    fi
}

install_mas

# ----------------------------------
# 10. Shell profile setup for toolchains
# ----------------------------------
setup_toolchain_profile() {
    info "Setting up toolchain environment in shell profile..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would setup toolchain profile"
        return 0
    fi
    
    local marker="# — NYPL AMIP toolchains —"
    
    if grep -q "$marker" "$PROFILE"; then
        info "Toolchain setup already exists in $PROFILE"
        return 0
    fi
    
    cat >> "$PROFILE" << 'EOF'

# — NYPL AMIP toolchains —
# rbenv
export PATH="$HOME/.rbenv/bin:$PATH"
if command -v rbenv &>/dev/null; then
    eval "$(rbenv init -)"
fi
# jenv
export PATH="$HOME/.jenv/bin:$PATH"
if command -v jenv &>/dev/null; then
    eval "$(jenv init -)"
fi
# pyenv
export PATH="$HOME/.pyenv/bin:$PATH"
if command -v pyenv &>/dev/null; then
    eval "$(pyenv init -)"
fi
# VS Code CLI
export PATH="$PATH:/Applications/Visual Studio Code.app/Contents/Resources/app/bin"
EOF
    
    success "Toolchain setup added to $PROFILE"
}

setup_toolchain_profile

# ----------------------------------
# 11. Source profile with error handling
# ----------------------------------
reload_profile() {
    info "Reloading shell profile..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would reload profile"
        return 0
    fi
    
    # shellcheck disable=SC1090
    if source "$PROFILE" 2>/dev/null; then
        success "Profile reloaded successfully"
    else
        warn "Could not reload profile automatically. Please restart your terminal."
    fi
}

reload_profile

# ----------------------------------
# 12. Language runtime installation with verification
# ----------------------------------
install_language_runtimes() {
    info "Installing language runtimes..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would install Ruby $RUBY_VERSION, Python $PYTHON_VERSION, Java $JAVA_VERSION"
        return 0
    fi
    
    # Ruby
    info "Installing Ruby $RUBY_VERSION..."
    if ! rbenv versions 2>/dev/null | grep -q "$RUBY_VERSION"; then
        rbenv install "$RUBY_VERSION" 2>&1 | tee -a "$LOG_FILE"
    fi
    rbenv global "$RUBY_VERSION"
    
    # Java
    info "Configuring Java $JAVA_VERSION..."
    local java_home
    java_home="$(brew --prefix openjdk@11)/libexec/openjdk.jdk/Contents/Home"
    if [[ -d "$java_home" ]]; then
        jenv add "$java_home" 2>&1 | tee -a "$LOG_FILE" || true
        jenv global "$JAVA_VERSION"
    else
        warn "Java home not found at $java_home"
    fi
    
    # Python
    info "Installing Python $PYTHON_VERSION..."
    if ! pyenv versions 2>/dev/null | grep -q "$PYTHON_VERSION"; then
        pyenv install "$PYTHON_VERSION" 2>&1 | tee -a "$LOG_FILE"
    fi
    pyenv global "$PYTHON_VERSION"
    
    success "Language runtimes configured"
}

install_language_runtimes

# ----------------------------------
# 13. VS Code extensions with error handling
# ----------------------------------
install_vscode_extensions() {
    if [[ "$SKIP_GUI" == true ]]; then
        info "Skipping VS Code extensions (GUI apps skipped)"
        return 0
    fi
    
    if ! command -v code &>/dev/null; then
        warn "VS Code not found, skipping extensions"
        return 0
    fi
    
    local extensions=(
        github.vscode-pull-request-github
        DavidAnson.vscode-markdownlint
        yzhang.markdown-all-in-one
        streetsidesoftware.code-spell-checker
        DotJoshJohnson.xml
        mechatroner.rainbow-csv
        ms-python.python
        ms-toolsai.jupyter
        foxundermoon.shell-format
        bmalehorn.shell-syntax
        ms-vscode-remote.remote-ssh
        ms-vscode-remote.remote-ssh-edit
    )
    
    info "Installing VS Code extensions (${#extensions[@]} total)..."
    
    if [[ "$DRY_RUN" == true ]]; then
        info "[DRY RUN] Would install ${#extensions[@]} VS Code extensions"
        return 0
    fi
    
    local installed=0
    local failed=()
    
    for i in "${!extensions[@]}"; do
        local ext="${extensions[$i]}"
        progress "$((i+1))" "${#extensions[@]}" "Installing $ext"
        
        if code --install-extension "$ext" --force >>"$LOG_FILE" 2>&1; then
            echo " [success]"
            ((installed++))
        else
            echo " [FAILED]"
            failed+=("$ext")
        fi
    done
    
    echo
    success "VS Code extensions: $installed/${#extensions[@]} installed"
    
    if [[ ${#failed[@]} -gt 0 ]]; then
        warn "Failed extensions: ${failed[*]}"
    fi
}

install_vscode_extensions

# ----------------------------------
# 14. Post-installation verification
# ----------------------------------
verify_critical_tools() {
    info "Verifying critical AV preservation tools..."
    
    local critical_tools=(
        "ffmpeg:FFmpeg"
        "mediainfo:MediaInfo" 
        "sox:SoX"
        "exiftool:ExifTool"
        "qcli:QCTools CLI"
        "mediaconch:MediaConch"
    )
    
    local verified=0
    local failed=()
    
    for tool_info in "${critical_tools[@]}"; do
        IFS=':' read -r cmd name <<< "$tool_info"
        if command -v "$cmd" &>/dev/null; then
            success "$name verified"
            ((verified++))
        else
            error "$name not found"
            failed+=("$name")
        fi
    done
    
    info "Critical tools verification: $verified/${#critical_tools[@]} verified"
    
    if [[ ${#failed[@]} -gt 0 ]]; then
        warn "Missing critical tools: ${failed[*]}"
        warn "Some AV preservation workflows may not function properly"
    fi
}

verify_critical_tools

# ----------------------------------
# 15. Installation summary
# ----------------------------------
print_summary() {
    local end_time=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo
    echo "========================================="
    echo "NYPL AMIP Installation Complete"
    echo "========================================="
    echo "Completed at: $end_time"
    echo "Log file: $LOG_FILE"
    echo
    echo "Next steps:"
    echo "1. Restart your terminal or run: source $PROFILE"
    echo "2. Verify installations with: brew doctor"
    echo "3. Sign into Mac App Store for 'mas' functionality"
    echo "4. Check log file for any warnings or errors"
    echo
    
    if [[ "$DRY_RUN" == true ]]; then
        echo "NOTE: This was a dry run - no actual changes were made"
    fi
    
    success "Installation script completed successfully!"
}

print_summary