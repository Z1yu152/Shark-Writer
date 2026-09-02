# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
from pathlib import Path

from cx_Freeze import Executable, setup

ROOT = Path(__file__).resolve().parents[1]

build_options = {
    "build_exe": str(ROOT / "dist" / "文鲨创作_cxfreeze_debug"),
    "path": [str(ROOT), *sys.path],
    "packages": ["PySide6", "shiboken6", "novel_assistant"],
    "includes": [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtNetwork",
    ],
    "include_files": [(str(ROOT / "assets"), "assets")],
    "zip_include_packages": [],
    "zip_exclude_packages": ["PySide6", "shiboken6", "novel_assistant"],
}

setup(
    name="wensha_creator_debug",
    version="1.0",
    description="debug build",
    options={"build_exe": build_options},
    executables=[
        Executable(
            str(ROOT / "scripts" / "debug_exe_startup.py"),
            base=None,
            target_name="文鲨创作_诊断.exe",
        )
    ],
)
