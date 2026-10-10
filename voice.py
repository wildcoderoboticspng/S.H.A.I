"""Microphone input and speech output, with graceful degradation to text."""
from __future__ import annotations

import queue
import threading

import config
import tts


class Speaker:
    """Thread-safe TTS queue so SHAI never talks over itself."""

    def __init__(self) -> None:
        self._queue: queue.Queue[str | None] = queue.Queue()
        self.enabled = config.VOICE_ENABLED
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _run(self) -> None:
        while True:
            text = self._queue.get()
            if text is None:
                break
            if self.enabled:
                try:
                    tts.speak(text)
                except Exception as exc:
                    print(f"[voice] speak failed: {exc}")
            self._queue.task_done()

    def say(self, text: str) -> None:
        if not text:
            return
        print(f"\n{config.ASSISTANT_NAME}: {text}\n")
        self._queue.put(text)

    def wait(self) -> None:
        self._queue.join()

    def shutdown(self) -> None:
        self._queue.put(None)


class Ears:
    def __init__(self) -> None:
        self.available = False
        try:
            import speech_recognition as sr

            self._sr = sr
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = config.MIC_ENERGY_THRESHOLD
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.pause_threshold = 0.8
            self.mic = sr.Microphone()
            with self.mic as source:
                print("[voice] Calibrating microphone... (stay quiet for a second)")
                self.recognizer.adjust_for_ambient_noise(source, duration=1.0)
            self.available = True
        except Exception as exc:
            print(f"[voice] Microphone unavailable ({exc}); using keyboard input.")

    def listen(self, timeout: float | None = None) -> str | None:
        if not self.available:
            try:
                return input("You: ").strip() or None
            except (EOFError, KeyboardInterrupt):
                return None

        try:
            with self.mic as source:
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=config.PHRASE_TIME_LIMIT,
                )
        except self._sr.WaitTimeoutError:
            return None
        except Exception as exc:
            print(f"[voice] listen error: {exc}")
            return None

        try:
            text = self.recognizer.recognize_google(audio)
            print(f"You: {text}")
            return text
        except self._sr.UnknownValueError:
            return None
        except self._sr.RequestError as exc:
            print(f"[voice] STT service error: {exc}")
            return None
