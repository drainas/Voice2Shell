#!/bin/bash
set -e

echo "============================="
echo "  Voice Control — Installer"
echo "============================="
echo ""

# Determine install directory
INSTALL_DIR="$HOME/VoiceControlApp"

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

# Copy app files
echo ""
echo "Installing to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp voice_control.py "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"

# Create virtual environment
echo "Setting up virtual environment..."
"$PYTHON" -m venv "$INSTALL_DIR/.venv"
"$INSTALL_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/.venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"
"$INSTALL_DIR/.venv/bin/pip" install --quiet openai-whisper
echo "✓ Virtual environment ready"

# Build .app bundle
echo ""
echo "Building Voice Control.app..."
APP="$INSTALL_DIR/Voice Control.app"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
mkdir -p "$APP/Contents/Resources"

# Launcher script
cat > "$APP/Contents/MacOS/launch" << LAUNCHER
#!/bin/bash
APPDIR="$INSTALL_DIR"
PYTHON_APP="$PYTHON_APP"
export PYTHONPATH="\$APPDIR/.venv/lib/python3.12/site-packages"
exec "\$PYTHON_APP" "\$APPDIR/voice_control.py"
LAUNCHER
chmod +x "$APP/Contents/MacOS/launch"

# Info.plist
cat > "$APP/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Voice Control</string>
    <key>CFBundleDisplayName</key>
    <string>Voice Control</string>
    <key>CFBundleIdentifier</key>
    <string>com.voicecontrol.app</string>
    <key>CFBundleVersion</key>
    <string>1.5</string>
    <key>CFBundleExecutable</key>
    <string>launch</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
    <key>NSMicrophoneUsageDescription</key>
    <string>Voice Control needs microphone access for speech recognition.</string>
</dict>
</plist>
PLIST

# Generate icon
"$INSTALL_DIR/.venv/bin/python3" << 'ICONPY'
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

# Copy to Desktop
cp -R "$APP" "$HOME/Desktop/Voice Control.app"
echo "✓ Copied to Desktop"

echo ""
echo "============================="
echo "  Installation complete!"
echo "============================="
echo ""
echo "  Double-click 'Voice Control' on your Desktop to launch."
echo "  Drag it to the Dock for quick access."
echo ""
echo "  First launch: macOS may ask you to right-click → Open"
echo "  to bypass the unidentified developer warning."
echo ""
echo "  The Whisper speech model (~150MB) downloads on first use."
echo ""
