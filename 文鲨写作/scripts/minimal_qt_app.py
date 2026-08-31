# -*- coding: utf-8 -*-
from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QLabel


def main() -> int:
    app = QApplication(sys.argv)
    label = QLabel("Qt OK")
    label.resize(240, 120)
    label.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
