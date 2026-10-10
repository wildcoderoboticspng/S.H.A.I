#!/usr/bin/env python3
"""SHAI — entry point.

Usage:
    python main.py              # voice mode with wake word
    python main.py --text       # keyboard only
    python main.py --no-wake    # voice, always listening
    python main.py --home       # HUD in the browser
"""
from __future__ import annotations

import argparse
import sys
import time

import config
import skills
from brain import Brain
from voice import Ears, Speaker

BANNER = r"""
   ____  _   _    _    ___
  / ___|| | | |  / \  |_ _|
  \___ \| |_| | / _ \  | |
   ___) |  _  |/ ___ \ | |
  |____/|_| |_/_/   \_\___|
  Smart Helpful Artificial Intelligence
"""

EXIT_WORDS = {"exit", "quit", "goodbye", "shut down", "shutdown", "go to sleep", "stop"}


def contains_wake_word(text: str) -> tuple[bool, str]:
    low = text.lower()
    for w in config.WAKE_WORDS:
        if low.startswith(w):
            return True, text[len(w) :].lstrip(" ,.!?")
        if w in low:
            return True, low.split(w, 1)[1].lstrip(" ,.!?")
    return False, text


def main() -> None:
    parser = argparse.ArgumentParser(description="SHAI assistant")
    parser.add_argument("--text", action="store_true", help="keyboard input only")
    parser.add_argument("--no-wake", action="store_true", help="skip wake word")
    parser.add_argument("--home", action="store_true", help="open SHAI Home HUD in the browser")
    args = parser.parse_args()

    if args.home:
        from home import run_home

        print(BANNER)
        run_home()
        return

    print(BANNER)

    if args.text:
        config.VOICE_ENABLED = False

    speaker = Speaker()
    ears = Ears() if not args.text else None
    brain = Brain()
    skills.set_timer_callback(speaker.say)

    use_wake = bool(ears and ears.available and not args.no_wake)

    speaker.say(
        f"{config.ASSISTANT_NAME} online. "
        + (
            f"Say '{config.ASSISTANT_NAME}' to wake me."
            if use_wake
            else f"At your service, {config.USER_TITLE}."
        )
    )

    awake = not use_wake
    last_interaction = time.time()

    try:
        while True:
            if use_wake and awake and time.time() - last_interaction > 45:
                awake = False
                print("[shai] Going idle. Say the wake word.")

            if ears:
                text = ears.listen(timeout=None if not use_wake else 5)
            else:
                try:
                    text = input("You: ").strip() or None
                except (EOFError, KeyboardInterrupt):
                    break

            if not text:
                continue

            if use_wake and not awake:
                heard, remainder = contains_wake_word(text)
                if not heard:
                    continue
                awake = True
                last_interaction = time.time()
                if not remainder:
                    speaker.say(f"Yes, {config.USER_TITLE}?")
                    continue
                text = remainder
            elif use_wake:
                _, text = contains_wake_word(text)

            last_interaction = time.time()

            if text.lower().strip(" .!?") in EXIT_WORDS:
                speaker.say(f"Powering down. Goodbye, {config.USER_TITLE}.")
                break

            if text.lower().startswith(("reset", "new conversation", "forget")):
                brain.reset()
                speaker.say("Context cleared.")
                continue

            reply = brain.think(text)
            speaker.say(reply)
            speaker.wait()

    except KeyboardInterrupt:
        print("\n[shai] Interrupted.")
    finally:
        speaker.wait()
        speaker.shutdown()
        sys.exit(0)


if __name__ == "__main__":
    main()
