# -*- coding: utf-8 -*-
"""AI 请求线程与服务边界。"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from PySide6.QtCore import QThread, Signal

from ..core.config import APP_VERSION



class AIStreamThread(QThread):
    chunk_received = Signal(str)
    result_ready = Signal(bool, str, bool)

    def __init__(self, settings: dict[str, Any], messages: list[dict[str, str]], max_tokens: int = 900) -> None:
        super().__init__()
        self.settings = dict(settings)
        self.messages = list(messages)
        self.max_tokens = max_tokens
        self.stop_requested = False

    def request_stop(self) -> None:
        self.stop_requested = True

    def run(self) -> None:
        base_url = str(self.settings.get("base_url", "")).strip().rstrip("/")
        payload = {
            "model": str(self.settings.get("model", "")).strip(),
            "messages": self.messages,
            "max_tokens": self.max_tokens,
            "temperature": 0.4,
            "stream": True,
        }
        request = urllib.request.Request(
            f"{base_url}/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {str(self.settings.get('api_key', '')).strip()}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Connection": "close",
                "User-Agent": f"WenshaCreator/{APP_VERSION}",
            },
            method="POST",
        )
        received = False
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                while not self.stop_requested:
                    raw_line = response.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        payload = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    for choice in payload.get("choices", []):
                        delta = choice.get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            received = True
                            self.chunk_received.emit(str(content))
                if self.stop_requested:
                    self.result_ready.emit(True, "已停止生成。", True)
                elif received:
                    self.result_ready.emit(True, "", False)
                else:
                    self.result_ready.emit(False, "AI 请求失败：未返回有效内容。", False)
        except urllib.error.HTTPError as exc:
            self.result_ready.emit(False, f"AI 请求失败：HTTP {exc.code}。请检查 Key、Base URL 或模型名。", False)
        except urllib.error.URLError as exc:
            self.result_ready.emit(False, f"AI 请求失败：{exc.reason}", False)
        except TimeoutError:
            self.result_ready.emit(False, "AI 请求失败：连接超时。", False)
