"""Everything SHAI can do. Add a @skill function and the LLM can call it."""
from __future__ import annotations

import datetime as dt
import json
import platform
import shutil
import subprocess
import threading
import urllib.parse
import webbrowser
from dataclasses import dataclass, field
from typing import Any, Callable

import requests

import config


@dataclass
class Skill:
    name: str
    description: str
    func: Callable[..., str]
    parameters: dict[str, Any] = field(
        default_factory=lambda: {"type": "object", "properties": {}}
    )


REGISTRY: dict[str, Skill] = {}


def skill(description: str, parameters: dict[str, Any] | None = None):
    def decorator(fn: Callable[..., str]) -> Callable[..., str]:
        REGISTRY[fn.__name__] = Skill(
            name=fn.__name__,
            description=description,
            func=fn,
            parameters=parameters or {"type": "object", "properties": {}},
        )
        return fn

    return decorator


def tool_schemas() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": s.name,
                "description": s.description,
                "parameters": s.parameters,
            },
        }
        for s in REGISTRY.values()
    ]


def dispatch(name: str, arguments: str | dict) -> str:
    sk = REGISTRY.get(name)
    if not sk:
        return f"Unknown skill '{name}'."
    try:
        args = json.loads(arguments) if isinstance(arguments, str) else (arguments or {})
        return str(sk.func(**args))
    except Exception as exc:
        return f"Skill '{name}' failed: {exc}"


@skill("Get the current local time and date.")
def get_time() -> str:
    now = dt.datetime.now()
    return now.strftime("It is %H:%M on %A, %d %B %Y.")


@skill(
    "Get the current weather for a city.",
    {
        "type": "object",
        "properties": {
            "city": {"type": "string", "description": "City name, e.g. 'Tokyo'"}
        },
        "required": [],
    },
)
def get_weather(city: str | None = None) -> str:
    city = city or config.DEFAULT_CITY
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city, "count": 1},
        timeout=10,
    ).json()
    if not geo.get("results"):
        return f"I couldn't find a place called {city}."
    loc = geo["results"][0]

    wx = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "current": "temperature_2m,apparent_temperature,wind_speed_10m,weather_code",
            "daily": "temperature_2m_max,temperature_2m_min",
            "forecast_days": 1,
            "timezone": "auto",
        },
        timeout=10,
    ).json()

    codes = {
        0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
        45: "foggy", 48: "rime fog", 51: "light drizzle", 61: "light rain",
        63: "moderate rain", 65: "heavy rain", 71: "light snow", 73: "snow",
        75: "heavy snow", 80: "rain showers", 95: "thunderstorms",
    }
    c = wx["current"]
    d = wx["daily"]
    return (
        f"{loc['name']}: {codes.get(c['weather_code'], 'unsettled')}, "
        f"{round(c['temperature_2m'])}°C (feels like {round(c['apparent_temperature'])}°C), "
        f"wind {round(c['wind_speed_10m'])} km/h. "
        f"Today's range {round(d['temperature_2m_min'][0])} to "
        f"{round(d['temperature_2m_max'][0])}°C."
    )


@skill(
    "Open a web search in the user's browser.",
    {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    },
)
def web_search(query: str) -> str:
    webbrowser.open(f"https://duckduckgo.com/?q={urllib.parse.quote(query)}")
    return f"Searching the web for {query}."


@skill(
    "Open a specific website or URL.",
    {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL or bare domain"}
        },
        "required": ["url"],
    },
)
def open_website(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opening {urllib.parse.urlparse(url).netloc}."


@skill(
    "Look up a factual summary from Wikipedia.",
    {
        "type": "object",
        "properties": {"topic": {"type": "string"}},
        "required": ["topic"],
    },
)
def wikipedia(topic: str) -> str:
    r = requests.get(
        "https://en.wikipedia.org/api/rest_v1/page/summary/"
        + urllib.parse.quote(topic),
        headers={"User-Agent": "SHAI/1.0"},
        timeout=10,
    )
    if r.status_code != 200:
        return f"No Wikipedia article found for {topic}."
    return r.json().get("extract", "No summary available.")[:900]


_APP_ALIASES = {
    "browser": {"Windows": "start chrome", "Darwin": "open -a 'Google Chrome'", "Linux": "xdg-open https://"},
    "terminal": {"Windows": "start cmd", "Darwin": "open -a Terminal", "Linux": "x-terminal-emulator"},
    "files": {"Windows": "explorer", "Darwin": "open .", "Linux": "xdg-open ."},
    "calculator": {"Windows": "calc", "Darwin": "open -a Calculator", "Linux": "gnome-calculator"},
    "notepad": {"Windows": "notepad", "Darwin": "open -a TextEdit", "Linux": "gedit"},
    "spotify": {"Windows": "start spotify", "Darwin": "open -a Spotify", "Linux": "spotify"},
    "code": {"Windows": "code", "Darwin": "open -a 'Visual Studio Code'", "Linux": "code"},
}


@skill(
    "Launch a desktop application. Known aliases: browser, terminal, files, "
    "calculator, notepad, spotify, code. Any other name is tried as a command.",
    {
        "type": "object",
        "properties": {"app": {"type": "string"}},
        "required": ["app"],
    },
)
def open_app(app: str) -> str:
    key = app.lower().strip()
    system = platform.system()
    cmd = _APP_ALIASES.get(key, {}).get(system)

    if cmd is None:
        if shutil.which(key) is None and system != "Windows":
            return f"I don't know how to open {app} on this machine."
        cmd = key if system != "Windows" else f"start {key}"

    try:
        subprocess.Popen(cmd, shell=True)
        return f"Opening {app}."
    except Exception as exc:
        return f"Couldn't open {app}: {exc}"


@skill(
    "Save a note for the user.",
    {
        "type": "object",
        "properties": {"text": {"type": "string"}},
        "required": ["text"],
    },
)
def add_note(text: str) -> str:
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(config.NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {text}\n")
    return "Note saved."


@skill(
    "Read back the most recent saved notes.",
    {
        "type": "object",
        "properties": {"count": {"type": "integer", "default": 5}},
    },
)
def read_notes(count: int = 5) -> str:
    if not config.NOTES_FILE.exists():
        return "You have no notes."
    lines = [
        line.strip()
        for line in config.NOTES_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not lines:
        return "You have no notes."
    return "Your latest notes: " + " | ".join(lines[-count:])


_timer_callback: Callable[[str], None] | None = None


def set_timer_callback(cb: Callable[[str], None]) -> None:
    global _timer_callback
    _timer_callback = cb


@skill(
    "Set a countdown timer or reminder.",
    {
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "description": "Delay in seconds"},
            "label": {"type": "string", "description": "What the reminder is about"},
        },
        "required": ["seconds"],
    },
)
def set_timer(seconds: int, label: str = "your timer") -> str:
    def fire() -> None:
        msg = f"{config.USER_TITLE}, {label} is up."
        if _timer_callback:
            _timer_callback(msg)
        else:
            print(msg)

    threading.Timer(max(1, int(seconds)), fire).start()
    mins, secs = divmod(int(seconds), 60)
    human = f"{mins} minute{'s' if mins != 1 else ''}" if mins else f"{secs} seconds"
    return f"Timer set for {human}."


@skill("Report CPU, memory, disk and battery status of this computer.")
def system_status() -> str:
    try:
        import psutil
    except ImportError:
        return "psutil isn't installed, so I can't read system vitals."

    cpu = psutil.cpu_percent(interval=0.4)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage("/").percent
    out = f"CPU at {cpu} percent, memory at {mem} percent, disk at {disk} percent."
    batt = getattr(psutil, "sensors_battery", lambda: None)()
    if batt:
        charging = ", charging" if batt.power_plugged else ""
        out += f" Battery at {int(batt.percent)} percent{charging}."
    return out


@skill(
    "Change the system volume.",
    {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ["up", "down", "mute", "unmute"]}
        },
        "required": ["action"],
    },
)
def set_volume(action: str) -> str:
    system = platform.system()
    try:
        if system == "Darwin":
            cur = int(
                subprocess.check_output(
                    ["osascript", "-e", "output volume of (get volume settings)"]
                ).strip()
            )
            mapping = {"up": min(100, cur + 15), "down": max(0, cur - 15)}
            if action in mapping:
                subprocess.run(
                    ["osascript", "-e", f"set volume output volume {mapping[action]}"],
                    check=False,
                )
            else:
                muted = "false" if action == "unmute" else "true"
                subprocess.run(
                    ["osascript", "-e", f"set volume output muted {muted}"],
                    check=False,
                )
        elif system == "Linux":
            arg = {"up": "5%+", "down": "5%-", "mute": "mute", "unmute": "unmute"}[action]
            subprocess.run(["amixer", "-q", "sset", "Master", arg], check=False)
        else:
            return "Volume control isn't wired up on Windows yet."
        return f"Volume {action}."
    except Exception as exc:
        return f"Volume change failed: {exc}"
