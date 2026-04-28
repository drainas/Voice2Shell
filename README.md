# Voice2Shell

A lightweight app that lets you control your terminal with your voice. Speak commands, edit them, and send them to your terminal.

Uses OpenAI's Whisper for accurate, fully offline speech recognition.

## Features

- **Live transcription** — see your words appear as you speak
- **Fully offline** — Whisper runs locally, no API keys needed
- **Cross-platform** — macOS, Linux, and Windows
- **Global push-to-talk hotkey** — hold a key to record from anywhere
- **Adjustable silence detection** — auto-stops when you pause
- **Mic threshold control** — filter out background noise
- **Live audio level meter** — visualize mic input
- **Whisper model selection** — tiny, base, or small

## Install

### macOS

Requires macOS 14+ and [Homebrew](https://brew.sh).

```bash
git clone https://github.com/drainas/Voice2Shell.git
cd Voice2Shell
./install.sh
```

Installs **Voice2Shell.app** to `/Applications`. Find it via Launchpad or Spotlight.

### Linux

Requires Ubuntu 22.04+, Fedora 38+, or Arch Linux. X11 required for global hotkey and terminal send.

```bash
git clone https://github.com/drainas/Voice2Shell.git
cd Voice2Shell
./install.sh
```

Creates a desktop entry — find Voice2Shell in your application launcher.

### Windows

Requires Windows 10+ and Python 3.12+.

```powershell
git clone https://github.com/drainas/Voice2Shell.git
cd Voice2Shell
.\install.ps1
```

Creates a Start Menu shortcut.

## Usage

1. Open your terminal
2. Launch Voice2Shell
3. Click **Record** and speak
4. Text appears live as you talk
5. Edit if needed, then press **Enter** or click **Send**

### Supported terminals

| macOS | Linux | Windows |
|-------|-------|---------|
| iTerm | gnome-terminal | PowerShell |
| Terminal.app | konsole | cmd |
| | xfce4-terminal | Windows Terminal |
| | alacritty | |
| | xterm | |

### Voice commands

- Say **"execute"** at the end to auto-send
- Say **"clear"** to clear the input

### Push-to-talk

Hold the configured hotkey (default: Right Option/Alt) to record from any app. Release to transcribe and send to your terminal.

- **macOS**: Requires Accessibility permission (System Settings → Privacy & Security → Accessibility)
- **Linux**: Requires X11 (Wayland is not supported)
- **Windows**: Works natively

## Requirements

Installed automatically by the installer:

- Python 3.12+
- portaudio
- openai-whisper
- PyAudio
- SpeechRecognition
- numpy
