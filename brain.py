"""LLM conversation + tool-calling, with a rule-based offline fallback."""
from __future__ import annotations

import datetime as dt
import re

import config
import skills


class Brain:
    def __init__(self) -> None:
        self.history: list[dict] = []
        self.client = None
        if config.OPENAI_API_KEY:
            try:
                from openai import OpenAI

                self.client = OpenAI(api_key=config.OPENAI_API_KEY)
            except Exception as exc:
                print(f"[brain] OpenAI unavailable ({exc}); using offline rules.")

    def think(self, user_text: str) -> str:
        if self.client is None:
            return self._offline(user_text)
        try:
            return self._llm(user_text)
        except Exception as exc:
            print(f"[brain] LLM error: {exc}")
            return self._offline(user_text)

    def reset(self) -> None:
        self.history.clear()

    def _llm(self, user_text: str) -> str:
        self.history.append({"role": "user", "content": user_text})
        self._trim()

        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}] + self.history
        tools = skills.tool_schemas()

        for _ in range(5):
            resp = self.client.chat.completions.create(
                model=config.MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                temperature=0.6,
            )
            msg = resp.choices[0].message

            if not msg.tool_calls:
                answer = (msg.content or "").strip()
                self.history.append({"role": "assistant", "content": answer})
                return answer

            messages.append(msg.model_dump(exclude_none=True))
            for call in msg.tool_calls:
                print(f"[brain] → {call.function.name}({call.function.arguments})")
                result = skills.dispatch(call.function.name, call.function.arguments)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    }
                )

        return "That turned into rather a lot of steps. Try narrowing the request."

    def _trim(self) -> None:
        if len(self.history) > config.MAX_HISTORY:
            self.history = self.history[-config.MAX_HISTORY :]

    def _offline(self, text: str) -> str:
        t = text.lower().strip()

        rules = [
            (r"\b(time|clock|what.*date|what day)\b", lambda m: skills.get_time()),
            (
                r"\bweather\b(?:.*\bin\s+(?P<city>[a-z\s]+))?",
                lambda m: skills.get_weather((m.group("city") or "").strip() or None),
            ),
            (
                r"\b(open|launch|start)\s+(?P<app>[\w\s]+)",
                lambda m: skills.open_app(m.group("app").strip()),
            ),
            (
                r"\b(search|google|look up)\s+(?:for\s+)?(?P<q>.+)",
                lambda m: skills.web_search(m.group("q")),
            ),
            (
                r"\b(note|remember)\s+(?:that\s+)?(?P<n>.+)",
                lambda m: skills.add_note(m.group("n")),
            ),
            (r"\b(read|show).*notes\b", lambda m: skills.read_notes()),
            (r"\b(system|cpu|memory|battery|status)\b", lambda m: skills.system_status()),
            (
                r"\btimer\s+(?:for\s+)?(?P<n>\d+)\s*(?P<u>second|minute|hour)",
                lambda m: skills.set_timer(
                    int(m.group("n"))
                    * {"second": 1, "minute": 60, "hour": 3600}[m.group("u")]
                ),
            ),
            (
                r"\b(hello|hi|hey|good morning|good evening)\b",
                lambda m: f"Good {self._part_of_day()}, {config.USER_TITLE}. How can I help?",
            ),
            (r"\b(thanks|thank you)\b", lambda m: "Always a pleasure."),
            (
                r"\bwho are you\b",
                lambda m: f"I'm {config.ASSISTANT_NAME}, your personal assistant.",
            ),
        ]

        for pattern, handler in rules:
            match = re.search(pattern, t)
            if match:
                return handler(match)

        return (
            "I'm running without a language model, so I only handle direct commands "
            "like time, weather, open, search, notes, timers and system status."
        )

    @staticmethod
    def _part_of_day() -> str:
        h = dt.datetime.now().hour
        return "morning" if h < 12 else "afternoon" if h < 18 else "evening"
