# S.H.A.I.

**Smart Helpful Artificial Intelligence** — a Jarvis-style desktop assistant with a local Home HUD.

Wake word → speech-to-text → LLM with tool calling → skills → spoken reply.

Also runs in the browser as **SHAI Home** with a male British neural voice.

## Features

- Voice (wake word "Shai") or keyboard mode
- Home HUD — orb, chat, mic, system vitals, quick commands
- Male neural voice (Microsoft Edge TTS, not Google)
- Time, weather, web search, Wikipedia
- Open apps and websites
- Notes, timers, system status, volume
- Add a new skill with one decorator
- Offline fallback if no API key is set

## Setup

```bash
git clone https://github.com/YOUR_USERNAME/shai.git
cd shai
python -m venv .venv
