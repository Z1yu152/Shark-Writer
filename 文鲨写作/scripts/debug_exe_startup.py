# -*- coding: utf-8 -*-
from __future__ import annotations

import faulthandler
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from novel_assistant.main import APP_DIR, APP_NAME, RESOURCE_DIR, ProjectHomeWindow, load_application_fonts  # noqa: E402


def log(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    faulthandler.enable()
    try:
        log(f"APP_DIR={APP_DIR}")
        log(f"RESOURCE_DIR={RESOURCE_DIR}")
        log("stage=QApplication")
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        log("stage=load_fonts")
        load_application_fonts(app)
        log("stage=create_window")
        window = ProjectHomeWindow()
        log("stage=show")
        window.show()
        window.raise_()
        window.activateWindow()
        log(f"visible={window.isVisible()} title={window.windowTitle()!r} size={window.size().width()}x{window.size().height()}")
        QTimer.singleShot(5000, app.quit)
        result = app.exec()
        log(f"stage=exit code={result}")
        return result
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
