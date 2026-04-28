# Voice Control

A lightweight macOS app that lets you control your terminal with your voice. Speak commands, edit them, and send them to iTerm or Terminal.app.

Uses OpenAI's Whisper for accurate, fully offline speech recognition.

## Features

- **Live transcription** — see your words appear as you speak
- **Works with iTerm & Terminal.app** — select in settings
- **Fully offline** — Whisper runs locally, no API keys needed
- **Adjustable silence detection** — auto-stops when you pause
- **Mic threshold control** — filter out background noise
- **Live audio level meter** — visualize mic input
- **Whisper model selection** — tiny, base, or small

## Install

Requires macOS 14+ and [Homebrew](https://brew.sh).

```bash
git clone https://github.com/drainas/VoiceControlApp.git
cd VoiceControlApp
./install.sh
```

The installer sets everything up and places **Voice Control.app** on your Desktop. Drag it to the Dock for quick access.

## Usage

1. Open iTerm (or Terminal.app)
2. Launch Voice Control
3. Click **Record** and speak
4. Text appears live as you talk
5. Edit if needed, then press **Enter** or click **Send**

### Voice commands

- Say **"execute"** at the end to auto-send
- Say **"clear"** to clear the input

## Requirements

Installed automatically by `install.sh`:

- Python 3.12
- portaudio
- python-tk
- openai-whisper
- PyAudio
- SpeechRecognition
