# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
import sys

from cx_Freeze import Executable, setup

ROOT = Path(__file__).resolve().parents[1]

build_options = {
    "build_exe": str(ROOT / "dist" / "文鲨创作_cxfreeze"),
    "path": [str(ROOT), *sys.path],
    "packages": ["PySide6", "shiboken6", "novel_assistant"],
    "includes": [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
    ],
    "include_files": [(str(ROOT / "assets"), "assets")],
    "excludes": ["tkinter", "unittest", "email", "http.server", "xmlrpc"],
    "zip_include_packages": [],
    "zip_exclude_packages": ["PySide6", "shiboken6", "novel_assistant"],
}

setup(
    name="wensha_creator",
    version="1.0",
    description="本地小说创作辅助软件",
    options={"build_exe": build_options},
    executables=[
        Executable(
            str(ROOT / "run_app.py"),
            base="gui",
            target_name="文鲨创作.exe",
        )
    ],
)
