# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtWidgets import QApplication  # noqa: E402

from novel_assistant.main import ProjectHomeWindow, load_app_settings, save_app_settings  # noqa: E402


def main() -> None:
    api_key = os.environ.get("WENSHA_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("missing WENSHA_API_KEY")
    settings = load_app_settings()
    settings.update(
        {
            "ai_enabled": True,
            "api_key": api_key,
            "base_url": os.environ.get("WENSHA_BASE_URL", "https://api.deepseek.com/v1").strip(),
            "model": os.environ.get("WENSHA_MODEL", "deepseek-chat").strip(),
        }
    )
    save_app_settings(settings)
    app = QApplication.instance() or QApplication([])
    window = ProjectHomeWindow()
    ok, message = window.perform_ai_connection_test(settings)
    window.close()
    print("ok" if ok else "fail")
    print(message)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
