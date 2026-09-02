# -*- coding: utf-8 -*-
"""文件系统适配：回收站删除等平台相关操作。"""

from __future__ import annotations

import ctypes
import sys
from pathlib import Path


def move_path_to_recycle_bin(path: Path) -> None:
    if not sys.platform.startswith("win"):
        raise OSError("当前版本仅支持在 Windows 上移入回收站。")

    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ("hwnd", ctypes.c_void_p),
            ("wFunc", ctypes.c_uint),
            ("pFrom", ctypes.c_wchar_p),
            ("pTo", ctypes.c_wchar_p),
            ("fFlags", ctypes.c_ushort),
            ("fAnyOperationsAborted", ctypes.c_int),
            ("hNameMappings", ctypes.c_void_p),
            ("lpszProgressTitle", ctypes.c_wchar_p),
        ]

    operation = SHFILEOPSTRUCTW()
    operation.wFunc = 0x0003  # FO_DELETE
    operation.pFrom = str(path.resolve()) + "\0\0"
    operation.fFlags = 0x0040  # FOF_ALLOWUNDO: send to Recycle Bin when possible.

    result = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(operation))
    if result != 0:
        raise OSError(f"移入回收站失败，系统错误码：{result}")
    if operation.fAnyOperationsAborted:
        raise OSError("删除操作已取消。")
