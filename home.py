"""SHAI Home — local HUD server."""
from __future__ import annotations

import base64
import datetime as dt
import platform
import threading
import webbrowser

from flask import Flask, jsonify, render_template, request

import config
import skills
import tts
from brain import Brain

app = Flask(__name__)
brain = Brain()
_lock = threading.Lock()


def _vitals() -> dict:
    data = {
        "cpu": None,
        "memory": None,
        "disk": None,
        "battery": None,
        "charging": None,
    }
    try:
        import psutil

        data["cpu"] = psutil.cpu_percent(interval=0.2)
        data["memory"] = psutil.virtual_memory().percent
        data["disk"] = psutil.disk_usage("/").percent
        batt = getattr(psutil, "sensors_battery", lambda: None)()
        if batt:
            data["battery"] = int(batt.percent)
            data["charging"] = bool(batt.power_plugged)
    except Exception:
        pass
    return data


@app.get("/")
def index():
    return render_template("home.html", name=config.ASSISTANT_NAME, user=config.USER_TITLE)


@app.get("/api/status")
def status():
    now = dt.datetime.now()
    return jsonify(
        {
            "name": config.ASSISTANT_NAME,
            "user": config.USER_TITLE,
            "model": config.MODEL if config.OPENAI_API_KEY else "offline",
            "online": bool(brain.client),
            "city": config.DEFAULT_CITY,
            "host": platform.node(),
            "system": f"{platform.system()} {platform.release()}",
            "time": now.strftime("%H:%M:%S"),
            "date": now.strftime("%A, %d %B %Y"),
            "voice": config.TTS_VOICE,
            "vitals": _vitals(),
        }
    )


@app.post("/api/chat")
def chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "empty"}), 400
    with _lock:
        reply = brain.think(message)
        audio_b64 = None
        mp3 = tts.synthesize_mp3(reply)
        if mp3:
            audio_b64 = base64.b64encode(mp3).decode("ascii")
    return jsonify({"reply": reply, "audio": audio_b64})


@app.post("/api/reset")
def reset():
    brain.reset()
    return jsonify({"ok": True})


@app.get("/api/notes")
def notes():
    return jsonify({"notes": skills.read_notes(8)})


def run_home(host: str = "127.0.0.1", port: int = 5000) -> None:
    url = f"http://{host}:{port}"
    print(f"\n  {config.ASSISTANT_NAME} Home → {url}")
    print(f"  Voice: {config.TTS_VOICE}\n")
    threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    app.run(host=host, port=port, debug=False, threaded=True)
