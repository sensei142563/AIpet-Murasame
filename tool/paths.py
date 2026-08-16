# -*- coding: utf-8 -*-
"""公共路径基准 — 统一「程序根目录」解析，杜绝 _internal/ 临时目录路径错位。

背景：
- 源码模式：__file__ 在项目根下的 tool/ 内 → 根 = dirname(dirname(__file__))
- exe 模式（PyInstaller onedir）：__file__ 在 _internal/ 内（会被 PyInstaller 解压），
  若用它推导数据目录 → 人脸/记忆/配置会写进 _internal/，重启后丢失或与子进程不同步。
  正确做法：exe 模式一律用「exe 所在目录」（可持久读写）。

用法：
    from tool.paths import app_base_dir, data_path
    FACE_DIR = data_path("face_shibie")
    CONFIG_PATH = data_path("config.json")
"""
import os
import sys


def app_base_dir() -> str:
    """程序根目录：
    - exe 模式 → exe 所在目录（持久可写，绿色版根）
    - 源码模式 → 项目根
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def data_path(*rel: str) -> str:
    """从程序根目录解析数据文件/目录的绝对路径（可传多段子路径）。"""
    return os.path.join(app_base_dir(), *rel)