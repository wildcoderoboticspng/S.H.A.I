"""Male neural TTS via Microsoft Edge (not Google).

Primary: edge-tts → en-GB-RyanNeural
Fallback: pyttsx3 system male (David / Daniel / Alex)
"""
from __future__ import annotations

import asyncio
import os
import tempfile
import threading
import time
from pathlib import Path

import config

_pygame_ok = False
try:
    import pygame

    pygame.mixer.init()
    _pygame_ok = True
except Exception as exc:
    print(f"[tts] pygame mixer unavailable ({exc})")


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: list = []
    error: list = []

    def _target() -> None:
        try:
            result.append(asyncio.run(coro))
        except Exception as e:
            error.append(e)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join()
    if error:
        raise error[0]
    return result[0]


async def _edge_bytes(text: str) -> bytes:
    import edge_tts

    communicate = edge_tts.Communicate(
        text,
        voice=config.TTS_VOICE,
        rate=config.TTS_RATE_EDGE,
    )
    chunks: list[bytes] = []
    async for piece in communicate.stream():
        if piece["type"] == "audio":
            chunks.append(piece["data"])
    return b"".join(chunks)


def synthesize_mp3(text: str) -> bytes | None:
    """Return MP3 bytes from Edge neural TTS, or None on failure."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        audio = _run_async(_edge_bytes(text))
        return audio or None
    except Exception as exc:
        print(f"[tts] edge-tts failed ({exc})")
        return None


def _play_mp3_bytes(audio: bytes) -> None:
    if not _pygame_ok:
        raise RuntimeError("pygame mixer not initialised")
    fd, path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    try:
        Path(path).write_bytes(audio)
        pygame.mixer.music.load(path)
        pygame.mixer.music.set_volume(config.TTS_VOLUME)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.05)
    finally:
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        try:
            os.remove(path)
        except OSError:
            pass


def _pyttsx3_say(text: str) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty("rate", config.TTS_RATE)
    engine.setProperty("volume", config.TTS_VOLUME)
    try:
        for v in engine.getProperty("voices"):
            blob = f"{v.name} {getattr(v, 'id', '')}".lower()
            if any(
                k in blob
                for k in (
                    "david", "mark", "daniel", "alex", "george",
                    "james", "ryan", "guy", "male",
                )
            ):
                engine.setProperty("voice", v.id)
                break
    except Exception:
        pass
    engine.say(text)
    engine.runAndWait()


def speak(text: str) -> None:
    """Speak with male neural voice; fall back to system male TTS."""
    text = (text or "").strip()
    if not text:
        return
    audio = synthesize_mp3(text)
    if audio:
        try:
            _play_mp3_bytes(audio)
            return
        except Exception as exc:
            print(f"[tts] playback failed ({exc})")
    try:
        _pyttsx3_say(text)
    except Exception as exc:
        print(f"[tts] pyttsx3 failed ({exc})")
        print(f"{config.ASSISTANT_NAME}: {text}")
