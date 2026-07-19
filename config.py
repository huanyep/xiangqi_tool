"""
配置管理模块

管理应用的所有配置项, 支持 JSON 序列化/反序列化
"""

import json
import os
from pathlib import Path
from typing import Optional


# 默认配置
DEFAULT_CONFIG = {
    # 引擎设置
    "engine": {
        "path": "",                # 引擎路径, 空=自动搜索
        "think_time": 1000,        # 思考时间 (ms)
        "skill_level": 20,         # AI难度 (0-20)
        "hash_size": 64,           # 哈希表大小 (MB)
        "threads": 2,              # CPU线程数
    },

    # 视觉识别设置
    "vision": {
        "board_x": 0,              # 棋盘屏幕坐标 X
        "board_y": 0,              # 棋盘屏幕坐标 Y
        "board_size": 0,           # 棋盘像素大小
        "auto_detect": True,       # 是否自动检测棋盘
        "template_dir": "templates",
    },

    # 界面设置
    "ui": {
        "overlay_opacity": 0.85,   # 悬浮窗透明度 (0-1)
        "overlay_font_size": 14,   # 字体大小
        "overlay_position": "top-left",  # 悬浮窗位置
        "minimize_to_tray": True,  # 最小化到托盘
        "language": "zh",          # 语言
    },

    # 热键设置
    "hotkeys": {
        "toggle": "z",             # Z: 开启/关闭辅助
        "calibrate": "x",          # X: 刷新分析
        "quit": "esc",             # Esc: 退出
    },

    # 功能设置
    "features": {
        "auto_analyze": True,      # 启动后自动分析
        "show_best_move": True,    # 显示最优走法
        "show_score": True,        # 显示局面评分
        "show_pv": True,           # 显示推演变例
        "show_depth": True,        # 显示搜索深度
    },
}


class Config:
    """配置管理器"""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or str(
            Path(__file__).parent / "config.json"
        )
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def get(self, key: str, default=None):
        """获取配置值, 支持点号分隔的路径"""
        keys = key.split(".")
        val = self.data
        for k in keys:
            if isinstance(val, dict):
                val = val.get(k)
            else:
                return default
            if val is None:
                return default
        return val

    def set(self, key: str, value):
        """设置配置值, 支持点号分隔的路径"""
        keys = key.split(".")
        target = self.data
        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]
        target[keys[-1]] = self._to_native(value)
        self.save()

    @staticmethod
    def _to_native(val):
        """将 numpy 等第三方类型转为 Python 原生类型 (确保 JSON 可序列化)"""
        import numpy as np
        if isinstance(val, (np.integer,)):
            return int(val)
        if isinstance(val, (np.floating,)):
            return float(val)
        if isinstance(val, np.bool_):
            return bool(val)
        if isinstance(val, np.ndarray):
            return val.tolist()
        return val

    def load(self):
        """从文件加载配置"""
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                self._deep_merge(self.data, loaded)
            print(f"[INFO] 配置已加载: {self.config_path}")
        except FileNotFoundError:
            print(f"[INFO] 使用默认配置")
        except json.JSONDecodeError as e:
            print(f"[WARN] 配置文件解析失败: {e}")

    def save(self):
        """保存配置到文件"""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ERROR] 配置保存失败: {e}")

    def _deep_merge(self, base: dict, update: dict):
        """递归合并字典"""
        for key, val in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(val, dict):
                self._deep_merge(base[key], val)
            else:
                base[key] = val

    def reset(self):
        """重置为默认配置"""
        self.data = dict(DEFAULT_CONFIG)
        self.save()

    def to_dict(self) -> dict:
        return dict(self.data)
