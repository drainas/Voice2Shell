#!/bin/bash
set -e

echo "============================="
echo "  Voice2Shell — Installer"
echo "============================="
echo ""

# Detect OS
OS="$(uname -s)"

# Source directory (where this script lives)
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$OS" = "Darwin" ]; then
    # =========================================================================
    # macOS
    # =========================================================================

    # Check for Homebrew
    if ! command -v brew &>/dev/null; then
        echo "❌ Homebrew is required. Install it from https://brew.sh"
        echo '   Run: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
        exit 1
    fi
    echo "✓ Homebrew found"

    # Install system dependencies
    echo ""
    echo "Installing dependencies..."
    brew install portaudio python@3.12 python-tk@3.12 2>/dev/null || true
    echo "✓ Dependencies installed"

    # Find Python 3.12
    PYTHON="$(brew --prefix python@3.12)/bin/python3.12"
    if [ ! -f "$PYTHON" ]; then
        echo "❌ Python 3.12 not found"
        exit 1
    fi
    echo "✓ Python 3.12 found"

    # Find Python.app framework binary (needed for GUI)
    PYTHON_APP="$(brew --prefix python@3.12)/Frameworks/Python.framework/Versions/3.12/Resources/Python.app/Contents/MacOS/Python"
    if [ ! -f "$PYTHON_APP" ]; then
        echo "❌ Python.app framework not found"
        exit 1
    fi
    echo "✓ Python.app framework found"

    # Remove old Voice Control.app if it exists
    if [ -d "/Applications/Voice Control.app" ]; then
        rm -rf "/Applications/Voice Control.app"
        echo "✓ Removed old Voice Control.app"
    fi

    # Build .app bundle in /Applications
    echo ""
    echo "Building Voice2Shell.app..."
    APP="/Applications/Voice2Shell.app"
    rm -rf "$APP"
    mkdir -p "$APP/Contents/MacOS"
    mkdir -p "$APP/Contents/Resources"

    # Copy the main script into the app bundle
    cp "$SRC_DIR/voice2shell.py" "$APP/Contents/Resources/"
    cp "$SRC_DIR/platform_support.py" "$APP/Contents/Resources/"
    cp "$SRC_DIR/requirements.txt" "$APP/Contents/Resources/"

    # Create virtual environment inside the app bundle
    echo "Setting up virtual environment (this may take a minute)..."
    "$PYTHON" -m venv "$APP/Contents/Resources/.venv"
    "$APP/Contents/Resources/.venv/bin/pip" install --quiet --upgrade pip
    "$APP/Contents/Resources/.venv/bin/pip" install --quiet -r "$APP/Contents/Resources/requirements.txt"
    "$APP/Contents/Resources/.venv/bin/pip" install --quiet openai-whisper
    echo "✓ Virtual environment ready"

    # Launcher script — fully self-contained, references only paths inside the .app
    cat > "$APP/Contents/MacOS/launch" << LAUNCHER
#!/bin/bash
APPDIR="\$(dirname "\$0")/../Resources"
PYTHON_APP="$PYTHON_APP"
export PYTHONPATH="\$APPDIR/.venv/lib/python3.12/site-packages"
exec "\$PYTHON_APP" "\$APPDIR/voice2shell.py"
LAUNCHER
    chmod +x "$APP/Contents/MacOS/launch"

    # Info.plist
    cat > "$APP/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Voice2Shell</string>
    <key>CFBundleDisplayName</key>
    <string>Voice2Shell</string>
    <key>CFBundleIdentifier</key>
    <string>com.voice2shell.app</string>
    <key>CFBundleVersion</key>
    <string>1.7</string>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Voice2Shell needs microphone access for speech recognition.</string>
</dict>
</plist>
PLIST

    # Generate icon
    "$APP/Contents/Resources/.venv/bin/python3" << 'ICONPY'
import struct, zlib
SIZE = 256
def create_png(w, h, px):
    def chunk(t, d):
        c = t + d
        return struct.pack('>I', len(d)) + c + struct.pack('>I', zlib.crc32(c) & 0xffffffff)
    raw = b''
    for y in range(h):
        raw += b'\x00' + bytes(px[y*w*4:(y+1)*w*4])
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw, 9)) + chunk(b'IEND', b'')
px = [0]*(SIZE*SIZE*4)
cx, cy = SIZE//2, SIZE//2
for y in range(SIZE):
    for x in range(SIZE):
        dx, dy = x-cx, y-cy
        d = (dx*dx+dy*dy)**0.5
        i = (y*SIZE+x)*4
        if d < SIZE//2-2: px[i], px[i+1], px[i+2], px[i+3] = 0x1e, 0x1e, 0x2e, 255
        elif d < SIZE//2: px[i], px[i+1], px[i+2], px[i+3] = 0x31, 0x32, 0x44, 255
mic_w, mic_h, mic_y = 40, 70, cy-20
for y in range(SIZE):
    for x in range(SIZE):
        dx, dy = abs(x-cx), y-(mic_y-mic_h//2)
        i = (y*SIZE+x)*4
        if 0 <= dy <= mic_h and dx <= mic_w//2:
            if dy < mic_w//2:
                if (dx**2+(dy-mic_w//2)**2)**0.5 <= mic_w//2: px[i], px[i+1], px[i+2], px[i+3] = 0xf3, 0x8b, 0xa8, 255
            elif dy > mic_h-mic_w//2:
                if (dx**2+(dy-(mic_h-mic_w//2))**2)**0.5 <= mic_w//2: px[i], px[i+1], px[i+2], px[i+3] = 0xf3, 0x8b, 0xa8, 255
            else: px[i], px[i+1], px[i+2], px[i+3] = 0xf3, 0x8b, 0xa8, 255
for y in range(mic_y+mic_h//2, mic_y+mic_h//2+30):
    for x in range(cx-3, cx+4):
        if 0<=y<SIZE and 0<=x<SIZE: i=(y*SIZE+x)*4; px[i], px[i+1], px[i+2], px[i+3] = 0xa6, 0xe3, 0xa1, 255
by = mic_y+mic_h//2+28
for y in range(by, by+5):
    for x in range(cx-20, cx+21):
        if 0<=y<SIZE and 0<=x<SIZE: i=(y*SIZE+x)*4; px[i], px[i+1], px[i+2], px[i+3] = 0xa6, 0xe3, 0xa1, 255
for y in range(SIZE):
    for x in range(SIZE):
        dx, dy = x-cx, y-mic_y
        d = (dx*dx+dy*dy)**0.5
        if abs(d-45)<5 and dy>15:
            i=(y*SIZE+x)*4
            if px[i+3]==0 or px[i]==0x1e: px[i], px[i+1], px[i+2], px[i+3] = 0x89, 0xb4, 0xfa, 255
with open('/tmp/vc_icon.png','wb') as f: f.write(create_png(SIZE,SIZE,px))
ICONPY
    sips -s format icns /tmp/vc_icon.png --out "$APP/Contents/Resources/icon.icns" &>/dev/null
    rm /tmp/vc_icon.png
    echo "✓ App bundle created"

    # Clean up old Desktop copy if it exists
    if [ -d "$HOME/Desktop/Voice Control.app" ]; then
        rm -rf "$HOME/Desktop/Voice Control.app"
        echo "✓ Removed old Desktop copy"
    fi

    echo ""
    echo "============================="
    echo "  Installation complete!"
    echo "============================="
    echo ""
    echo "  Voice2Shell is now in /Applications."
    echo "  Find it in Launchpad or Spotlight (⌘+Space → Voice2Shell)."
    echo ""
    echo "  First launch: macOS may ask you to right-click → Open"
    echo "  to bypass the unidentified developer warning."
    echo ""
    echo "  You'll also need to grant Accessibility permission"
    echo "  (System Settings → Privacy & Security → Accessibility)"
    echo "  for the global push-to-talk hotkey to work."
    echo ""
    echo "  The Whisper speech model (~150MB) downloads on first use."
    echo ""

elif [ "$OS" = "Linux" ]; then
    # =========================================================================
    # Linux
    # =========================================================================

    echo "Detected Linux"
    echo ""

    # Detect package manager and install dependencies
    if command -v apt &>/dev/null; then
        echo "Using apt (Debian/Ubuntu)..."
        sudo apt update -y
        sudo apt install -y python3 python3-venv python3-tk portaudio19-dev xdotool
    elif command -v dnf &>/dev/null; then
        echo "Using dnf (Fedora)..."
        sudo dnf install -y python3 python3-tkinter portaudio-devel xdotool
    elif command -v pacman &>/dev/null; then
        echo "Using pacman (Arch)..."
        sudo pacman -S --noconfirm python python-virtualenv tk portaudio xdotool
    else
        echo "❌ No supported package manager found (apt, dnf, or pacman required)"
        exit 1
    fi
    echo "✓ System dependencies installed"

    # Create install directory
    INSTALL_DIR="$HOME/.local/share/voice2shell"
    mkdir -p "$INSTALL_DIR"
    echo "✓ Install directory created at $INSTALL_DIR"

    # Copy application files
    cp "$SRC_DIR/voice2shell.py" "$INSTALL_DIR/"
    cp "$SRC_DIR/platform_support.py" "$INSTALL_DIR/"
    cp "$SRC_DIR/requirements.txt" "$INSTALL_DIR/"
    echo "✓ Application files copied"

    # Create virtual environment
    echo "Setting up virtual environment (this may take a minute)..."
    python3 -m venv "$INSTALL_DIR/.venv"
    "$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
    "$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
    echo "✓ Virtual environment ready"

    # Create .desktop file
    DESKTOP_DIR="$HOME/.local/share/applications"
    mkdir -p "$DESKTOP_DIR"
    cat > "$DESKTOP_DIR/voice2shell.desktop" << DESKTOP
[Desktop Entry]
Name=Voice2Shell
Comment=Speak commands to your terminal
Exec=$HOME/.local/share/voice2shell/.venv/bin/python3 $HOME/.local/share/voice2shell/voice2shell.py
Icon=utilities-terminal
Terminal=false
Type=Application
Categories=Utility;
DESKTOP
    echo "✓ Desktop entry created"

    echo ""
    echo "============================="
    echo "  Installation complete!"
    echo "============================="
    echo ""
    echo "  Voice2Shell is installed at $INSTALL_DIR"
    echo "  Launch it from your application menu, or run:"
    echo "    $INSTALL_DIR/.venv/bin/python3 $INSTALL_DIR/voice2shell.py"
    echo ""
    echo "  The Whisper speech model (~150MB) downloads on first use."
    echo ""

else
    echo "❌ Unsupported operating system: $OS"
    echo "   Voice2Shell supports macOS (Darwin) and Linux."
    exit 1
fi
